import Link from "next/link";
import Header from "@/components/Header";
import { Home, Music } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 via-white to-orange-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      <div className="container mx-auto px-4 py-12 max-w-4xl">
        <Header />

        {/* 404 Card */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8 mb-6 text-center">
          <div className="mb-6">
            <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-gradient-to-r from-orange-100 to-orange-200 dark:from-orange-900/30 dark:to-orange-800/30 mb-4">
              <Music className="w-12 h-12 text-orange-600 dark:text-orange-400" />
            </div>
            <h2 className="text-6xl font-bold bg-gradient-to-r from-[#fea049] via-[#cd2b69] to-[#5a4ec5] bg-clip-text text-transparent mb-2">
              404
            </h2>
            <h3 className="text-2xl font-semibold text-gray-800 dark:text-gray-200 mb-2">
              Page Not Found
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              The page you're looking for doesn't exist or has been moved.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link
              href="/"
              className="px-6 py-3 bg-gradient-to-r from-orange-500 to-orange-600 text-white font-semibold rounded-lg hover:from-orange-600 hover:to-orange-700 transition-all duration-200 flex items-center gap-2 shadow-lg hover:shadow-xl"
            >
              <Home className="w-5 h-5" />
              <span>Go Home</span>
            </Link>
          </div>
        </div>

        {/* Helpful Links */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 text-center">
          <p className="text-sm text-blue-800 dark:text-blue-200">
            Looking for something? Try going back to the{" "}
            <Link href="/" className="font-semibold underline hover:text-blue-600 dark:hover:text-blue-300">
              home page
            </Link>{" "}
            to download SoundCloud tracks.
          </p>
        </div>
      </div>
    </div>
  );
}


