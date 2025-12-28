import { Info } from "lucide-react";

export default function InfoCard() {
  return (
    <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
      <div className="flex items-start gap-3">
        <Info className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800 dark:text-blue-200">
          <p className="font-medium mb-1">How to use:</p>
          <ol className="list-decimal list-inside space-y-1 text-blue-700 dark:text-blue-300">
            <li>Copy a SoundCloud track, playlist, or album URL</li>
            <li>Paste it in the input field above</li>
            <li>For playlists/albums, check &quot;Download all tracks&quot; to get a ZIP file</li>
            <li>Click Download to get the MP3 file(s)</li>
          </ol>
          <p className="font-medium mt-4">Note: Large playlists or long songs may take some time, please wait for the download popup OR a error message.</p>
        </div>
      </div>
    </div>
  );
}

