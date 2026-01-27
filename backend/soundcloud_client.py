"""SoundCloud API client to resolve track URLs and get streaming information."""

import os
import re
import httpx
from typing import Optional, Dict, Any, List

from utils.constants import BATCH_SIZE, HTTP_TIMEOUT, HTTP_MAX_CONNECTIONS, HTTP_MAX_KEEPALIVE_CONNECTIONS
from utils.drm_detection import is_drm_protected_url


class SoundCloudClient:
    """Client for interacting with SoundCloud API."""
    
    # Common SoundCloud client IDs (these may need to be updated)
    # These are used as fallback if client_id extraction from SoundCloud fails
    CLIENT_IDS = [
        "xXKzFLdhfXAtbaLbKFp4cNoiduLizuYO",
        "LvWovRaZq8q5f1Z2K0t1Y7v5fJ8xK9pL",
        "dH1Xed1fpITYonugor6sw39jvdq58M3h",
        "02gUJC0hH2ct1EGOcYXQIzRFU91c72Ea",
    ]
    
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
                            r'client_id["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32,})["\']',
                            r'clientId["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32,})["\']',
                            r'CLIENT_ID["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{32,})["\']',
                            r'["\']([a-zA-Z0-9]{32})["\']',  # Generic 32-char strings (common client_id length)
                            r'client_id:\s*["\']([a-zA-Z0-9]{32,})["\']',
                            r'clientId:\s*["\']([a-zA-Z0-9]{32,})["\']',
                        ]
                        for pattern in js_patterns:
                            matches = re.findall(pattern, js_content)
                            found_ids.extend(matches)
                except Exception:
                    continue
            
            # Remove duplicates and validate (client_ids are typically 32 chars)
            unique_ids = []
            seen = set()
            for cid in found_ids:
                # SoundCloud client_ids are typically exactly 32 characters
                if len(cid) >= 30 and len(cid) <= 35 and cid not in seen:
                    unique_ids.append(cid)
                    seen.add(cid)
            
            print(f"Extracted {len(unique_ids)} potential client_id(s) from SoundCloud")
            return unique_ids
        except Exception as e:
            # Log error but don't fail completely
            print(f"Warning: Failed to extract client IDs: {str(e)}")
            return []
    
    async def _test_client_id(self, client_id: str) -> bool:
        """Test if a client_id is valid by making a simple API call."""
        try:
            # Try multiple test endpoints to validate client_id
            test_urls = [
                ("https://api-v2.soundcloud.com/tracks", {"ids": "13158665", "client_id": client_id}),
                ("https://api-v2.soundcloud.com/resolve", {"url": "https://soundcloud.com/johnnycash", "client_id": client_id}),
            ]
            
            for test_url, params in test_urls:
                try:
                    response = await self.client.get(test_url, params=params, timeout=10)
                    if response.status_code == 200:
                        # Verify we got valid data
                        data = response.json()
                        if data and (isinstance(data, dict) or isinstance(data, list)):
                            return True
                except Exception:
                    continue
            return False
        except Exception:
            return False
    
    async def get_client_id(self, force_refresh: bool = False) -> str:
        """Extract and validate client ID from SoundCloud."""
        if self.client_id and not force_refresh:
            return self.client_id
        
        # Check for manually set client_id from environment variable
        env_client_id = os.getenv("SOUNDCLOUD_CLIENT_ID")
        if env_client_id:
            print("Using client_id from SOUNDCLOUD_CLIENT_ID environment variable")
            if await self._test_client_id(env_client_id):
                self.client_id = env_client_id
                return self.client_id
            else:
                print("Warning: Environment variable client_id is invalid, falling back to extraction")
        
        # Try to extract from JS bundles first
        extracted_ids = await self._extract_client_ids_from_js_bundles()
        
        # Combine with fallback IDs (prioritize extracted ones)
        all_candidates = extracted_ids + self.CLIENT_IDS
        
        if not all_candidates:
            raise Exception("No client_id candidates found. Unable to extract from SoundCloud.")
        
        # Test each candidate
        for candidate_id in all_candidates:
            try:
                if await self._test_client_id(candidate_id):
                    self.client_id = candidate_id
                    print(f"Successfully validated client_id: {candidate_id[:8]}...")
                    return self.client_id
            except Exception as e:
                print(f"Warning: Failed to test client_id {candidate_id[:8]}...: {str(e)}")
                continue
        
        # If all fail, raise a more descriptive error
        raise Exception(
            f"No valid client_id found. Tested {len(all_candidates)} candidates. "
            "SoundCloud may have changed their API or the client IDs may be expired. "
            "Please check if SoundCloud is accessible and try again. "
            "You can also set SOUNDCLOUD_CLIENT_ID environment variable with a valid client_id."
        )
    
    async def resolve(self, url: str) -> Dict[str, Any]:
        """
        Resolve a SoundCloud URL - can be a track, playlist, or album.
        Returns the resolved object with its kind (track, playlist, album).
        """
        resolve_url = "https://api-v2.soundcloud.com/resolve"
        
        # Try with current client_id first
        try:
            client_id = await self.get_client_id()
        except Exception as e:
            # If we can't get a client_id, try to extract one more time
            print(f"Warning: Failed to get client_id initially: {str(e)}")
            self.client_id = None
            client_id = await self.get_client_id(force_refresh=True)
        
        params = {
            "url": url,
            "client_id": client_id,
        }
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = await self.client.get(resolve_url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # If we get 401, try refreshing client_id and retry
                if e.response.status_code == 401:
                    if attempt < max_retries - 1:
                        # Clear cached client_id and get a fresh one
                        print(f"Got 401 error, refreshing client_id (attempt {attempt + 1}/{max_retries})...")
                        self.client_id = None
                        try:
                            new_client_id = await self.get_client_id(force_refresh=True)
                            params["client_id"] = new_client_id
                            continue  # Retry with new client_id
                        except Exception as refresh_error:
                            print(f"Warning: Failed to refresh client_id: {str(refresh_error)}")
                            # Try one more extraction attempt
                            if attempt == 0:
                                continue
                    
                    # If all retries failed, raise error with more context
                    error_text = e.response.text[:200] if e.response.text else "No error details"
                    raise Exception(
                        f"Failed to resolve URL: 401 Unauthorized - Invalid client_id. "
                        f"Tried {max_retries} times. {error_text}. "
                        "SoundCloud may have changed their API authentication. "
                        "Please try again in a few moments."
                    )
                
                # For other HTTP errors, raise immediately
                error_text = e.response.text[:200] if e.response.text else "No error details"
                raise Exception(f"Failed to resolve URL: {e.response.status_code} - {error_text}")
            except Exception as e:
                # For non-HTTP errors, raise immediately
                raise Exception(f"Failed to resolve URL: {str(e)}")
        
        # Should not reach here, but just in case
        raise Exception("Failed to resolve URL after all retry attempts")
    
    async def _resolve_url(self, url: str) -> Dict[str, Any]:
        """Resolve a SoundCloud URL (alias for resolve method)."""
        return await self.resolve(url)
    
    async def _get_tracks_by_ids(self, track_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Get full track data for multiple track IDs using batch endpoint."""
        if not track_ids:
            return {}
        
        client_id = await self.get_client_id()
        all_tracks = {}
        
        try:
            # Limit to BATCH_SIZE tracks per request (SoundCloud API limit)
            for i in range(0, len(track_ids), BATCH_SIZE):
                batch = track_ids[i:i + BATCH_SIZE]
                ids_param = ",".join(str(tid) for tid in batch)
                
                tracks_url = "https://api-v2.soundcloud.com/tracks"
                params = {
                    "ids": ids_param,
                    "client_id": client_id,
                }
                
                response = await self.client.get(tracks_url, params=params)
                response.raise_for_status()
                tracks_data = response.json()
                
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
        
        client_id = await self.get_client_id()
        
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
                stream_url = hls_transcoding.get("url")
                if not stream_url:
                    continue
                
                # Add client_id to the URL
                if "?" in stream_url:
                    stream_url += f"&client_id={client_id}"
                else:
                    stream_url += f"?client_id={client_id}"
                
                # Add track authorization if available
                if track_authorization:
                    stream_url += f"&track_authorization={track_authorization}"
                
                # Fetch the actual m3u8 URL
                response = await self.client.get(stream_url)
                response.raise_for_status()
                stream_info = response.json()
                
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
        
        media_url = f"https://api-v2.soundcloud.com/media/soundcloud:tracks:{track_id}/{secret}/stream/hls"
        if track_authorization:
            media_url += f"?client_id={client_id}&track_authorization={track_authorization}"
        else:
            media_url += f"?client_id={client_id}"
        
        try:
            response = await self.client.get(media_url)
            response.raise_for_status()
            stream_info = response.json()
            return stream_info.get("url")
        except Exception:
            return None
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
