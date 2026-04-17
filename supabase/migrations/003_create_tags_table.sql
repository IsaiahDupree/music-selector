-- Create tags table
CREATE TABLE IF NOT EXISTS tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL UNIQUE,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create track_tags junction table
CREATE TABLE IF NOT EXISTS track_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  track_id UUID NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
  tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  UNIQUE(track_id, tag_id)
);

-- Create indexes
CREATE INDEX idx_tags_user_id ON tags(user_id);
CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_track_tags_track_id ON track_tags(track_id);
CREATE INDEX idx_track_tags_tag_id ON track_tags(tag_id);

-- Enable RLS
ALTER TABLE tags ENABLE ROW LEVEL SECURITY;
ALTER TABLE track_tags ENABLE ROW LEVEL SECURITY;

-- RLS Policies for tags
CREATE POLICY "Users can read their own tags"
  ON tags
  FOR SELECT
  USING (auth.uid() = user_id OR user_id IS NULL);

CREATE POLICY "Users can create tags"
  ON tags
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own tags"
  ON tags
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own tags"
  ON tags
  FOR DELETE
  USING (auth.uid() = user_id);

-- RLS Policies for track_tags
CREATE POLICY "Users can read track_tags for their tracks"
  ON track_tags
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_tags.track_id AND tracks.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can add tags to their tracks"
  ON track_tags
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_tags.track_id AND tracks.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can remove tags from their tracks"
  ON track_tags
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM tracks WHERE tracks.id = track_tags.track_id AND tracks.user_id = auth.uid()
    )
  );
