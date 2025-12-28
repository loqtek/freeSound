"""FreeSound API - FastAPI application for downloading SoundCloud tracks."""

import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import subprocess

from soundcloud_client import SoundCloudClient
from downloader import SoundCloudDownloader
from utils.access_logger import AccessLoggerMiddleware
import config

app = FastAPI(title="FreeSound API", version="1.0.0")

# Access logging middleware (before CORS to log all requests)
app.add_middleware(AccessLoggerMiddleware)

# CORS middleware

cors_origins = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
sc_client = SoundCloudClient()
downloader = SoundCloudDownloader()


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "FreeSound API", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        ffmpeg_available = result.returncode == 0
    except Exception:
        ffmpeg_available = False
    
    return {
        "status": "healthy",
        "ffmpeg_available": ffmpeg_available
    }


@app.get("/track-info")
async def get_track_info(url: str = Query(..., description="SoundCloud URL")):
    """Get track/playlist/album information."""
    try:
        info = await sc_client.get_info(url)
        return JSONResponse(content=info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/download")
async def download_media(
    url: str = Query(..., description="SoundCloud URL"),
    format: str = Query("mp3", description="Output format (mp3)"),
    download_all: bool = Query(False, description="Download all tracks from playlist/album"),
    attach_metadata: bool = Query(True, description="Attach metadata to downloaded files")
):
    """Download track, playlist, or album as MP3."""
    try:
        # Get media info first
        info = await sc_client.get_info(url)
        kind = info.get("kind", "track")
        
        # Handle single track
        if kind == "track":
            return await downloader.download_track(url, format, attach_metadata)
        
        # Handle playlist/album - always download as ZIP
        elif kind in ["playlist", "album"]:
            return await downloader.download_playlist(url, format, attach_metadata)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported media type: {kind}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
