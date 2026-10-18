# Developer Guide — MusicLibrary

## Architecture Overview

MusicLibrary is built as a modern web application with the following architecture:

```
┌─────────────────┐
│  Next.js Web UI │
│  (React, TypeScript)
└────────┬────────┘
         │ API calls
┌────────▼──────────┐
│   Next.js API     │
│   (Route Handlers)│
└────────┬──────────┘
         │ SQL queries
┌────────▼──────────┐
│    Supabase       │
│  (PostgreSQL DB)  │
└───────────────────┘
```

## Project Structure

```
music-library/
├── app/                          # Next.js app directory
│   ├── api/                      # API route handlers
│   │   ├── health/               # Health check endpoint
│   │   ├── upload/               # File upload endpoint
│   │   ├── tracks/               # Track CRUD endpoints
│   │   ├── search/               # Search endpoint
│   │   ├── filters/              # Filter options endpoint
│   │   ├── tags/                 # Tag management endpoints
│   │   ├── playlists/            # Playlist endpoints
│   │   └── export/               # Export endpoints (CSV, JSON)
│   ├── layout.tsx                # Root layout
│   └── page.tsx                  # Home page
├── components/                   # React components
│   ├── AudioPlayer.tsx           # Audio player component
│   ├── TrackCard.tsx             # Track display card
│   ├── LibraryView.tsx           # Main library view
│   └── Waveform.tsx              # Audio waveform visualization
├── lib/                          # Utilities and helpers
│   ├── supabase.ts               # Supabase client configuration
│   └── supabase-storage.ts       # Storage operations
├── utils/                        # General utilities
│   └── audio-validation.ts       # File validation
├── supabase/
│   └── migrations/               # Database migrations
├── docs/                         # Documentation
│   ├── api.md                    # API reference
│   ├── user-guide.md             # User documentation
│   └── contributing.md           # This file
├── public/                       # Static assets
├── tsconfig.json                 # TypeScript configuration
├── next.config.js                # Next.js configuration
├── vercel.json                   # Vercel deployment config
└── package.json                  # Dependencies
```

## Technology Stack

- **Frontend:** React 19, Next.js 16, TypeScript
- **Backend:** Next.js API Routes
- **Database:** PostgreSQL (via Supabase)
- **Storage:** Supabase Storage (cloud file hosting)
- **Deployment:** Vercel
- **Authentication:** Supabase Auth (future)

## Setup for Development

### 1. Prerequisites

- Node.js 18+ and npm
- Supabase account (free tier available at supabase.com)
- Git

### 2. Clone and Install

```bash
git clone https://github.com/IsaiahDupree/music-selector.git
cd music-selector
npm install
```

### 3. Environment Setup

Create `.env.local`:

```bash
cp .env.example .env.local
```

Fill in your Supabase credentials:
- Get `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` from Supabase project settings
- Get `SUPABASE_SERVICE_ROLE_KEY` from Settings → API Keys

### 4. Database Setup

Create the database tables:

```bash
# Using Supabase CLI
npx supabase db push
```

Or manually run migrations in Supabase SQL editor:
1. Go to your Supabase project
2. SQL Editor
3. Copy content from `supabase/migrations/001_create_tracks_table.sql`
4. Paste and execute
5. Repeat for all migration files

### 5. Start Development

```bash
npm run dev
```

Visit http://localhost:3000

## Code Style

### TypeScript

- Always use explicit types
- Avoid `any` type
- Use interfaces for component props

```typescript
// Good
interface TrackCardProps {
  id: string;
  title: string;
  onSelect?: (id: string) => void;
}

// Avoid
interface TrackCardProps {
  props: any;
}
```

### Component Naming

- Use PascalCase for components: `AudioPlayer.tsx`
- Use camelCase for utilities: `audio-validation.ts`
- Name exports after the file: `export default function AudioPlayer()`

### API Route Naming

- Use RESTful conventions: `/api/tracks`, `/api/tracks/{id}`
- Use HTTP methods correctly: GET (read), POST (create), PUT (update), DELETE (delete)

## Adding a New Feature

### 1. Plan the Database Changes

If your feature needs data storage:
- Create a new migration in `supabase/migrations/`
- Follow naming: `NNN_feature_name.sql`
- Include RLS policies for security

