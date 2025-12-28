"""DRM detection utilities."""

from typing import Optional


def is_drm_protected_url(url: str) -> bool:
    """Check if a URL indicates DRM protection."""
    url_lower = url.lower()
    return "cenc" in url_lower or "/cenc/" in url_lower


def check_drm_in_content(content: str) -> Optional[str]:
    """
    Check content for DRM indicators.
    Returns error message if DRM detected, None otherwise.
    """
    content_lower = content.lower()
    
    # Check for various DRM indicators
    if "cenc" in content_lower or "/cenc/" in content_lower:
        return "Track is DRM-protected (encrypted) and cannot be downloaded"
    
    if "not on whitelist" in content_lower and "https" in content_lower:
        return "Track is DRM-protected (encrypted) and cannot be downloaded"
    
    if "data:text" in content_lower and "wrmheader" in content_lower:
        return "Track is DRM-protected (encrypted) and cannot be downloaded"
    
    return None

