"""Configuration settings for the application."""

import os
from pathlib import Path

# Logs directory - defaults to ./logs if not set
LOGS_DIR = os.getenv("LOGS_DIR", str(Path(__file__).parent / "logs"))

# Ensure logs directory exists
os.makedirs(LOGS_DIR, exist_ok=True)

# Log file paths
ACCESS_LOG_FILE = os.path.join(LOGS_DIR, "access.log")
DOWNLOAD_LOG_FILE = os.path.join(LOGS_DIR, "download.log")

