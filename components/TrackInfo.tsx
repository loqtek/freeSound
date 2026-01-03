import Image from "next/image";
import { Music, X } from "lucide-react";
import { TrackInfo as TrackInfoType } from "@/types/track";

interface TrackInfoProps {
  trackInfo: TrackInfoType;
  confirmingDownload: boolean;
  attachMetadata: boolean;
  onCancel: () => void;
  onAttachMetadataChange: (checked: boolean) => void;
}

export default function TrackInfo({
  trackInfo,
  confirmingDownload,
  attachMetadata,
  onCancel,
  onAttachMetadataChange,
}: TrackInfoProps) {
  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-700/50 rounded-lg border border-gray-200 dark:border-gray-600">
      <div className="flex items-start gap-4">
        {trackInfo.artwork_url && (
          <Image
            src={trackInfo.artwork_url}
            alt={trackInfo.title}
            width={96}
            height={96}
            className="w-24 h-24 rounded-lg object-cover"
            unoptimized
          />
        )}
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {trackInfo.title}
              </h3>
              {trackInfo.kind && (
                <span className="px-2 py-0.5 text-xs font-medium bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 rounded">
                  {trackInfo.kind}
                </span>
              )}
            </div>
            {confirmingDownload && (
              <button
                onClick={onCancel}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                title="Cancel"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
            by {trackInfo.artist}
          </p>
          <div className="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400">
            {trackInfo.duration && (
              <span className="flex items-center gap-1">
                <Music className="w-3 h-3" />
                {formatDuration(trackInfo.duration)}
              </span>
            )}
            {trackInfo.track_count !== undefined && (
              <span>🎵 {trackInfo.track_count} tracks</span>
            )}
            {trackInfo.playback_count !== undefined && trackInfo.playback_count !== null && (
              <span>👁 {trackInfo.playback_count.toLocaleString()} plays</span>
            )}
            {trackInfo.likes_count !== undefined && trackInfo.likes_count !== null && (
              <span>❤️ {trackInfo.likes_count.toLocaleString()} likes</span>
            )}
          </div>
          {trackInfo.description && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-3 line-clamp-2">
              {trackInfo.description}
            </p>
          )}
          {/* Download options - shown when confirming */}
          {confirmingDownload && (
            <div className="mt-4 space-y-3 p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-600">
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Download Options:
              </p>
              {/* Show info for playlists/albums */}
              {trackInfo.kind && ["playlist", "album"].includes(trackInfo.kind) && (
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  This {trackInfo.kind} will be downloaded as a ZIP file with all {trackInfo.track_count || 0} tracks.
                </p>
              )}
              {/* Attach metadata checkbox */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="attach-metadata"
                  checked={attachMetadata}
                  onChange={(e) => onAttachMetadataChange(e.target.checked)}
                  className="w-4 h-4 text-orange-600 border-gray-300 rounded focus:ring-orange-500"
                />
                <label htmlFor="attach-metadata" className="text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
                  Attach song metadata (title, artist, album, genre, cover art)
                </label>
              </div>
            </div>
          )}
          {/* Track list preview for playlists */}
          {trackInfo.tracks && trackInfo.tracks.length > 0 && (
            <div className="mt-4 max-h-64 overflow-y-auto">
              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                Tracks ({trackInfo.track_count || trackInfo.tracks.length} total):
              </p>
              <ul className="space-y-1">
                {trackInfo.tracks.map((track, idx) => (
                  <li key={idx} className="text-xs text-gray-600 dark:text-gray-400">
                    {idx + 1}. {track.title} - {track.artist}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

