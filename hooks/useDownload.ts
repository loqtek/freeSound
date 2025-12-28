import { useState } from "react";
import { TrackInfo } from "@/types/track";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useDownload() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [attachMetadata, setAttachMetadata] = useState(true);
  const [confirmingDownload, setConfirmingDownload] = useState(false);

  const sanitizeFilename = (name: string) => {
    return name
      .replace(/[<>:"/\\|?*]/g, '') // Remove invalid filesystem characters
      .replace(/\s+/g, ' ') // Replace multiple spaces with single space
      .substring(0, 120); // Limit length
  };

  const downloadTrack = async (url: string, trackInfo: TrackInfo | null) => {
    if (!url.trim()) {
      setError("Please enter a SoundCloud URL");
      return;
    }

    // Validate URL
    if (!url.includes("soundcloud.com")) {
      setError("Please enter a valid SoundCloud URL");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);
    setStatus("Downloading and converting...");

    try {
      // Check if it's a playlist/album
      const isPlaylistOrAlbum = trackInfo?.kind && ["playlist", "album"].includes(trackInfo.kind);
      
      // Always download playlists/albums as ZIP
      const shouldDownloadAll = isPlaylistOrAlbum;
      // Always send attach_metadata parameter (backend defaults to true if not provided)
      const apiUrl = `${API_BASE_URL}/download?url=${encodeURIComponent(url)}&format=mp3${shouldDownloadAll ? "&download_all=true" : ""}&attach_metadata=${attachMetadata}`;
      
      // Download the track/playlist
      const response = await fetch(apiUrl, {
        method: "POST",
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || "Failed to download track");
      }

      // Get the filename from trackInfo, Content-Disposition header, or use default
      const contentDisposition = response.headers.get("content-disposition");
      const contentType = response.headers.get("content-type");
      const isZip = contentType?.includes("application/zip");
      
      let filename = isZip ? `playlist.zip` : `track.mp3`;
      // Prefer track/playlist title from trackInfo if available
      if (trackInfo?.title) {
        filename = `${sanitizeFilename(trackInfo.title)}${isZip ? ".zip" : ".mp3"}`;
      } else if (contentDisposition) {
        // Fallback to Content-Disposition header
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/i);
        if (filenameMatch) {
          filename = filenameMatch[1].replace(/['"]/g, ''); // Remove quotes
        }
      }

      // Create blob and download
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      document.body.removeChild(a);

      setSuccess(true);
      setStatus("Download complete!");
      setConfirmingDownload(false);
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        setSuccess(false);
        setStatus("");
      }, 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setStatus("");
    } finally {
      setLoading(false);
    }
  };

  const resetDownload = () => {
    setError(null);
    setSuccess(false);
    setStatus("");
    setConfirmingDownload(false);
  };

  return {
    loading,
    error,
    success,
    status,
    attachMetadata,
    confirmingDownload,
    setAttachMetadata,
    setConfirmingDownload,
    setError,
    downloadTrack,
    resetDownload,
  };
}

