import { useState } from "react";
import { TrackInfo } from "@/types/track";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function useTrackInfo() {
  const [trackInfo, setTrackInfo] = useState<TrackInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTrackInfo = async (soundcloudUrl: string): Promise<TrackInfo | null> => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(
        `${API_BASE_URL}/track-info?url=${encodeURIComponent(soundcloudUrl)}`
      );
      if (!response.ok) {
        throw new Error("Failed to fetch track info");
      }
      const data = await response.json();
      setTrackInfo(data);
      setError(null);
      return data;
    } catch (err) {
      console.error("Error fetching track info:", err);
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch track info";
      setError(errorMessage);
      setTrackInfo(null);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const clearTrackInfo = () => {
    setTrackInfo(null);
    setError(null);
  };

  return {
    trackInfo,
    loading,
    error,
    fetchTrackInfo,
    clearTrackInfo,
  };
}

