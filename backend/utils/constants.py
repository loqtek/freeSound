"""Constants used across the backend."""

# File size validation
MIN_FILE_SIZE = 10 * 1024  # 10KB minimum for MP3 files
MIN_FILE_SIZE_WARNING = 1024  # 1KB warning threshold

# FFmpeg settings - optimized for speed and quality balance
FFMPEG_BITRATE = "192k"
FFMPEG_CODEC = "libmp3lame"
# Additional FFmpeg optimizations for faster encoding
FFMPEG_THREADS = "0"  # Use all available CPU cores
FFMPEG_QUALITY = "2"  # Fast encoding preset (0=best quality/slowest, 7=fastest/lower quality)

# API settings
BATCH_SIZE = 50  # SoundCloud API limit for batch requests
REQUEST_DELAY = 0.1  # Reduced delay - we use semaphore for rate limiting instead

# Concurrency settings
MAX_CONCURRENT_DOWNLOADS = 3  # Max concurrent track downloads (prevents resource exhaustion)
MAX_CONCURRENT_FFMPEG = 2  # Max concurrent ffmpeg processes (CPU-bound, limit more strictly)
MAX_CONCURRENT_REQUESTS = 10  # Max concurrent HTTP requests

# ZIP compression settings
ZIP_COMPRESSION_LEVEL = 6  # Balance between speed and compression (0=no compression, 9=max compression)
# ZIP_COMPRESSION_METHOD = zipfile.ZIP_DEFLATED  # Use zipfile.ZIP_DEFLATED directly where needed

# Streaming settings
STREAM_CHUNK_SIZE = 64 * 1024  # 64KB chunks for better throughput
BUFFER_SIZE = 128 * 1024  # 128KB buffer size

# HTTP client settings
HTTP_TIMEOUT = 120.0  # Increased timeout for large downloads
HTTP_MAX_CONNECTIONS = 20  # Connection pool size
HTTP_MAX_KEEPALIVE_CONNECTIONS = 10  # Keep-alive connections

# Filename limits
MAX_FILENAME_LENGTH = 200

