"use client";

import { useState } from "react";
import { useTrackInfo } from "@/hooks/useTrackInfo";
import { useDownload } from "@/hooks/useDownload";
import Header from "@/components/Header";
import URLInput from "@/components/URLInput";
import StatusMessage from "@/components/StatusMessage";
import TrackInfo from "@/components/TrackInfo";
import InfoCard from "@/components/InfoCard";

export default function Home() {
  const [url, setUrl] = useState("");
  const { trackInfo, loading: trackInfoLoading, error: trackInfoError, fetchTrackInfo, clearTrackInfo } = useTrackInfo();
  const {
    loading: downloadLoading,
    error: downloadError,
    success,
    status,
    attachMetadata,
    confirmingDownload,
    setAttachMetadata,
    setConfirmingDownload,
    setError: setDownloadError,
    downloadTrack,
    resetDownload,
  } = useDownload();

  const loading = trackInfoLoading || downloadLoading;
  const error = trackInfoError || downloadError;

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value);
    clearTrackInfo();
    resetDownload();
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !loading) {
      handleDownload();
    }
  };

  const handleDownload = async () => {
    // Validate URL first
    if (!url.trim()) {
      setDownloadError("Please enter a SoundCloud URL");
      return;
    }

    if (!url.includes("soundcloud.com")) {
      setDownloadError("Please enter a valid SoundCloud URL");
      return;
    }

    // If not in confirmation mode, fetch track info and enter confirmation mode
    if (!confirmingDownload) {
        const fetchedTrackInfo = await fetchTrackInfo(url);
        if (fetchedTrackInfo) {
          setConfirmingDownload(true);
      }
      return;
    }

    // Confirmation mode - actually perform the download
    await downloadTrack(url, trackInfo);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-orange-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <Header />

        {/* Main Card */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 mb-6">
          <URLInput
            url={url}
            loading={loading}
            confirmingDownload={confirmingDownload}
            onUrlChange={handleUrlChange}
                onKeyPress={handleKeyPress}
            onDownload={handleDownload}
          />

          <StatusMessage status={status} error={error} success={success} />

          {trackInfo && (
            <TrackInfo
              trackInfo={trackInfo}
              confirmingDownload={confirmingDownload}
              attachMetadata={attachMetadata}
              onCancel={() => {
                          setConfirmingDownload(false);
                resetDownload();
              }}
              onAttachMetadataChange={setAttachMetadata}
            />
          )}
        </div>

        <InfoCard />
      </div>
    </div>
  );
}
