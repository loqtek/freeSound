"""Simple logging utility for application logs."""

from datetime import datetime
from zoneinfo import ZoneInfo
from config import DOWNLOAD_LOG_FILE


def get_est_timestamp() -> str:
    """Get current timestamp in EST/EDT format."""
    utc_time = datetime.now(ZoneInfo("UTC"))
    est_time = utc_time.astimezone(ZoneInfo("America/New_York"))
    return est_time.strftime("%Y-%m-%d %H:%M:%S %Z")


def log_to_file(message: str, log_file: str = DOWNLOAD_LOG_FILE):
    """Write message to log file with timestamp."""
    try:
        timestamp = get_est_timestamp()
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        # Don't fail if logging fails
        print(f"Failed to write to log file: {str(e)}")


def log(message: str, log_file: str = DOWNLOAD_LOG_FILE):
    """Log message to both console and file."""
    print(message)
    log_to_file(message, log_file)

