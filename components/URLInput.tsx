import { Download, Loader2, CheckCircle2 } from "lucide-react";

interface URLInputProps {
  url: string;
  loading: boolean;
  confirmingDownload: boolean;
  onUrlChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onKeyPress: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onDownload: () => void;
}

export default function URLInput({
  url,
  loading,
  confirmingDownload,
  onUrlChange,
  onKeyPress,
  onDownload,
}: URLInputProps) {
  return (
    <div className="mb-6">
      <label htmlFor="soundcloud-url" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
        SoundCloud URL (Track, Playlist, or Album)
      </label>
      <div className="flex gap-3">
        <input
          id="soundcloud-url"
          type="text"
          value={url}
          onChange={onUrlChange}
          onKeyPress={onKeyPress}
          placeholder="https://soundcloud.com/artist/track or playlist URL"
          className="flex-1 px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500"
          disabled={loading}
        />
        <button
          onClick={onDownload}
          disabled={loading || !url.trim()}
          className="px-8 py-3 bg-gradient-to-r from-orange-500 to-orange-600 text-white font-semibold rounded-lg hover:from-orange-600 hover:to-orange-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Processing...</span>
            </>
          ) : confirmingDownload ? (
            <>
              <CheckCircle2 className="w-5 h-5" />
              <span>Confirm Download</span>
            </>
          ) : (
            <>
              <Download className="w-5 h-5" />
              <span>Download</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

