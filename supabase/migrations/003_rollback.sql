-- Rollback Migration 003: Drop tags table and related objects
-- This script reverses the tags schema creation

-- Drop foreign key constraints
ALTER TABLE IF EXISTS track_tags DROP CONSTRAINT IF EXISTS fk_track_tags_track_id;
ALTER TABLE IF EXISTS track_tags DROP CONSTRAINT IF EXISTS fk_track_tags_tag_id;

-- Drop indexes
DROP INDEX IF EXISTS idx_track_tags_track_id;
DROP INDEX IF EXISTS idx_track_tags_tag_id;
DROP INDEX IF EXISTS idx_tags_user_id;
DROP INDEX IF EXISTS idx_tags_name;

-- Drop tables
DROP TABLE IF EXISTS track_tags;
DROP TABLE IF EXISTS tags;

-- Verify rollback
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tags') THEN
    RAISE NOTICE 'Rollback successful: tags table removed';
  ELSE
    RAISE EXCEPTION 'Rollback failed: tags table still exists';
  END IF;
END $$;
