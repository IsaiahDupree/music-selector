# Production Environment Setup Guide

This guide covers setting up and maintaining MusicLibrary in a production environment on Vercel and Supabase.

## Overview

Production deployment consists of:
- **Database**: Dedicated Supabase project with production PostgreSQL instance
- **Storage**: Supabase Storage bucket for audio files
- **Authentication**: Supabase Auth for user management
- **API**: Next.js deployed on Vercel
- **Monitoring**: Error tracking and performance metrics
- **Secrets**: Secure environment variable management

## Supabase Production Setup

### 1. Create Production Project

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Create a new project:
   - **Organization**: Your organization
   - **Project name**: `music-library-prod` or similar
   - **Database password**: Generate a strong password (30+ characters)
   - **Region**: Choose region closest to your users
   - **Pricing plan**: Pro plan recommended for production

3. Wait for project initialization (5-10 minutes)

### 2. Configure Database

Once the project is ready:

1. **Enable required extensions**:
   - Go to Extensions
   - Search for and enable:
     - `uuid-ossp` (for UUID generation)
     - `pgcrypto` (for encryption)
     - `plpgsql` (stored procedures)

2. **Run migrations**:
   ```bash
   export SUPABASE_URL=https://your-prod-project.supabase.co
   export SUPABASE_SERVICE_ROLE_KEY=your-prod-service-role-key
   ./scripts/migrate.sh
   ```

3. **Verify schema**:
   - Open SQL Editor
   - Query: `SELECT * FROM information_schema.tables WHERE table_schema='public';`
   - Verify all 4 tables exist: tracks, track_metadata, tags, playlists

### 3. Configure Authentication

1. **Email/Password Auth**:
   - Go to Authentication > Providers
   - Enable Email with Password
   - Configure email templates:
     - Welcome email
     - Confirmation email
     - Password reset email
     - Change email address

2. **Email Configuration** (Optional - uses Supabase default by default):
   - Go to Email Templates
   - Customize sender name and logo
   - Or use custom SMTP:
     - Go to Auth > Email Templates > SMTP
     - Configure your mail server details

3. **User Settings**:
   - Set password requirements
   - Set email confirmation requirement
   - Set auto-confirm new users if needed

### 4. Configure Storage Bucket

1. **Create audio-files bucket**:
   - Go to Storage > Buckets
   - Create new bucket: `audio-files`
   - Set to **Private** (RLS required)

2. **Storage size limits**:
   - Set max file size: 100MB
   - Configure CORS if needed

3. **Set RLS Policies**:
   ```sql
   -- Allow authenticated users to upload
   CREATE POLICY "Authenticated users can upload"
   ON storage.objects FOR INSERT
   TO authenticated
   WITH CHECK (
     bucket_id = 'audio-files' AND
     auth.uid()::text = (storage.foldername(name))[1]
   );

   -- Allow users to read their own files
   CREATE POLICY "Users can read own audio files"
   ON storage.objects FOR SELECT
   TO authenticated
   USING (
     bucket_id = 'audio-files' AND
     auth.uid()::text = (storage.foldername(name))[1]
   );

   -- Allow users to delete their own files
   CREATE POLICY "Users can delete own audio files"
   ON storage.objects FOR DELETE
   TO authenticated
   USING (
     bucket_id = 'audio-files' AND
     auth.uid()::text = (storage.foldername(name))[1]
   );
   ```

### 5. Configure Row-Level Security

Verify RLS is enabled on all tables:

```sql
-- Check RLS status
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public';

-- RLS should be ON for all tables
```

If RLS is not enabled:

```sql
ALTER TABLE tracks ENABLE ROW LEVEL SECURITY;
ALTER TABLE track_metadata ENABLE ROW LEVEL SECURITY;
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE playlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE playlist_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE track_tags ENABLE ROW LEVEL SECURITY;
```

## Vercel Deployment

### 1. Connect Repository

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Import project:
   - Click "Add New" > "Project"
   - Import from Git (GitHub/GitLab/Bitbucket)
   - Select your repository
   - Vercel auto-detects Next.js

### 2. Configure Environment Variables

1. **In Vercel Dashboard**:
   - Go to Project Settings > Environment Variables
   - Add production variables:

   ```
   NEXT_PUBLIC_SUPABASE_URL=https://your-prod-project.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your-prod-anon-key
   SUPABASE_SERVICE_ROLE_KEY=your-prod-service-role-key
   ```

   Note: Never commit `.env.local` to git

2. **Or via Vercel CLI**:
   ```bash
   vercel env add NEXT_PUBLIC_SUPABASE_URL
   vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY
   vercel env add SUPABASE_SERVICE_ROLE_KEY
   ```

### 3. Deploy

1. **First deployment**:
   ```bash
   vercel --prod
   ```

2. **Automatic deployments**:
   - Subsequent pushes to main branch automatically deploy
   - Preview deployments created for pull requests

3. **Monitor build**:
   - Go to Deployments tab
   - Watch build logs for errors
   - Wait for "Ready" status

## Secrets Management

### Environment Variables Structure

```
Production:
├── NEXT_PUBLIC_SUPABASE_URL          # Public - browser accessible
├── NEXT_PUBLIC_SUPABASE_ANON_KEY     # Public - browser accessible
├── SUPABASE_SERVICE_ROLE_KEY          # Secret - server-only
└── NODE_ENV=production

Development:
├── NEXT_PUBLIC_SUPABASE_URL
├── NEXT_PUBLIC_SUPABASE_ANON_KEY
├── SUPABASE_SERVICE_ROLE_KEY
└── NODE_ENV=development
```

### Getting Production Keys

From Supabase Project Settings:

