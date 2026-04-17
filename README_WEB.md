# MusicLibrary — Audio Asset Manager

**Complete audio management system for video creators and content producers.**

Production-ready web application built with Next.js, React, and Supabase. Manage, search, filter, and export audio files with ease.

## 🎯 Quick Start

### Local Development

```bash
# Clone and install
git clone https://github.com/IsaiahDupree/music-selector.git
cd music-selector
npm install

# Configure environment
cp .env.example .env.local
# Add your Supabase credentials to .env.local

# Start development server
npm run dev

# Visit http://localhost:3000
```

### Deploy to Vercel

1. Push to GitHub
2. Connect to Vercel
3. Add environment variables
4. Deploy!

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions.

## ✨ Features

### 🎵 Audio Management
- Upload audio files (MP3, WAV, AAC, FLAC)
- Automatic metadata extraction
- Cloud storage via Supabase
- Track organization with metadata

### 🔍 Discovery & Search
- Full-text search across titles and artists
- Advanced filtering:
  - By genre, mood, duration, energy level
  - Customizable filter options
- Smart sorting (Recently Added, Title, Artist, Duration)

### 🏷️ Organization
- Custom tagging system
- Create and manage playlists
- Drag-and-drop track ordering
- Tag-based organization

### 💾 Export & Integration
- Export as CSV (for spreadsheets)
- Export as JSON (for backups/integration)
- Individual track downloads
- Batch export capabilities (coming soon)

### 🎮 User Interface
- Beautiful, responsive design
- Grid and list view toggle
- Audio player with controls
- Track detail sidebar
- Real-time upload progress

### 🔐 Security
- Supabase authentication (implementation ready)
- Row-level security (RLS) on all tables
- Secure file storage with signed URLs
- Service role separation

## 📊 Project Status

**66.7% Complete (36/54 features)**

### Completed ✅
- Core API endpoints (upload, search, tracks, filters)
- Database schema and migrations
- React UI components
- Audio player and library view
- Export functionality (CSV, JSON)
- Authentication infrastructure
- Monitoring and error logging
- Documentation and deployment guides

### In Progress 🔄
- Audio metadata extraction (FFmpeg integration)
- Automatic audio classification
- Advanced batch operations
- Additional testing coverage
- Performance optimization

## 🏗️ Architecture

```
┌─────────────────┐
│  Next.js Web    │
│  (React + TS)   │
└────────┬────────┘
         │ API
┌────────▼──────────┐
│   Next.js API     │
│  Route Handlers   │
└────────┬──────────┘
         │ SQL
┌────────▼──────────┐
│    Supabase       │
│  (PostgreSQL)     │
└───────────────────┘
```

## 📚 Documentation

- **[API Reference](./docs/api.md)** — Complete REST API documentation
- **[User Guide](./docs/user-guide.md)** — Feature walkthroughs and usage
- **[Developer Guide](./docs/contributing.md)** — Architecture and contribution
- **[Deployment Guide](./DEPLOYMENT.md)** — Production deployment steps

## 🚀 Getting Started

### 1. Local Setup
```bash
npm install
npm run dev
```

### 2. Configure Database
- Create Supabase project
- Run migrations from `supabase/migrations/`
- Set up storage bucket

### 3. Set Environment Variables
```
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
```

### 4. Test
```bash
npm test
npm run build
```

### 5. Deploy
```bash
vercel --prod
```

## 🔧 Technology Stack

- **Frontend:** React 19, Next.js 16, TypeScript
- **Backend:** Next.js API Routes
- **Database:** PostgreSQL (Supabase)
- **Storage:** Supabase Storage
- **Hosting:** Vercel
- **Auth:** Supabase Auth
- **Testing:** Jest, React Testing Library

## 📖 API Examples

### Upload Audio
```bash
curl -X POST http://localhost:3000/api/upload \
  -F "file=@song.mp3" \
  -F "title=My Song" \
  -F "artist=My Artist" \
  -F "genre=lofi"
```

### Search Tracks
```bash
curl "http://localhost:3000/api/search?q=calm&limit=5"
```

### Filter Tracks
```bash
curl "http://localhost:3000/api/tracks?genre=lofi&mood=calm&minDuration=60"
```

### Export Library
```bash
# CSV
curl "http://localhost:3000/api/export/csv" > library.csv

# JSON
curl "http://localhost:3000/api/export/json" > library.json
```

## 🧪 Testing

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# Type checking
npx tsc --noEmit
```

## 📦 File Structure

```
├── app/                    # Next.js app directory
│   ├── api/               # API route handlers
│   ├── layout.tsx         # Root layout
│   └── page.tsx           # Home page
├── components/            # React components
├── lib/                   # Utilities
├── utils/                 # Helpers
├── supabase/
│   └── migrations/        # Database schemas
├── docs/                  # Documentation
├── __tests__/             # Tests
└── public/                # Static assets
```

## 🤝 Contributing

See [CONTRIBUTING.md](./docs/contributing.md) for:
- Development setup
- Code style guidelines
- Architecture overview
- How to add features

## 🐛 Known Limitations

- Audio metadata extraction requires FFmpeg setup
- Automatic classification needs ML model setup
- Batch operations have file size limitations
- Real-time collaboration not yet implemented

## 🗺️ Roadmap

### Next Phase (Q2 2026)
- [ ] Audio metadata extraction with FFmpeg
- [ ] Automatic genre/mood classification
- [ ] Advanced batch operations
- [ ] Team collaboration features

### Future (Q3+ 2026)
- [ ] Mobile app (React Native)
- [ ] Desktop application (Electron)
- [ ] Direct Remotion/FFmpeg integration
- [ ] AI-powered recommendations

## 📄 License

MIT License — see [LICENSE](./LICENSE) file

## 🤔 Support

### Resources
- [GitHub Issues](https://github.com/IsaiahDupree/music-selector/issues)
- [API Documentation](./docs/api.md)
- [User Guide](./docs/user-guide.md)
- [Deployment Guide](./DEPLOYMENT.md)

### Getting Help
1. Check documentation
2. Search existing issues
3. Open new issue with details

## 👏 Credits

Built with ❤️ for content creators

**Technologies:**
- [Next.js](https://nextjs.org)
- [React](https://react.dev)
- [Supabase](https://supabase.com)
- [Vercel](https://vercel.com)

---

**[Deploy Now](./DEPLOYMENT.md)** | **[API Docs](./docs/api.md)** | **[User Guide](./docs/user-guide.md)**
