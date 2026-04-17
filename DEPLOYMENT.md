# Deployment Guide — MusicLibrary

## Prerequisites

- Node.js 18+ and npm
- Supabase account (free tier available)
- Vercel account (free tier available)
- GitHub account and repository

## Step 1: Prepare Supabase

### Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click "New Project"
3. Choose your region and select a strong password
4. Wait for the project to initialize

### Get API Keys

1. Go to Project Settings → API
2. Copy these values to a safe location:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
3. Go to Project Settings → API Keys (Service Role)
4. Copy `SUPABASE_SERVICE_ROLE_KEY`

### Set Up Database

1. Go to SQL Editor
2. Run each migration file in order:
   - Copy content from `supabase/migrations/001_create_tracks_table.sql`
   - Run it
   - Repeat for migrations 002, 003, 004

### Enable Storage

1. Go to Storage
2. Click "New bucket"
3. Name it `audio-files`
4. Set it to Public
5. Allow these MIME types:
   - `audio/mpeg`
   - `audio/wav`
   - `audio/aac`
   - `audio/flac`

## Step 2: Prepare for Vercel Deployment

### Update Environment Variables

```bash
cp .env.example .env.local
```

Edit `.env.local` with your Supabase keys:

```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
NEXT_PUBLIC_APP_URL=https://your-domain.vercel.app
```

### Test Locally

```bash
npm install
npm run build
npm run start
```

Visit http://localhost:3000 and test:
- [ ] Health check endpoint: `/api/health`
- [ ] Upload a file
- [ ] View library
- [ ] Search functionality

## Step 3: Deploy to Vercel

### Option A: Using Vercel CLI

```bash
# Install Vercel CLI if you haven't
npm install -g vercel

# Deploy
vercel --prod
```

### Option B: Using GitHub Integration

1. Push code to GitHub
2. Go to [vercel.com](https://vercel.com)
3. Click "Add New" → "Project"
4. Import your GitHub repository
5. Add environment variables in project settings
6. Click "Deploy"

### Configure Environment Variables in Vercel

1. Go to Project Settings → Environment Variables
2. Add each variable with appropriate values:
   - Set Production environment for API keys
   - Leave `NEXT_PUBLIC_APP_URL` for production domain

## Step 4: Verify Deployment

After deployment, visit your production URL and check:

1. **Health Check**
   ```bash
   curl https://your-domain.com/api/health
   ```

2. **Upload Functionality**
   - Click "Upload Audio"
   - Upload a test audio file
   - Verify it appears in the library

3. **Search**
   - Search for uploaded tracks
   - Verify results appear

4. **Filters**
   - Apply genre/mood filters
   - Verify filtering works

5. **Export**
   - Export library as CSV or JSON
   - Verify files download correctly

## Troubleshooting

### "Database connection failed"

- Check `NEXT_PUBLIC_SUPABASE_URL` in Vercel environment variables
- Verify Supabase project is active
- Check RLS policies are enabled

### "File upload fails"

- Verify `audio-files` bucket exists in Supabase
- Check bucket is public
- Verify `SUPABASE_SERVICE_ROLE_KEY` is correct

### "Build fails"

Run `npm run build` locally to see detailed errors:
```bash
npm install
npm run build
```

### "TypeScript errors in production"

Run `npx tsc --noEmit` to check types:
```bash
npx tsc --noEmit
```

## Performance Optimization (Optional)

### Enable Caching

1. Go to Vercel Project Settings → Integrations
2. Recommend CDN edge caching for API responses

### Database Optimization

1. Verify indexes exist (created in migrations)
2. Monitor slow queries in Supabase

### Monitor Deployment

1. Check Vercel Analytics
2. Monitor Supabase API usage
3. Review application logs

## Security Checklist

- [ ] All environment variables are set
- [ ] `SUPABASE_SERVICE_ROLE_KEY` is only in server environment
- [ ] RLS policies are enabled on all tables
- [ ] Storage bucket has appropriate permissions
- [ ] HTTPS is enforced
- [ ] CORS is configured if needed

## Custom Domain

1. Go to Vercel Project Settings → Domains
2. Add your domain
3. Update DNS records as instructed
4. Wait for DNS propagation (up to 24 hours)

## Monitoring & Maintenance

### Regular Checks

- [ ] Monitor API error logs
- [ ] Check database storage usage
- [ ] Review user activity

### Backups

1. Go to Supabase → Backups
2. Enable automated backups
3. Export critical data regularly

### Updates

Keep dependencies up to date:
```bash
npm update
npm audit
```

## Support

For issues:
1. Check [GitHub Issues](https://github.com/IsaiahDupree/music-selector/issues)
2. Review Supabase documentation
3. Check Vercel deployment logs

## Post-Deployment

### Send Feedback

After deploying, consider:
- [ ] Test with real audio files
- [ ] Get user feedback
- [ ] Monitor error logs
- [ ] Optimize based on usage

### Feature Roadmap

Future enhancements:
- Audio metadata extraction
- Automatic genre classification
- Machine learning recommendations
- Advanced batch operations
- Team collaboration features