1. **Anon Key**:
   - Settings > API
   - Copy "anon public" key

2. **Service Role Key**:
   - Settings > API
   - Copy "service_role secret" key (RESTRICTED)

3. **Project URL**:
   - Settings > API
   - Copy "Project URL"

### Security Best Practices

1. **Never commit secrets**:
   - `.env.local` in `.gitignore`
   - Use Vercel env variables
   - Use Supabase dashboard for secrets

2. **Rotate keys regularly**:
   - Supabase dashboard: Settings > API > Regenerate
   - Update Vercel environment variables
   - Redeploy application

3. **Principle of least privilege**:
   - Service role key only on server
   - Anon key only for public operations
   - Use RLS policies to restrict data access

4. **Audit access**:
   - Enable Supabase audit logs
   - Monitor API usage
   - Set up alerts

## Database Backups

### Enable Automated Backups

In Supabase Dashboard:

1. Go to Project Settings > Backups
2. Enable Point-in-Time Recovery (PITR)
3. Set backup retention: 7-30 days
4. Schedule regular backups

### Manual Backup

```bash
# Using pg_dump (requires psql installed)
pg_dump "postgresql://postgres:PASSWORD@db.supabase.co:5432/postgres" \
  > backup.sql

# Using Supabase CLI
supabase db pull
```

### Restore from Backup

1. In Supabase Dashboard:
   - Go to Backups
   - Select backup to restore
   - Click "Restore"
   - Confirm operation

## Monitoring and Maintenance

### Enable Monitoring

1. **Supabase Monitoring**:
   - Database > Status tab
   - View query performance
   - Monitor connection count
   - Check storage usage

2. **Vercel Monitoring**:
   - Project > Deployments
   - Check build times
   - Monitor API response times
   - View error rates

3. **Application Logs**:
   ```bash
   # View Vercel logs
   vercel logs

   # View Supabase logs
   supabase logs --tail
   ```

### Scaling Considerations

- **Database connections**: Monitor via Supabase metrics
- **Storage usage**: Track audio file size growth
- **Bandwidth**: Monitor outbound storage bandwidth
- **Compute**: Monitor API response times

If hitting limits:
1. Upgrade Supabase plan
2. Implement caching layer
3. Optimize database queries
4. Archive old tracks

## Performance Optimization

### Database

```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM tracks WHERE genre = 'lofi';

-- Update statistics
ANALYZE tracks;

-- Monitor slow queries
SELECT query, mean_time, calls
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat%'
ORDER BY mean_time DESC
LIMIT 10;
```

### API

1. **Enable caching**:
   - Add Cache-Control headers
   - Implement Redis layer (optional)
   - Cache filter options

2. **Compress responses**:
   - Vercel automatically gzips
   - Verify with Network tab

3. **Optimize queries**:
   - Use pagination
   - Select only needed columns
   - Add indexes (done in migrations)

### Storage

1. **Signed URLs expiry**:
   - Set reasonable expiry (1 hour - 1 day)
   - Regenerate as needed

2. **Bucket optimization**:
   - Enable CDN caching
   - Set appropriate CORS headers

## Troubleshooting

### Cannot Connect to Database

```bash
# Verify credentials
psql "postgresql://user:password@host:5432/postgres"

# Check connection limit
# In Supabase: Settings > Database > Replication
```

### Slow Queries

```sql
-- Find slow queries
SELECT query, mean_time, calls
FROM pg_stat_statements
WHERE mean_time > 100  -- queries slower than 100ms
ORDER BY mean_time DESC;

-- Add missing indexes
CREATE INDEX idx_tracks_genre ON tracks(genre);
CREATE INDEX idx_tracks_created_at ON tracks(created_at);
```

### Storage Issues

1. **File not uploading**:
   - Check file size < 100MB
   - Verify bucket permissions
   - Check CORS settings

2. **File not accessible**:
   - Verify signed URL hasn't expired
   - Check RLS policies
   - Check user authentication

### Performance Issues

1. **Slow page loads**:
   - Enable Vercel Analytics
   - Check Supabase query performance
   - Review network waterfall in DevTools

2. **High bandwidth usage**:
   - Check for unoptimized audio files
   - Review storage CDN usage
   - Implement caching headers

## Disaster Recovery

### Database Failure

1. **Immediate action**:
   - Supabase handles automatic failover
   - Check status dashboard
   - Wait for recovery (usually <5 minutes)

2. **If not recovering**:
   - Restore from backup
   - Contact Supabase support
   - Update DNS/endpoints if needed

### Application Failure

1. **Immediate action**:
   - Check Vercel deployment status
   - Rollback to previous version
   - Check error logs

2. **Rollback**:
   ```bash
   # Revert to previous commit
   git revert HEAD
   git push
   # Vercel auto-deploys
   ```

## Security Audit Checklist

- [ ] RLS policies enabled on all tables
- [ ] Service role key not exposed in client code
- [ ] HTTPS enforced (Vercel default)
- [ ] Database backups enabled
- [ ] Audit logs enabled
- [ ] Authentication rate limiting configured
- [ ] CORS properly configured
- [ ] API keys rotated within last 90 days
- [ ] Secrets not in git history
- [ ] Database firewall rules configured

## Support and Escalation

**Supabase Issues**:
- Dashboard status: https://status.supabase.com
- Documentation: https://supabase.com/docs
- Discord community: https://discord.supabase.com

**Vercel Issues**:
- Status page: https://www.vercel-status.com
- Documentation: https://vercel.com/docs
- Community: https://github.com/vercel/next.js/discussions

**Application Issues**:
- Check error logs
- Review recent deployments
- Contact development team
