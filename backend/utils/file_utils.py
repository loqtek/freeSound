"""File utility functions."""

import re
import os
from typing import Optional


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """Sanitize a filename by removing invalid characters and limiting length."""
    # Remove invalid filesystem characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # Limit length
    return sanitized[:max_length]


def validate_file_size(file_path: str, min_size: int = 1024) -> bool:
    """Validate that a file exists and meets minimum size requirements."""
    if not os.path.exists(file_path):
        return False
    
    file_size = os.path.getsize(file_path)
    return file_size >= min_size


def get_file_size(file_path: str) -> int:
    """Get file size in bytes, or 0 if file doesn't exist."""
    if not os.path.exists(file_path):
        return 0
    return os.path.getsize(file_path)

