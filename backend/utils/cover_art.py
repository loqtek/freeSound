"""Cover art downloading utilities."""

from typing import Optional
import httpx


async def download_cover_art(
    client: httpx.AsyncClient,
    artwork_url: Optional[str]
) -> Optional[bytes]:
    """
    Download cover art image from SoundCloud.
    Tries multiple URL variations to find a working image.
    """
    if not artwork_url:
        return None
    
    try:
        # Try the original URL first
        try:
            response = await client.get(artwork_url)
            if response.status_code == 200:
                image_data = response.content
                if _is_valid_image(image_data):
                    return image_data
        except Exception:
            pass
        
        # Try URL variations with different sizes
        variations = [
            artwork_url.replace("-large", "-t500x500"),
            artwork_url.replace("-t67x67", "-t500x500"),
            artwork_url.replace("-t124x124", "-t500x500"),
            artwork_url.replace("-t300x300", "-t500x500"),
        ]
        
        for variant_url in variations:
            if variant_url != artwork_url:
                try:
                    response = await client.get(variant_url)
                    if response.status_code == 200:
                        image_data = response.content
                        if _is_valid_image(image_data):
                            return image_data
                except Exception:
                    continue
        
        return None
        
    except Exception:
        return None


def _is_valid_image(image_data: bytes) -> bool:
    """Check if bytes represent valid image data."""
    if len(image_data) < 100:
        return False
    
    # Check for common image file signatures
    return (
        image_data.startswith(b'\xff\xd8') or  # JPEG
        image_data.startswith(b'\x89PNG') or    # PNG
        image_data.startswith(b'GIF')           # GIF
    )

