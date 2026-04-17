-- Rollback Migration 004: Drop playlists table and related objects
-- This script reverses the playlist schema creation

-- Drop foreign key constraints
ALTER TABLE IF EXISTS playlist_items DROP CONSTRAINT IF EXISTS fk_playlist_items_playlist_id;
ALTER TABLE IF EXISTS playlist_items DROP CONSTRAINT IF EXISTS fk_playlist_items_track_id;

-- Drop indexes
DROP INDEX IF EXISTS idx_playlist_items_playlist_id;
DROP INDEX IF EXISTS idx_playlist_items_track_id;

-- Drop tables
DROP TABLE IF EXISTS playlist_items;
DROP TABLE IF EXISTS playlists;

-- Verify rollback
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'playlists') THEN
    RAISE NOTICE 'Rollback successful: playlists table removed';
  ELSE
    RAISE EXCEPTION 'Rollback failed: playlists table still exists';
  END IF;
END $$;
