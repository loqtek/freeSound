<p align="center">
  <a href="https://github.com/loqteklabs/freeSound">
   <img src="/public/freesoundLogo.png" alt="logo" width="200"/>
  </a>
</p>

# Welcome To Free Sound
The free, light, self hostable app to download SoundCloud songs as a .mp3

## Features

- 🎵 Download SoundCloud tracks as MP3 files
- 📊 Display track information (title, artist, duration, plays, likes)
- ⚡ Fast HLS stream processing
- 📱 Simple and light design

## Architecture

- **Frontend**: Next.js 16 with TypeScript and Tailwind CSS
- **Backend**: FastAPI with async HTTP client and ffmpeg

## Quick Start
Note: We do not reccommend setting this up public facing. As of now anyone can download songs and there is no authentication method. Please only use on private or properly secured networks.

### Option 1: Docker (Recommended)

The easiest way to run FreeSound is using Docker:

1. **Copy the environment file:**
   ```bash
   cp .env.sample .env
   ```

2. **Edit `.env` file** and configure the settings:
   ```bash
   # Open .env in your editor and update:
   # For local Docker setup (services in same network):
   NEXT_PUBLIC_API_URL=http://backend:8000
   
   # For remote backend (if backend is on different server):
   # NEXT_PUBLIC_API_URL=http://your-server-ip:8000
   
   # For accessing from host machine (if needed):
   # NEXT_PUBLIC_API_URL=http://localhost:8000
   ```
   
   **Note:** The `.env` file is gitignored` and won't be committed to the repository. Only `.env.sample` is tracked.

3. **Build and start all services:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f
   ```

5. **Stop services:**
   ```bash
   docker-compose down
   ```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

See [DOCKER.md](./DOCKER.md) for detailed Docker documentation.

### Option 2: Manual Setup

#### Prerequisites

- Node.js 18+ (or Bun)
- Python 3.8+
- ffmpeg installed on your system

### 1. Install ffmpeg

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html

### 2. Start the Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

The backend will run on `http://localhost:8000`

### 3. Start the Frontend

In a new terminal:

```bash
npm install  # or bun install
npm run dev  # or bun dev
```

The frontend will run on `http://localhost:3000`

### 4. Use the Application

1. Open `http://localhost:3000` in your browser
2. Paste a SoundCloud track URL
3. Click "Download" to get the MP3 file

## Project Structure

```
freeSound/
├── app/                    # Next.js frontend
│   ├── page.tsx            # Main page component
│   ├── layout.tsx          # Root layout
│   └── globals.css         # Global styles
├── backend/                 # FastAPI backend
│   ├── main.py             # FastAPI application
│   ├── soundcloud_client.py # SoundCloud API client
│   ├── downloader.py       # Download and conversion handler
│   ├── config.py           # Configuration settings
│   ├── utils/              # Utility modules
│   └── requirements.txt
└── README.md
```

## How It Works

1. **User Input**: User pastes a SoundCloud URL in the frontend
2. **URL Resolution**: Backend resolves the URL to get track metadata
3. **Stream Extraction**: Backend extracts the HLS (m3u8) stream URL
4. **Direct Download**: Backend uses ffmpeg to download the HLS stream directly and convert to MP3 (handles authentication automatically)
5. **Fallback**: If direct download fails, falls back to segment-by-segment download
6. **Download**: Frontend receives and downloads the MP3 file

## API Endpoints

### Backend (FastAPI)

- `GET /` - Health check
- `GET /health` - Health check with ffmpeg status
- `POST /download?url=<soundcloud_url>&format=mp3` - Download and convert track
- `GET /track-info?url=<soundcloud_url>` - Get track information

### Frontend

- `GET /` - Main application page

## Configuration

### Docker Setup

1. Copy the sample environment file:
   ```bash
   cp .env.sample .env
   ```

2. Edit `.env` and configure:
   - `NEXT_PUBLIC_API_URL`: The backend API URL that the frontend will use
     - For Docker: `http://backend:8000` (uses Docker service name)
     - For remote backend: `http://your-server-ip:8000`
     - For local development: `http://localhost:8000`

### Manual Setup

#### Backend

No configuration needed. The backend automatically extracts client IDs from SoundCloud.

#### Frontend

Create a `.env.local` file (optional):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

If not set, defaults to `http://localhost:8000`

## Development

### Backend Development

```bash
cd backend
python main.py
# or
uvicorn main:app --reload
```

### Frontend Development

```bash
npm run dev
# or
bun run dev
```

## Documentation

- [Backend Documentation](./backend/README.md)

## Troubleshooting

### Backend Issues

- **ffmpeg not found**: Install ffmpeg and ensure it's in your PATH
- **Connection errors**: Check if port 8000 is available
- **SoundCloud API errors**: Some tracks may be private or restricted

### Frontend Issues

- **Cannot connect to backend**: Ensure backend is running on port 8000
- **CORS errors**: Backend CORS is configured to allow all origins in development
- **Download not working**: Check browser console and backend logs

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note:** This project is for educational & learning purposes. Please respect SoundCloud's terms of service and copyright laws.