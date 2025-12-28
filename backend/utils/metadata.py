"""MP3 metadata handling utilities."""

import os
from typing import Optional
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TCON, APIC, ID3NoHeaderError


def add_metadata_to_mp3(
    file_path: str,
    title: str,
    artist: str,
    album: Optional[str] = None,
    track_number: Optional[int] = None,
    genre: Optional[str] = None,
    cover_art: Optional[bytes] = None
) -> None:
    """
    Add metadata to MP3 file using mutagen.
    Uses ID3v2.3 for maximum Windows compatibility.
    """
    try:
        # Load or create ID3 tags
        try:
            audio = MP3(file_path, ID3=ID3)
        except ID3NoHeaderError:
            audio = MP3(file_path)
            audio.add_tags(ID3=ID3)
        
        if audio.tags is None:
            audio.add_tags(ID3=ID3)
        
        # Set basic text tags using ID3v2.3 compatible encoding (UTF-8)
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        
        if album:
            audio.tags.add(TALB(encoding=3, text=album))
        
        if track_number:
            audio.tags.add(TRCK(encoding=3, text=str(track_number)))
        
        if genre:
            # Handle genre - take the first tag if multiple
            genre_str = genre.split()[0] if isinstance(genre, str) else str(genre)
            audio.tags.add(TCON(encoding=3, text=genre_str))
        
        # Add cover art if provided
        if cover_art:
            _add_cover_art(audio, cover_art)
        
        # Save with ID3v2.3 for maximum Windows compatibility
        audio.save(v2_version=3)
        
        # Verify the file still exists and has content
        if not os.path.exists(file_path):
            raise Exception("File does not exist after save")
            
    except Exception as e:
        # Log error but don't fail the download if metadata fails
        print(f"Failed to add metadata: {str(e)}")
        raise


def _add_cover_art(audio: MP3, cover_art: bytes) -> None:
    """Add cover art to MP3 file."""
    try:
        # Remove existing APIC frames
        audio.tags.delall("APIC")
        
        # Determine MIME type from image data
        mime = _detect_image_mime(cover_art)
        
        # Create APIC frame with encoding 0 (ISO-8859-1) for better Windows compatibility
        apic_frame = APIC(
            encoding=0,  # ISO-8859-1 (better Windows compatibility)
            mime=mime,
            type=3,  # Cover (front)
            desc="",  # Empty string - many Windows players prefer this
            data=cover_art
        )
        
        # Add the APIC frame
        audio.tags.add(apic_frame)
        
        # Verify it was added
        apic_frames = audio.tags.getall("APIC")
        if not apic_frames:
            print("WARNING: APIC frame was not added!")
            
    except Exception as e:
        print(f"Error adding cover art to MP3: {str(e)}")
        raise


def _detect_image_mime(image_data: bytes) -> str:
    """Detect MIME type from image data."""
    if image_data.startswith(b'\x89PNG'):
        return "image/png"
    elif image_data.startswith(b'GIF'):
        return "image/gif"
    elif image_data.startswith(b'\xff\xd8'):
        return "image/jpeg"
    else:
        return "image/jpeg"  # Default to JPEG

