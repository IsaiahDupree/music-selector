-- Create tracks table
CREATE TABLE IF NOT EXISTS tracks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  artist VARCHAR(255),
  genre VARCHAR(100),
  mood VARCHAR(50),
  energy_level NUMERIC(2,1) CHECK (energy_level >= 0 AND energy_level <= 1),
  duration_sec INTEGER,
  bpm INTEGER,
  is_trending BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

-- Create indexes for searchable columns
CREATE INDEX idx_tracks_title ON tracks USING GIN (to_tsvector('english', title));
CREATE INDEX idx_tracks_artist ON tracks USING GIN (to_tsvector('english', artist));
CREATE INDEX idx_tracks_genre ON tracks(genre);
CREATE INDEX idx_tracks_mood ON tracks(mood);
CREATE INDEX idx_tracks_energy ON tracks(energy_level);
CREATE INDEX idx_tracks_duration ON tracks(duration_sec);
CREATE INDEX idx_tracks_user_id ON tracks(user_id);
CREATE INDEX idx_tracks_is_trending ON tracks(is_trending);

-- Enable RLS
ALTER TABLE tracks ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only see their own tracks
CREATE POLICY "Users can read their own tracks"
  ON tracks
  FOR SELECT
  USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can insert their own tracks"
  ON tracks
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own tracks"
  ON tracks
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own tracks"
  ON tracks
  FOR DELETE
  USING (auth.uid() = user_id);