```sql
-- Example migration
CREATE TABLE feature_table (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 2. Create API Endpoints

Create route handlers in `app/api/`:

```typescript
// app/api/feature/route.ts
import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  try {
    // Fetch data
    const { data, error } = await supabaseAdmin
      .from("feature_table")
      .select("*");

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 400 });
    }

    return NextResponse.json({ data });
  } catch (error) {
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
```

### 3. Build React Components

Create components in `components/`:

```typescript
// components/FeatureComponent.tsx
"use client";

import { useEffect, useState } from "react";

export default function FeatureComponent() {
  const [data, setData] = useState(null);

  useEffect(() => {
    fetch("/api/feature")
      .then(r => r.json())
      .then(d => setData(d));
  }, []);

  return <div>{/* Component JSX */}</div>;
}
```

### 4. Integrate and Test

- Add to main page or route
- Test locally with `npm run dev`
- Check TypeScript: `npx tsc --noEmit`
- Test API: `curl http://localhost:3000/api/feature`

### 5. Document Changes

- Update API docs in `docs/api.md`
- Update user guide if user-facing
- Add comments for complex logic

## Database Queries

### Good Practices

```typescript
// ✅ Use parameterized queries
const { data, error } = await supabaseAdmin
  .from("tracks")
  .select("*")
  .eq("id", trackId);

// ❌ Avoid string concatenation
const query = `SELECT * FROM tracks WHERE id = '${trackId}'`;
```

### Common Patterns

```typescript
// Select all
const { data } = await supabaseAdmin.from("tracks").select("*");

// With filters
const { data } = await supabaseAdmin
  .from("tracks")
  .select("*")
  .eq("genre", "lofi")
  .gte("energy_level", 0.5);

// With pagination
const { data, count } = await supabaseAdmin
  .from("tracks")
  .select("*", { count: "exact" })
  .range(0, 19);

// Insert
const { data } = await supabaseAdmin
  .from("tracks")
  .insert({ title: "...", artist: "..." })
  .select()
  .single();

// Update
const { data } = await supabaseAdmin
  .from("tracks")
  .update({ title: "New Title" })
  .eq("id", trackId)
  .select()
  .single();

// Delete
await supabaseAdmin.from("tracks").delete().eq("id", trackId);
```

## Error Handling

- Always validate input
- Return appropriate HTTP status codes
- Never expose sensitive information in errors
- Log errors for debugging

```typescript
// Good error handling
if (!file) {
  return NextResponse.json(
    { error: "No file provided" },
    { status: 400 }
  );
}

try {
  // operation
} catch (error) {
  console.error("Operation failed:", error);
  return NextResponse.json(
    { error: "Internal server error" },
    { status: 500 }
  );
}
```

## Testing

```bash
# Run tests (when available)
npm test

# Run tests in watch mode
npm run test:watch

# Type checking
npx tsc --noEmit
```

## Deployment

### Manual Deployment to Vercel

```bash
npx vercel --prod
```

### Automatic Deployment

Push to main branch:
```bash
git push origin main
```

Vercel automatically builds and deploys.

### Environment Variables

Set in Vercel Project Settings:
1. Go to Settings → Environment Variables
2. Add all variables from `.env.example`
3. Redeploy project

## Performance Tips

1. **Image optimization:** Use Next.js Image component
2. **Code splitting:** Components automatically code-split
3. **Caching:** Use proper cache headers in API responses
4. **Database indexes:** Already created in migrations
5. **Query optimization:** Use `select()` to limit fields

## Security Checklist

- [ ] RLS policies enabled on all tables
- [ ] Service role key never exposed in browser
- [ ] Input validation on all endpoints
- [ ] No hardcoded secrets
- [ ] HTTPS enforced in production
- [ ] CORS properly configured if needed

## Common Issues

### "Environment variables not found"

Make sure `.env.local` exists with all required variables.

### "Supabase connection failed"

Check that:
- NEXT_PUBLIC_SUPABASE_URL is correct
- NEXT_PUBLIC_SUPABASE_ANON_KEY is valid
- Internet connection is working

### Build fails with TypeScript errors

Run `npx tsc --noEmit` to see detailed errors.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT - see LICENSE file

## Support

Questions? Open an issue on [GitHub](https://github.com/IsaiahDupree/music-selector/issues)
