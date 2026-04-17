-- Rollback Migration 001: Drop tracks table
-- This script reverses the tracks schema creation

-- Drop indexes
DROP INDEX IF EXISTS idx_tracks_user_id;
DROP INDEX IF EXISTS idx_tracks_genre;
DROP INDEX IF EXISTS idx_tracks_mood;
DROP INDEX IF EXISTS idx_tracks_energy_level;
DROP INDEX IF EXISTS idx_tracks_duration_sec;
DROP INDEX IF EXISTS idx_tracks_is_trending;
DROP INDEX IF EXISTS idx_tracks_title_artist;
DROP INDEX IF EXISTS idx_tracks_created_at;

-- Drop RLS policies
DROP POLICY IF EXISTS "Users can view their own tracks" ON tracks;
DROP POLICY IF EXISTS "Users can insert their own tracks" ON tracks;
DROP POLICY IF EXISTS "Users can update their own tracks" ON tracks;
DROP POLICY IF EXISTS "Users can delete their own tracks" ON tracks;

-- Drop table
DROP TABLE IF EXISTS tracks;

-- Verify rollback
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tracks') THEN
    RAISE NOTICE 'Rollback successful: tracks table removed';
  ELSE
    RAISE EXCEPTION 'Rollback failed: tracks table still exists';
  END IF;
END $$;
