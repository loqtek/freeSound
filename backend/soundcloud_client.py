"""SoundCloud API client to resolve track URLs and get streaming information."""

import os
import re
import time
import httpx
from typing import Optional, Dict, Any, List, Set

from utils.constants import BATCH_SIZE, HTTP_TIMEOUT, HTTP_MAX_CONNECTIONS, HTTP_MAX_KEEPALIVE_CONNECTIONS
from utils.drm_detection import is_drm_protected_url


class SoundCloudClient:
    """Client for interacting with SoundCloud API."""
    
    # SoundCloud web client IDs rotate; hardcoded values go stale quickly.
    # Prefer SOUNDCLOUD_CLIENT_ID or live extraction from sndcdn bundles.
    CLIENT_IDS: List[str] = []
    
    # Re-fetch client_id after this many seconds so cached IDs do not go stale mid-session.
    CLIENT_ID_TTL_SECONDS = 45 * 60
    
    # Stable public URL used only to verify that a client_id works with /resolve (same as real API usage).
    _VERIFY_RESOLVE_URL = "https://soundcloud.com/johnnycash"
    
    # User-Agent string for HTTP requests
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    
    def __init__(self):
        # Create HTTP client with optimized connection pooling
        limits = httpx.Limits(
            max_connections=HTTP_MAX_CONNECTIONS,
            max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS
        )
        self.client = httpx.AsyncClient(
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://soundcloud.com",
                "Referer": "https://soundcloud.com/",
            },
            timeout=HTTP_TIMEOUT,
            limits=limits
        )
        self.client_id: Optional[str] = None
        self._client_id_obtained_at: Optional[float] = None
    
    def _invalidate_client_id(self) -> None:
        self.client_id = None
        self._client_id_obtained_at = None
    
    async def _extract_client_ids_from_js_bundles(self) -> List[str]:
        """Extract client IDs from SoundCloud's JavaScript bundles (more reliable)."""
        found_ids = []
        try:
            # Get main page
            response = await self.client.get("https://soundcloud.com")
            response.raise_for_status()
            html_content = response.text
            
            # Find JavaScript bundle URLs - updated patterns
            js_url_patterns = [
                r'<script[^>]+src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"',
                r'<script[^>]+src="(https://[^"]*sndcdn[^"]*\.js)"',
                r'src="(https://[^"]*\.sndcdn\.com[^"]*\.js)"',
            ]
            js_urls = []
            for pattern in js_url_patterns:
                matches = re.findall(pattern, html_content)
                js_urls.extend(matches)
            
            # Remove duplicate URLs
            js_urls = list(dict.fromkeys(js_urls))
            
            # Also try to find client_id directly in HTML with more patterns
            html_patterns = [
                r'client_id["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32,})["\']',
                r'"client_id":"([a-zA-Z0-9]{32,})"',
                r'clientId["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32,})["\']',
                r'clientId["\']?\s*:\s*["\']([a-zA-Z0-9]{32,})["\']',
                r'client_id=([a-zA-Z0-9]{32,})',
                r'clientId=([a-zA-Z0-9]{32,})',
                r'CLIENT_ID["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32,})["\']',
                r'window\.__sc_hydration\s*=\s*[^;]*client[Ii]d["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32,})["\']',
            ]
            for pattern in html_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                found_ids.extend(matches)
            
            # Also check inline scripts and JSON data
            inline_script_pattern = r'<script[^>]*>(.*?)</script>'
            inline_scripts = re.findall(inline_script_pattern, html_content, re.DOTALL | re.IGNORECASE)
            for script in inline_scripts:
                for pattern in html_patterns:
                    matches = re.findall(pattern, script, re.IGNORECASE)
                    found_ids.extend(matches)
            
            # Look for JSON data in script tags
            json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>'
            json_scripts = re.findall(json_pattern, html_content, re.DOTALL | re.IGNORECASE)
            for json_data in json_scripts:
                for pattern in html_patterns:
                    matches = re.findall(pattern, json_data, re.IGNORECASE)
                    found_ids.extend(matches)
            
            # Extract from JS bundles (limit to first 15 to avoid too many requests)
            for js_url in js_urls[:15]:
                try:
                    js_response = await self.client.get(js_url, timeout=10)
                    if js_response.status_code == 200:
                        js_content = js_response.text
                        # Look for client_id in JS with multiple patterns
                        js_patterns = [
                            r'client_id:\s*["\']([a-zA-Z0-9]{32})["\']',
                            r'client_id["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32})["\']',
                            r'clientId["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32})["\']',
                            r'CLIENT_ID["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32})["\']',
                        ]
                        for pattern in js_patterns:
                            matches = re.findall(pattern, js_content)
                            found_ids.extend(matches)
                except Exception:
                    continue
            
            # Remove duplicates; SoundCloud web client_ids are 32 chars
            unique_ids = []
            seen = set()
            for cid in found_ids:
                if len(cid) == 32 and cid not in seen:
                    unique_ids.append(cid)
                    seen.add(cid)
            
            print(f"Extracted {len(unique_ids)} potential client_id(s) from SoundCloud")
            return unique_ids
        except Exception as e:
            # Log error but don't fail completely
            print(f"Warning: Failed to extract client IDs: {str(e)}")
            return []
    
    async def _verify_client_id(self, client_id: str) -> bool:
        """True if client_id works with /resolve (matches how we call the API for real URLs)."""
        try:
            response = await self.client.get(
                "https://api-v2.soundcloud.com/resolve",
                params={"url": self._VERIFY_RESOLVE_URL, "client_id": client_id},
                timeout=15,
            )
            if response.status_code != 200:
                return False
            data = response.json()
            return isinstance(data, dict) and data.get("kind") in ("user", "track", "playlist")
        except Exception:
            return False
    
    async def _collect_candidate_ids(self, exclude: Optional[Set[str]] = None) -> List[str]:
        """Ordered list of client_id candidates: env, extracted bundles, optional static fallbacks."""
        exclude = exclude or set()
        out: List[str] = []
        seen: Set[str] = set()

        def add(cid: Optional[str]) -> None:
            if not cid or cid in exclude or cid in seen:
                return
            if len(cid) != 32:
                return
            seen.add(cid)
            out.append(cid)

        env_client_id = os.getenv("SOUNDCLOUD_CLIENT_ID")
        if env_client_id:
            add(env_client_id.strip())

        extracted = await self._extract_client_ids_from_js_bundles()
        for cid in extracted:
            add(cid)
        for cid in self.CLIENT_IDS:
            add(cid)
        return out

    async def get_client_id(self, force_refresh: bool = False) -> str:
        """Extract and validate client ID from SoundCloud."""
        now = time.time()
        if (
            self.client_id
            and not force_refresh
            and self._client_id_obtained_at is not None
            and (now - self._client_id_obtained_at) < self.CLIENT_ID_TTL_SECONDS
        ):
            return self.client_id

        if force_refresh:
            self._invalidate_client_id()

        env_client_id = os.getenv("SOUNDCLOUD_CLIENT_ID")
        if env_client_id:
            print("Using client_id from SOUNDCLOUD_CLIENT_ID environment variable")
            eid = env_client_id.strip()
            if len(eid) == 32 and await self._verify_client_id(eid):
                self.client_id = eid
                self._client_id_obtained_at = time.time()
                return self.client_id
            print("Warning: SOUNDCLOUD_CLIENT_ID failed /resolve check, fetching from SoundCloud")

        all_candidates = await self._collect_candidate_ids()
        if not all_candidates:
            raise Exception("No client_id candidates found. Unable to extract from SoundCloud.")

        for candidate_id in all_candidates:
            try:
                if await self._verify_client_id(candidate_id):
                    self.client_id = candidate_id
                    self._client_id_obtained_at = time.time()
                    print(f"Successfully validated client_id: {candidate_id[:8]}...")
                    return self.client_id
            except Exception as e:
                print(f"Warning: Failed to verify client_id {candidate_id[:8]}...: {str(e)}")
                continue

        raise Exception(
            f"No valid client_id found. Tested {len(all_candidates)} candidates against /resolve. "
            "SoundCloud may have changed their site; ensure soundcloud.com is reachable. "
            "You can set SOUNDCLOUD_CLIENT_ID to a current web client id from their JS bundles."
        )
    
    async def resolve(self, url: str) -> Dict[str, Any]:
        """
        Resolve a SoundCloud URL - can be a track, playlist, or album.
        Returns the resolved object with its kind (track, playlist, album).
        """
        resolve_url = "https://api-v2.soundcloud.com/resolve"
        tried: Set[str] = set()

        async def fetch_resolved(cid: str) -> Optional[Dict[str, Any]]:
            r = await self.client.get(resolve_url, params={"url": url, "client_id": cid})
            if r.status_code == 200:
                return r.json()
            if r.status_code == 401:
                return None
            error_text = r.text[:200] if r.text else "No error details"
            raise Exception(f"Failed to resolve URL: {r.status_code} - {error_text}")

        try:
            primary = await self.get_client_id()
            if primary not in tried:
                data = await fetch_resolved(primary)
                if data is not None:
                    return data
                tried.add(primary)
                print("Resolve returned 401; rotating client_id candidates...")
        except Exception as e:
            err = str(e)
            if "No valid client_id" not in err and "No client_id candidates" not in err:
                raise Exception(f"Failed to resolve URL: {err}") from e
            print(f"Warning: {err}")

        self._invalidate_client_id()

        for cid in await self._collect_candidate_ids(exclude=tried):
            tried.add(cid)
            if not await self._verify_client_id(cid):
                continue
            data = await fetch_resolved(cid)
            if data is not None:
                self.client_id = cid
                self._client_id_obtained_at = time.time()
                return data

        raise Exception(
            "Failed to resolve URL: 401 Unauthorized - Invalid client_id. No error details. "
            "Exhausted all client_id candidates from SoundCloud bundles; try again shortly."
        )
    
    async def _resolve_url(self, url: str) -> Dict[str, Any]:
        """Resolve a SoundCloud URL (alias for resolve method)."""
        return await self.resolve(url)
    
    async def _get_tracks_by_ids(self, track_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Get full track data for multiple track IDs using batch endpoint."""
        if not track_ids:
            return {}
        
        all_tracks = {}
        
        try:
            # Limit to BATCH_SIZE tracks per request (SoundCloud API limit)
            for i in range(0, len(track_ids), BATCH_SIZE):
                batch = track_ids[i:i + BATCH_SIZE]
                ids_param = ",".join(str(tid) for tid in batch)
                
                tracks_url = "https://api-v2.soundcloud.com/tracks"
                tracks_data = None
                for attempt in range(1, 4):
                    client_id = await self.get_client_id(force_refresh=(attempt > 1))
                    params = {
                        "ids": ids_param,
                        "client_id": client_id,
                    }
                    response = await self.client.get(tracks_url, params=params)
                    if response.status_code == 401:
                        self._invalidate_client_id()
                        continue
                    response.raise_for_status()
                    tracks_data = response.json()
                    break
                if tracks_data is None:
                    continue
                
                # Handle response format
                if isinstance(tracks_data, list):
                    for track in tracks_data:
                        track_id = track.get("id")
                        if track_id:
                            all_tracks[track_id] = track
                elif isinstance(tracks_data, dict):
                    tracks = tracks_data.get("collection", [])
                    for track in tracks:
                        track_id = track.get("id")
                        if track_id:
                            all_tracks[track_id] = track
            
            return all_tracks
        except Exception as e:
            print(f"Warning: Failed to fetch tracks by IDs: {str(e)}")
            return {}
    
    async def get_info(self, url: str) -> Dict[str, Any]:
        """Get information about a track, playlist, or album."""
        try:
            data = await self.resolve(url)
            kind = data.get("kind", "track")
            
            if kind == "track":
                return self._format_track_info(data)
            elif kind in ["playlist", "album"]:
                return await self._format_playlist_info(data)
            else:
                raise Exception(f"Unsupported kind: {kind}")
                
        except Exception as e:
            raise Exception(f"Failed to get info: {str(e)}")
    
    def _format_track_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format track information."""
        # Safely get user data (handle None case)
        user_data = data.get("user") or {}
        
        return {
            "kind": "track",
            "title": data.get("title", "Unknown"),
            "artist": user_data.get("username", "Unknown") if isinstance(user_data, dict) else "Unknown",
            "duration": data.get("duration"),
            "description": data.get("description"),
            "artwork_url": (
                data.get("artwork_url") or
                (user_data.get("avatar_url") if isinstance(user_data, dict) else None)
            ),
            "playback_count": data.get("playback_count"),
            "likes_count": data.get("likes_count"),
            "permalink_url": data.get("permalink_url"),
            "id": data.get("id"),
        }
            
    async def _format_playlist_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format playlist/album information."""
        tracks = data.get("tracks", [])
        track_list = []
        
        # Collect all track IDs - fetch full data for all tracks using batch endpoint
        track_ids = [track.get("id") for track in tracks if track.get("id")]
        
        # Fetch full track data for all tracks using batch endpoint
        full_tracks_data = {}
        if track_ids:
            full_tracks_data = await self._get_tracks_by_ids(track_ids)
        
        # Build track list with complete data
        for track in tracks:
            track_id = track.get("id")
            title = track.get("title")
            track_user = track.get("user") or {}
            artist = track_user.get("username") if isinstance(track_user, dict) else None
            duration = track.get("duration", 0)
            
            # Use full track data if available (preferred source)
            if track_id and track_id in full_tracks_data:
                full_track = full_tracks_data[track_id]
                title = full_track.get("title", "Unknown")
                full_user = full_track.get("user") or {}
                artist = full_user.get("username", "Unknown") if isinstance(full_user, dict) else "Unknown"
                duration = full_track.get("duration", 0)
            # If batch fetch didn't work and we have incomplete data, try individual fetch
            elif (not title or not artist) and track_id:
                try:
                    full_track = await self.resolve(f"https://soundcloud.com/tracks/{track_id}")
                    title = full_track.get("title", "Unknown")
                    full_user = full_track.get("user") or {}
                    artist = full_user.get("username", "Unknown") if isinstance(full_user, dict) else "Unknown"
                    duration = full_track.get("duration", 0)
                except Exception:
                    title = title or "Unknown"
                    artist = artist or "Unknown"
            
            track_list.append({
                "title": title or "Unknown",
                "artist": artist or "Unknown",
                "duration": duration,
                "id": track_id,
            })
        
        # Safely get user data (handle None case)
        user_data = data.get("user") or {}
        
        return {
            "kind": data.get("kind", "playlist"),
            "title": data.get("title", "Unknown"),
            "artist": user_data.get("username", "Unknown") if isinstance(user_data, dict) else "Unknown",
            "description": data.get("description"),
            "artwork_url": (
                data.get("artwork_url") or
                (user_data.get("avatar_url") if isinstance(user_data, dict) else None)
            ),
            "track_count": len(tracks),
            "tracks": track_list,
            "permalink_url": data.get("permalink_url"),
            "id": data.get("id"),
        }
    
    async def get_stream_url(self, url_or_data) -> Dict[str, Any]:
        """
        Get the HLS stream URL for a track.
        Can accept either a URL string or track data dict.
        Returns dict with m3u8_url, title, and artist.
        """
        # If it's a string, treat it as a URL and resolve it first
        if isinstance(url_or_data, str):
            track_data = await self.resolve(url_or_data)
            if track_data.get("kind") != "track":
                raise Exception("URL must be a track, not a playlist or album")
        else:
            track_data = url_or_data
        
        # Extract track ID and media info
        track_id = track_data.get("id")
        media = track_data.get("media", {})
        transcodings = media.get("transcodings", [])
        
        if not transcodings:
            raise ValueError("No transcodings available for this track")
        
        # Separate DRM and non-DRM transcodings
        non_drm_transcodings = []
        drm_transcodings = []
        
        for tc in transcodings:
            format_data = tc.get("format") or {}
            protocol = format_data.get("protocol", "").lower() if isinstance(format_data, dict) else ""
            url = tc.get("url", "").lower()
            
            if "hls" in protocol or "stream" in protocol:
                if "cenc" not in url:
                    non_drm_transcodings.append(tc)
                else:
                    drm_transcodings.append(tc)
        
        # Get track authorization if available
        track_authorization = track_data.get("track_authorization")
        
        # Try all non-DRM transcodings first
        transcodings_to_try = non_drm_transcodings if non_drm_transcodings else drm_transcodings
        
        if not transcodings_to_try:
            raise ValueError("No HLS transcodings available for this track")
        
        # Safely get user data for artist name
        user_data = track_data.get("user") or {}
        artist_name = user_data.get("username", "Unknown") if isinstance(user_data, dict) else "Unknown"
        
        # Try each transcoding until we find one that works and isn't DRM-protected
        last_error = None
        for hls_transcoding in transcodings_to_try:
            try:
                base_stream = hls_transcoding.get("url")
                if not base_stream:
                    continue
                
                stream_info = None
                for auth_try in range(1, 5):
                    client_id = await self.get_client_id(force_refresh=(auth_try > 1))
                    stream_url = base_stream
                    if "?" in stream_url:
                        stream_url += f"&client_id={client_id}"
                    else:
                        stream_url += f"?client_id={client_id}"
                    if track_authorization:
                        stream_url += f"&track_authorization={track_authorization}"
                    response = await self.client.get(stream_url)
                    if response.status_code == 401:
                        print("Stream step returned 401; rotating client_id...")
                        self._invalidate_client_id()
                        continue
                    response.raise_for_status()
                    stream_info = response.json()
                    break
                if stream_info is None:
                    continue
                
                m3u8_url = stream_info.get("url")
                if not m3u8_url:
                    continue
                
                # Check if the final m3u8 URL indicates DRM protection
                if is_drm_protected_url(m3u8_url):
                    # This is a DRM-protected stream, skip it and try next transcoding
                    if hls_transcoding in non_drm_transcodings:
                        non_drm_transcodings.remove(hls_transcoding)
                        if non_drm_transcodings:
                            continue
                    last_error = Exception("Track is DRM-protected and cannot be downloaded")
                    continue
                
                # Successfully found a non-DRM stream
                return {
                    "m3u8_url": m3u8_url,
                    "title": track_data.get("title", "Unknown"),
                    "artist": artist_name,
                }
                
            except httpx.HTTPStatusError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue
        
        # Try alternative method if all transcodings failed
        try:
            client_id = await self.get_client_id()
            m3u8_url = await self._try_alternative_stream_url(
                track_id,
                track_authorization,
                client_id,
                transcodings
            )
            if m3u8_url and not is_drm_protected_url(m3u8_url):
                user_data = track_data.get("user") or {}
                artist_name = user_data.get("username", "Unknown") if isinstance(user_data, dict) else "Unknown"
                return {
                    "m3u8_url": m3u8_url,
                    "title": track_data.get("title", "Unknown"),
                    "artist": artist_name,
                }
        except Exception:
            pass
        
        # If we get here, all transcodings failed or are DRM-protected
        if last_error:
            if isinstance(last_error, Exception) and "DRM-protected" in str(last_error):
                raise last_error
            raise Exception("Failed to get stream URL: All transcodings failed or are DRM-protected")
        else:
            raise Exception("Failed to get stream URL: No working transcodings found")
    
    async def _try_alternative_stream_url(
        self,
        track_id: int,
        track_authorization: Optional[str],
        client_id: str,
        transcodings: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Try alternative method to get stream URL."""
        # Extract secret from transcoding URL
        secret = None
        for tc in transcodings:
            secret_url = tc.get("url", "")
            if secret_url:
                parts = secret_url.split("/")
                if len(parts) >= 2:
                    secret = parts[-2]
                    break
        
        if not secret or not track_id:
            return None
        
        cid = client_id
        for attempt in range(1, 4):
            media_url = f"https://api-v2.soundcloud.com/media/soundcloud:tracks:{track_id}/{secret}/stream/hls"
            if track_authorization:
                media_url += f"?client_id={cid}&track_authorization={track_authorization}"
            else:
                media_url += f"?client_id={cid}"
            try:
                response = await self.client.get(media_url)
                if response.status_code == 401:
                    self._invalidate_client_id()
                    cid = await self.get_client_id(force_refresh=True)
                    continue
                response.raise_for_status()
                stream_info = response.json()
                return stream_info.get("url")
            except Exception:
                if attempt < 3:
                    self._invalidate_client_id()
                    cid = await self.get_client_id(force_refresh=True)
                continue
        return None
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
