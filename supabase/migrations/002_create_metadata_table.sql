-- Create metadata table for extended audio metadata
CREATE TABLE IF NOT EXISTS track_metadata (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  track_id UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
  bitrate INTEGER,
  codec VARCHAR(50),
  sample_rate INTEGER,
  channels INTEGER,
  file_size INTEGER,
  file_path VARCHAR(255),
  file_hash VARCHAR(64),
  storage_url TEXT,
  tempo VARCHAR(20),
  subgenres TEXT[],
  moods TEXT[],
  content_types TEXT[],
  scene_fit TEXT[],
  suitable_for TEXT[],
  platforms_trending TEXT[],
  source VARCHAR(50),
  license VARCHAR(50),
  usage_count INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create indexes
CREATE INDEX idx_metadata_track_id ON track_metadata(track_id);
CREATE INDEX idx_metadata_codec ON track_metadata(codec);
CREATE INDEX idx_metadata_bitrate ON track_metadata(bitrate);
CREATE INDEX idx_metadata_sample_rate ON track_metadata(sample_rate);
CREATE INDEX idx_metadata_source ON track_metadata(source);

-- Enable RLS
ALTER TABLE track_metadata ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can read metadata for their tracks"
  ON track_metadata
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_metadata.track_id AND tracks.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert metadata for their tracks"
  ON track_metadata
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_metadata.track_id AND tracks.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can update metadata for their tracks"
  ON track_metadata
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_metadata.track_id AND tracks.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_metadata.track_id AND tracks.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete metadata for their tracks"
  ON track_metadata
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_metadata.track_id AND tracks.user_id = auth.uid()
    )
  );
