export interface TrackInfo {
  kind?: string;
  title: string;
  artist: string;
  duration?: number | null;
  description?: string | null;
  artwork_url?: string | null;
  playback_count?: number | null;
  likes_count?: number | null;
  track_count?: number;
  tracks?: Array<{
    title: string;
    artist: string;
    duration: number;
  }>;
}

