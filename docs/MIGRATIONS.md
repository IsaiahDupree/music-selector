# Database Migrations Guide

This document explains how to manage database migrations for MusicLibrary.

## Overview

Migrations are version-controlled SQL scripts that manage database schema changes. Each migration is numbered and includes both forward and rollback scripts for safe schema evolution.

## Migration Files

All migration files are stored in `supabase/migrations/`:

- `001_create_tracks_table.sql` - Core tracks table with metadata columns
- `001_rollback.sql` - Rollback script for migration 001
- `002_create_metadata_table.sql` - Extended audio metadata storage
- `002_rollback.sql` - Rollback script for migration 002
- `003_create_tags_table.sql` - User-defined tags and track tagging
- `003_rollback.sql` - Rollback script for migration 003
- `004_create_playlists_table.sql` - Playlist creation and management
- `004_rollback.sql` - Rollback script for migration 004

## Running Migrations

### Method 1: Using the Migration Script (Recommended)

The `scripts/migrate.sh` script handles migration execution with proper error handling.

```bash
# Apply all pending migrations
./scripts/migrate.sh

# List all applied migrations
./scripts/migrate.sh --list

# Rollback to a specific version
./scripts/migrate.sh --rollback --version 001
```

### Method 2: Using Supabase CLI

If you have the Supabase CLI installed:

```bash
# Migrate the database
supabase migration up

# Create a new migration
supabase migration new my_migration_name

# Rollback the last migration
supabase migration down 1
```

### Method 3: Supabase Dashboard

1. Go to your Supabase project dashboard
2. Navigate to the SQL Editor
3. Copy-paste the SQL content from migration files
4. Execute each migration in order

## Prerequisites

Before running migrations, ensure you have set the required environment variables:

```bash
# In .env.local or your shell
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

## Migration Structure

Each migration includes:

### Forward Migration (`XXX_create_*.sql`)
- Creates tables with proper schema
- Sets up indexes for performance
- Configures Row-Level Security (RLS) policies
- Adds foreign key constraints
- Includes verification queries

### Rollback Script (`XXX_rollback.sql`)
- Drops foreign key constraints
- Removes indexes
- Removes RLS policies
- Drops tables in correct order
- Includes verification to confirm rollback

## Schema Overview

### Tracks Table
- Core table for audio file metadata
- Columns: id, user_id, title, artist, genre, mood, duration_sec, energy_level, file_path, is_trending, created_at, updated_at
- Indexes on searchable columns (genre, mood, duration, energy)
- RLS policies for user-level isolation

### Track Metadata Table
- Extended audio technical metadata
- Columns: id, track_id, bitrate, codec, sample_rate, channels, file_size, format
- Foreign key relationship to tracks table
- ON DELETE CASCADE for automatic cleanup

### Tags Table
- User-defined tags for organizing tracks
- Columns: id, user_id, name, created_at
- Many-to-many relationship with tracks via track_tags table

### Playlists Table
- User-created playlists
- Columns: id, user_id, name, description, created_at, updated_at
- Contains playlist_items for maintaining track order

## Best Practices

### Creating New Migrations

1. **Use sequential numbering**: Continue from the last migration number
2. **Use descriptive names**: `005_add_user_preferences_table.sql`
3. **Include both migration and rollback**: Always create matching rollback scripts
4. **Test locally first**: Run against a test database before production
5. **Document changes**: Add comments explaining schema changes
6. **Use transactions**: Wrap changes in `BEGIN; ... COMMIT;`

### Running Migrations

1. **Test in development first**: Always test migrations locally
2. **Backup production database**: Take a snapshot before migrating
3. **Run during low-traffic periods**: Minimize impact on users
4. **Monitor after migration**: Watch error logs and performance metrics
5. **Keep rollback plan ready**: Be prepared to rollback if issues occur

### Naming Convention

```
XXX_description.sql       # Forward migration
XXX_rollback.sql          # Rollback script

Examples:
001_create_tracks_table.sql
001_rollback.sql
005_add_spatial_indexes.sql
005_rollback.sql
```

## Production Migration Checklist

Before migrating production:

- [ ] Test migrations against a copy of production data
- [ ] Review SQL for security issues
- [ ] Verify RLS policies are correct
- [ ] Check index creation won't lock tables
- [ ] Prepare rollback plan
- [ ] Notify team of migration window
- [ ] Take database snapshot/backup
- [ ] Execute migration during low-traffic period
- [ ] Monitor application performance
- [ ] Verify all features work correctly
- [ ] Document any issues encountered

## Troubleshooting

### Migration Fails with "Constraint Violation"

**Problem**: Foreign key constraint error
**Solution**:
1. Check that referenced tables exist
2. Verify migration order
3. Clear any existing data conflicts

### Rollback Fails

**Problem**: Rollback script doesn't execute
**Solution**:
1. Check table exists before dropping
2. Remove dependent objects first
3. Check RLS policies are disabled
4. Verify you have sufficient permissions

### Performance Issues After Migration

**Problem**: Slow queries after schema changes
**Solution**:
1. Verify indexes were created
2. Analyze query plans with `EXPLAIN`
3. Check statistics with `ANALYZE`
4. Consider adding additional indexes

### Connection Issues

**Problem**: Can't connect to Supabase
**Solution**:
1. Verify `SUPABASE_URL` is correct
2. Verify `SUPABASE_SERVICE_ROLE_KEY` is valid
3. Check VPN/firewall isn't blocking connection
4. Test with Supabase dashboard directly

## Examples

### Applying Migrations

```bash
# Set environment variables
export SUPABASE_URL="https://ivhfuhxorppptyuofbgq.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="sbp_xxxxxxxxxxxxx"

# Run migrations
./scripts/migrate.sh

# Output:
# ✓ Applying migration: 001_create_tracks_table.sql
# ✓ Applied 001_create_tracks_table.sql
# ✓ Applying migration: 002_create_metadata_table.sql
# ✓ Applied 002_create_metadata_table.sql
# [...]
# ✓ All migrations completed successfully
```

### Checking Migration Status

```bash
./scripts/migrate.sh --list

# Output:
# Applied Migrations:
# 001_create_tracks_table.sql (2024-04-17 10:30:00)
# 002_create_metadata_table.sql (2024-04-17 10:30:15)
# 003_create_tags_table.sql (2024-04-17 10:30:30)
# 004_create_playlists_table.sql (2024-04-17 10:30:45)
```

### Rolling Back

```bash
# Rollback migration 003
./scripts/migrate.sh --rollback --version 003

# Output:
# Rolling back migration version 003...
# ✓ Rolled back version 003
# ✓ Rollback completed successfully
```

## Further Reading

- [Supabase Migration Documentation](https://supabase.com/docs/reference/cli/supabase_migration)
- [PostgreSQL DDL Reference](https://www.postgresql.org/docs/current/ddl.html)
- [Row-Level Security in PostgreSQL](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
