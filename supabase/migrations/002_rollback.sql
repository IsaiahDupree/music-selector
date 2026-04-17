-- Rollback Migration 002: Drop metadata table
-- This script reverses the metadata schema creation

-- Drop foreign key constraints
ALTER TABLE IF EXISTS track_metadata DROP CONSTRAINT IF EXISTS fk_track_metadata_track_id;

-- Drop indexes
DROP INDEX IF EXISTS idx_track_metadata_track_id;
DROP INDEX IF EXISTS idx_track_metadata_bitrate;
DROP INDEX IF EXISTS idx_track_metadata_codec;

-- Drop table
DROP TABLE IF EXISTS track_metadata;

-- Verify rollback
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'track_metadata') THEN
    RAISE NOTICE 'Rollback successful: track_metadata table removed';
  ELSE
    RAISE EXCEPTION 'Rollback failed: track_metadata table still exists';
  END IF;
END $$;
