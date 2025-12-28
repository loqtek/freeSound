import Image from "next/image";

export default function Header() {
  return (
    <div className="text-center mb-12">
      <div className="flex items-center justify-center mb-1">
        <Image
          src="/freesoundLogo.png"
          alt="FreeSound Logo"
          width={260}
          height={260}
          className="w-38 h-28"
          priority
        />
        <h1 className="text-5xl font-bold bg-gradient-to-r from-[#fea049] via-[#cd2b69] to-[#5a4ec5] bg-clip-text text-transparent">
          FreeSound
        </h1>
      </div>
      <p className="text-gray-600 dark:text-gray-400 text-lg">
        Download SoundCloud tracks, albums, and playlists as zip files with mp3 metadata.
      </p>
    </div>
  );
}

