"""Handles downloading and converting SoundCloud media."""
import asyncio
import subprocess
import tempfile
import os
import zipfile
from typing import Dict, Any, Optional
from fastapi.responses import StreamingResponse

from soundcloud_client import SoundCloudClient
from utils.constants import (
    MIN_FILE_SIZE,
    FFMPEG_BITRATE,
    FFMPEG_CODEC,
    FFMPEG_THREADS,
    FFMPEG_QUALITY,
    MAX_FILENAME_LENGTH,
    REQUEST_DELAY,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_CONCURRENT_FFMPEG,
    ZIP_COMPRESSION_LEVEL,
    STREAM_CHUNK_SIZE,
)
from utils.file_utils import sanitize_filename, validate_file_size, get_file_size
from utils.metadata import add_metadata_to_mp3
from utils.cover_art import download_cover_art
from utils.drm_detection import is_drm_protected_url, check_drm_in_content
from utils.logger import log


class SoundCloudDownloader:
    """Handles downloading and converting SoundCloud media."""
    
    def __init__(self):
        self.sc_client = SoundCloudClient()
        # Semaphores for resource management
        self.download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self.ffmpeg_semaphore = asyncio.Semaphore(MAX_CONCURRENT_FFMPEG)
    
    async def _download_with_ffmpeg(self, m3u8_url: str, output_path: str) -> bool:
        """Download and convert HLS stream to MP3 using ffmpeg with optimized settings."""
        # Acquire semaphore to limit concurrent ffmpeg processes
        async with self.ffmpeg_semaphore:
            try:
                # Check for DRM in URL
                if is_drm_protected_url(m3u8_url):
                    raise Exception("Track is DRM-protected (encrypted) and cannot be downloaded")
                
                # Build optimized ffmpeg command for faster encoding
                cmd = [
                    "ffmpeg",
                    "-threads", FFMPEG_THREADS,  # Use all CPU cores
                    "-i", m3u8_url,
                    "-c:a", FFMPEG_CODEC,
                    "-b:a", FFMPEG_BITRATE,
                    "-q:a", FFMPEG_QUALITY,  # Quality preset for faster encoding
                    "-y",  # Overwrite output
                    "-loglevel", "error",  # Reduce logging overhead
                    output_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                # Check stderr for DRM-related errors
                if stderr:
                    stderr_text = stderr.decode('utf-8', errors='ignore')
                    drm_error = check_drm_in_content(stderr_text)
                    if drm_error:
                        raise Exception(drm_error)
                
                if process.returncode != 0:
                    # Try with additional headers for authentication
                    success = await self._retry_with_headers(m3u8_url, output_path)
                    if not success:
                        error_msg = stderr.decode() if stderr else "Unknown error"
                        raise Exception(f"FFmpeg conversion failed: {error_msg}")
                
                # Validate file
                if not validate_file_size(output_path, MIN_FILE_SIZE):
                    log("Warning: Downloaded file is suspiciously small")
                    return False
                
                return True
                
            except Exception as e:
                raise Exception(f"Download failed: {str(e)}")
    
    async def _retry_with_headers(self, m3u8_url: str, output_path: str) -> bool:
        """Retry download with proper headers."""
        try:
            headers = {
                "User-Agent": self.sc_client.USER_AGENT,
                "Referer": "https://soundcloud.com/",
                "Origin": "https://soundcloud.com",
            }
            
            # Download m3u8 content first to check if it needs authentication
            response = await self.sc_client.client.get(m3u8_url, headers=headers)
            if response.status_code != 200:
                return False
            
            m3u8_content = response.text
            
            # Check m3u8 content for DRM indicators
            drm_error = check_drm_in_content(m3u8_content)
            if drm_error:
                raise Exception(drm_error)
            
            # Save to temp file and use that
            with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u8', delete=False) as f:
                f.write(m3u8_content)
                temp_m3u8 = f.name
            
            try:
                cmd = [
                    "ffmpeg",
                    "-threads", FFMPEG_THREADS,
                    "-i", temp_m3u8,
                    "-c:a", FFMPEG_CODEC,
                    "-b:a", FFMPEG_BITRATE,
                    "-q:a", FFMPEG_QUALITY,
                    "-y",
                    "-loglevel", "error",
                    output_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                # Check for DRM errors in retry attempt
                if stderr:
                    stderr_text = stderr.decode('utf-8', errors='ignore')
                    drm_error = check_drm_in_content(stderr_text)
                    if drm_error:
                        raise Exception(drm_error)
                
                if process.returncode != 0:
                    return False
                
                return True
            finally:
                if os.path.exists(temp_m3u8):
                    os.unlink(temp_m3u8)
        except Exception:
            return False
    
    def _extract_track_metadata(self, track_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from track data."""
        # Safely get user data (handle None case)
        user_data = track_data.get("user") or {}
        
        # Safely get publisher_metadata (handle None case)
        publisher_metadata = track_data.get("publisher_metadata") or {}
        
        return {
            "title": track_data.get("title", "Unknown"),
            "artist": user_data.get("username", "Unknown") if isinstance(user_data, dict) else "Unknown",
            "album": (
                track_data.get("release_title") or
                (publisher_metadata.get("album_title") if isinstance(publisher_metadata, dict) else None)
            ),
            "genre": track_data.get("genre") or track_data.get("tag_list"),
            "artwork_url": (
                track_data.get("artwork_url") or
                (user_data.get("avatar_url") if isinstance(user_data, dict) else None)
            ),
        }
    
    async def download_track(
        self,
        url: str,
        format: str = "mp3",
        attach_metadata: bool = True
    ) -> StreamingResponse:
        """Download a single track with streaming support."""
        if format != "mp3":
            raise ValueError("Only MP3 format is supported")
        
        try:
            # Get full track data for metadata
            track_data = await self.sc_client._resolve_url(url)
            
            # Get stream URL
            stream_info = await self.sc_client.get_stream_url(url)
            m3u8_url = stream_info["m3u8_url"]
            
            # Extract metadata
            metadata = self._extract_track_metadata(track_data)
            
            # Sanitize filename
            filename = f"{metadata['artist']} - {metadata['title']}.mp3"
            filename = sanitize_filename(filename, MAX_FILENAME_LENGTH)
            
            # If metadata is needed, download first then add metadata
            # Otherwise, stream directly from ffmpeg
            if attach_metadata:
                return await self._download_track_with_metadata(
                    m3u8_url, metadata, filename
                )
            else:
                return await self._stream_track_directly(m3u8_url, filename)
                
        except Exception as e:
            raise Exception(f"Track download failed: {str(e)}")
    
    async def _download_track_with_metadata(
        self,
        m3u8_url: str,
        metadata: Dict[str, Any],
        filename: str
    ) -> StreamingResponse:
        """Download track, add metadata, then stream."""
        # Create temp file for output
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Download and convert
            success = await self._download_with_ffmpeg(m3u8_url, output_path)
            
            if not success:
                raise Exception("Failed to download track")
            
            # Validate file size
            file_size = get_file_size(output_path)
            if file_size < MIN_FILE_SIZE:
                raise Exception(
                    f"Downloaded file is too small ({file_size} bytes), "
                    "likely corrupted or incomplete"
                )
            
            # Add metadata
            cover_art = None
            if metadata["artwork_url"]:
                log(f"Downloading cover art for track: {metadata['title']}")
                cover_art = await download_cover_art(
                    self.sc_client.client,
                    metadata["artwork_url"]
                )
            
            log(f"Adding metadata to track: {metadata['title']}")
            add_metadata_to_mp3(
                file_path=output_path,
                title=metadata["title"],
                artist=metadata["artist"],
                album=metadata["album"],
                track_number=1,
                genre=metadata["genre"],
                cover_art=cover_art
            )
            
            # Stream the file
            return self._create_streaming_response(
                output_path,
                filename,
                "audio/mpeg"
            )
            
        except Exception as e:
            # Clean up on error
            if os.path.exists(output_path):
                os.unlink(output_path)
            raise
    
    async def _stream_track_directly(
        self,
        m3u8_url: str,
        filename: str
    ) -> StreamingResponse:
        """Stream ffmpeg output directly to client (no metadata)."""
        async def generate():
            # Start ffmpeg process with stdout piped - optimized for streaming
            cmd = [
                "ffmpeg",
                "-threads", FFMPEG_THREADS,
                "-i", m3u8_url,
                "-c:a", FFMPEG_CODEC,
                "-b:a", FFMPEG_BITRATE,
                "-q:a", FFMPEG_QUALITY,
                "-f", "mp3",  # Force MP3 format
                "-loglevel", "error",
                "-"  # Output to stdout
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # Stream chunks as they come from ffmpeg - use larger chunks for better throughput
                while True:
                    chunk = await process.stdout.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
                
                # Wait for process to complete
                await process.wait()
                
                # Check for errors
                if process.returncode != 0:
                    stderr = await process.stderr.read()
                    error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                    raise Exception(f"FFmpeg conversion failed: {error_msg}")
                    
            except Exception as e:
                # Kill process on error
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass
                raise
        
        return StreamingResponse(
            generate(),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    async def download_playlist(
        self,
        url: str,
        format: str = "mp3",
        attach_metadata: bool = True
    ) -> StreamingResponse:
        """Download all tracks from a playlist/album and return as streaming ZIP."""
        if format != "mp3":
            raise ValueError("Only MP3 format is supported")
        
        try:
            # Get playlist info
            info = await self.sc_client.get_info(url)
            playlist_data = await self.sc_client._resolve_url(url)
            
            tracks = playlist_data.get("tracks", [])
            if not tracks:
                raise Exception("No tracks found in playlist/album")
            
            # Collect all track IDs and fetch full track data in batch
            track_ids = [track.get("id") for track in tracks if track.get("id")]
            full_tracks_data = await self.sc_client._get_tracks_by_ids(track_ids)
            
            # Sanitize ZIP filename
            zip_filename = sanitize_filename(
                f"{info.get('title', 'playlist')}.zip",
                MAX_FILENAME_LENGTH
            )
            
            # Stream ZIP as we download tracks
            return StreamingResponse(
                self._stream_playlist_zip(
                    tracks,
                    full_tracks_data,
                    attach_metadata
                ),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f'attachment; filename="{zip_filename}"'
                }
            )
                
        except Exception as e:
            raise Exception(f"Playlist download failed: {str(e)}")
    
    async def _stream_playlist_zip(
        self,
        tracks: list,
        full_tracks_data: Dict[int, Dict[str, Any]],
        attach_metadata: bool
    ):
        """Stream ZIP file as we download and add tracks concurrently."""
        # Use a temporary file for ZIP to allow incremental writing
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_zip:
            zip_path = tmp_zip.name
        
        total_tracks = len(tracks)
        tracks_added = 0
        last_zip_size = 0
        zip_lock = asyncio.Lock()  # Lock for ZIP file operations
        
        async def download_and_add_track(idx: int, track_data: Dict[str, Any]) -> Optional[tuple]:
            """Download a single track and return its data for ZIP addition."""
            async with self.download_semaphore:  # Limit concurrent downloads
                try:
                    # Download track to memory
                    track_bytes = await self._download_track_to_memory(
                        track_data,
                        full_tracks_data,
                        idx,
                        total_tracks,
                        attach_metadata
                    )
                    
                    if track_bytes:
                        # Get filename for this track
                        metadata = self._extract_track_metadata(
                            full_tracks_data.get(track_data.get("id")) or track_data
                        )
                        filename = f"{metadata['title']} - {metadata['artist']}.mp3"
                        filename = sanitize_filename(filename, MAX_FILENAME_LENGTH)
                        return (idx, filename, track_bytes)
                    return None
                    
                except Exception as e:
                    error_msg = str(e)
                    if "DRM-protected" in error_msg or "cenc" in error_msg.lower():
                        log(f"Skipping track {idx+1}/{total_tracks}: Track is DRM-protected")
                    else:
                        log(f"Failed to download track {idx+1}/{total_tracks}: {error_msg}")
                    return None
        
        try:
            # Create ZIP file with optimized compression
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=ZIP_COMPRESSION_LEVEL, allowZip64=True) as zip_file:
                # Create download tasks for all tracks
                download_tasks = [
                    asyncio.create_task(download_and_add_track(idx, track_data))
                    for idx, track_data in enumerate(tracks)
                ]
                
                # Use a dict to store completed tracks by index
                completed_tracks = {}  # idx -> (filename, track_bytes)
                next_expected_idx = 0
                
                # Process tasks as they complete, maintaining order for ZIP
                for task in asyncio.as_completed(download_tasks):
                    try:
                        result = await task
                        if result:
                            track_idx, filename, track_bytes = result
                            completed_tracks[track_idx] = (filename, track_bytes)
                            
                            # Add tracks to ZIP in order as they become available
                            while next_expected_idx in completed_tracks:
                                filename, track_bytes = completed_tracks.pop(next_expected_idx)
                                
                                async with zip_lock:
                                    zip_file.writestr(filename, track_bytes)
                                    tracks_added += 1
                                    
                                    # Flush to disk
                                    zip_file.fp.flush()
                                    
                                    # Read and yield new data since last read
                                    current_size = os.path.getsize(zip_path)
                                    if current_size > last_zip_size:
                                        with open(zip_path, 'rb') as f:
                                            f.seek(last_zip_size)
                                            new_data = f.read(current_size - last_zip_size)
                                            if new_data:
                                                yield new_data
                                        last_zip_size = current_size
                                
                                next_expected_idx += 1
                                
                                # Small delay to avoid overwhelming the system
                                if next_expected_idx % MAX_CONCURRENT_DOWNLOADS == 0:
                                    await asyncio.sleep(REQUEST_DELAY)
                    except Exception as e:
                        log(f"Error processing download task: {str(e)}")
                        continue
            
            # Close ZIP to write central directory
            # The ZIP file is already closed by context manager, but we need to read final data
            current_size = os.path.getsize(zip_path)
            if current_size > last_zip_size:
                with open(zip_path, 'rb') as f:
                    f.seek(last_zip_size)
                    final_data = f.read()
                    if final_data:
                        yield final_data
            
            if tracks_added == 0:
                raise Exception("No tracks were successfully downloaded")
                
        finally:
            # Clean up temp file
            if os.path.exists(zip_path):
                os.unlink(zip_path)
    
    async def _download_track_to_memory(
        self,
        track_data: Dict[str, Any],
        full_tracks_data: Dict[int, Dict[str, Any]],
        idx: int,
        total_tracks: int,
        attach_metadata: bool
    ) -> Optional[bytes]:
        """Download a track and return as bytes."""
        track_id = track_data.get("id")
        if not track_id:
            return None
        
        # Get track URL
        track_url = self._get_track_url(track_data, full_tracks_data, track_id)
        if not track_url:
            return None
        
        log(f"Downloading track {idx+1}/{total_tracks}: {track_url}")
        
        # Get full track data if not available
        full_track = full_tracks_data.get(track_id)
        if not full_track:
            try:
                full_track = await self.sc_client._resolve_url(track_url)
                if full_track and full_track.get("id") == track_id:
                    full_tracks_data[track_id] = full_track
            except Exception as e:
                log(f"Warning: Could not fetch full track data: {str(e)}")
        
        # Get stream info
        try:
            stream_info = await self.sc_client.get_stream_url(track_url)
            m3u8_url = stream_info["m3u8_url"]
            
            if is_drm_protected_url(m3u8_url):
                return None
        except Exception:
            return None
        
        # Extract metadata
        metadata = self._extract_track_metadata(full_track or track_data)
        
        # Create temp file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            output_path = tmp_file.name
        
        try:
            # Download track
            log(f"Converting track {idx+1}/{total_tracks} to MP3...")
            success = await self._download_with_ffmpeg(m3u8_url, output_path)
            
            if not success or not validate_file_size(output_path, MIN_FILE_SIZE):
                # Try retry once
                if os.path.exists(output_path):
                    os.unlink(output_path)
                success = await self._download_with_ffmpeg(m3u8_url, output_path)
                if not success or not validate_file_size(output_path, MIN_FILE_SIZE):
                    return None
            
            # Add metadata if requested
            if attach_metadata:
                cover_art = None
                if metadata["artwork_url"]:
                    cover_art = await download_cover_art(
                        self.sc_client.client,
                        metadata["artwork_url"]
                    )
                
                add_metadata_to_mp3(
                    file_path=output_path,
                    title=metadata["title"],
                    artist=metadata["artist"],
                    album=metadata["album"],
                    track_number=idx + 1,
                    genre=metadata["genre"],
                    cover_art=cover_art
                )
            
            # Read file into memory
            with open(output_path, "rb") as f:
                track_bytes = f.read()
            
            return track_bytes
            
        finally:
            # Clean up temp file
            if os.path.exists(output_path):
                os.unlink(output_path)
    
    def _get_track_url(
        self,
        track_data: Dict[str, Any],
        full_tracks_data: Dict[int, Dict[str, Any]],
        track_id: int
    ) -> Optional[str]:
        """Get track URL from various sources."""
        # Prefer from full track data
        if track_id in full_tracks_data:
            full_track = full_tracks_data[track_id]
            track_url = full_track.get("permalink_url")
            if track_url:
                return track_url
        
        # Fallback to permalink_url from playlist data
        track_url = track_data.get("permalink_url")
        if track_url:
            return track_url
        
        # Try to get permalink from track data
        permalink = track_data.get("permalink")
        if permalink:
            return f"https://soundcloud.com/{permalink}"
        
        # Last resort: construct URL from ID
        return f"https://soundcloud.com/tracks/{track_id}"
    
    def _create_streaming_response(
        self,
        file_path: str,
        filename: str,
        media_type: str
    ) -> StreamingResponse:
        """Create a streaming response for a file."""
        def generate():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk
            # Clean up
            if os.path.exists(file_path):
                os.unlink(file_path)
        
        return StreamingResponse(
            generate(),
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    