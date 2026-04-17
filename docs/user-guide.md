# MusicLibrary User Guide

## Getting Started

MusicLibrary is a complete audio asset manager designed for video creators, content producers, and music curators. It helps you organize, search, and export audio files efficiently.

## Installation

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/IsaiahDupree/music-selector.git
cd music-selector
```

2. Install dependencies:
```bash
npm install
```

3. Set up environment variables:
```bash
cp .env.example .env.local
```

4. Add your Supabase credentials to `.env.local`:
```
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

5. Start the development server:
```bash
npm run dev
```

6. Open [http://localhost:3000](http://localhost:3000)

### Deployment to Vercel

1. Push your code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Click "New Project" and import your repository
4. Add environment variables in project settings
5. Deploy!

## Features

### Uploading Audio Files

1. Click **"Upload Audio"** button at the top
2. Select an audio file (MP3, WAV, AAC, or FLAC)
3. (Optional) Add title, artist, and genre
4. Click **"Upload"**

**Supported formats:**
- MP3
- WAV
- AAC
- FLAC

**File size:** Max 100 MB

### Browsing Your Library

The main page displays all your uploaded tracks in a grid or list view.

**Toggle between views:**
- Click **"Grid"** for card view
- Click **"List"** for detailed list

**Sort tracks by:**
- Recently Added
- Title
- Artist
- Duration

### Filtering Tracks

Use the filter dropdowns to narrow down results:

**By Genre:**
- Lo-fi
- Electronic
- House
- Hip Hop
- Cinematic
- Pop
- Ambient

**By Mood:**
- Calm
- Energetic
- Happy
- Inspiring
- Dramatic

**By Duration:**
Use the track card or API filters to find tracks by length.

### Viewing Track Details

Click on any track to view its full details in the sidebar:
- Title
- Artist
- Genre
- Mood
- Duration
- Energy level

### Creating Tags

Organize your tracks with custom tags:
1. (Future feature) Click "Add Tag"
2. Enter a tag name
3. Tags are searchable and filterable

### Creating Playlists

Group related tracks into playlists:
1. Click "Create Playlist"
2. Name your playlist
3. Add tracks by dragging or selecting
4. Playlists maintain track order for sequential playback

### Exporting Your Library

**Export options:**

**CSV Export:**
- Contains: Title, Artist, Genre, Mood, Energy, Duration, etc.
- Use for: Spreadsheet analysis, data backup

**JSON Export:**
- Contains: Complete track data with all metadata
- Use for: Backup, reimport, sharing with team

**Download specific tracks:**
1. Click on a track
2. Click "Download"
3. File downloads in original format

## Tips & Tricks

### Organizing Your Library

- Use consistent naming for artist names
- Assign genres carefully - it helps with searching
- Add mood tags to help with video matching

### Finding Tracks Faster

- Use the search bar for quick title/artist lookups
- Filter by genre and mood first, then duration
- Create playlists for common projects (e.g., "YouTube Videos", "TikToks")

### Best Practices

- Keep file sizes under 50 MB for faster uploads
- Use descriptive titles (include artist name in title)
- Set the correct genre - it helps with recommendations
- Tag tracks with moods that match their sound

## Troubleshooting

### Upload fails

**"File size exceeds limit"**
- Your file is larger than 100 MB
- Try compressing or splitting the audio

**"Unsupported format"**
- Only MP3, WAV, AAC, and FLAC are supported
- Convert your file using a tool like [CloudConvert](https://cloudconvert.com/)

### Can't find tracks

- Use the search bar (minimum 2 characters)
- Try different genre or mood filters
- Clear filters to see all tracks

### Export not working

- Check your internet connection
- Try a smaller export (fewer tracks)
- Contact support if the issue persists

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd + K` | Search (coming soon) |
| `Ctrl/Cmd + U` | Upload (coming soon) |

## API Integration

Power users can integrate with the REST API:

```bash
# Search for tracks
curl "http://localhost:3000/api/search?q=calm"

# Get all tracks
curl "http://localhost:3000/api/tracks"

# Upload a track
curl -X POST http://localhost:3000/api/upload \
  -F "file=@song.mp3" \
  -F "title=My Song"
```

See [API Documentation](./api.md) for complete endpoint reference.

## Support

For issues or feature requests, visit [GitHub Issues](https://github.com/IsaiahDupree/music-selector/issues)

## License

MIT License - see LICENSE file for details
