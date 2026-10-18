import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const supabaseServiceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Create clients only if env vars are available
export const supabaseClient =
  supabaseUrl && supabaseAnonKey
    ? createClient(supabaseUrl, supabaseAnonKey)
    : null;

export const supabaseAdmin =
  supabaseUrl && supabaseServiceRoleKey
    ? createClient(supabaseUrl, supabaseServiceRoleKey)
    : null;

export type Track = {
  id: string;
  title: string;
  artist: string | null;
  genre: string | null;
  mood: string | null;
  energy_level: number | null;
  duration_sec: number | null;
  bpm: number | null;
  is_trending: boolean;
  created_at: string;
  updated_at: string;
  user_id: string | null;
};

export type TrackMetadata = {
  id: string;
  track_id: string;
  bitrate: number | null;
  codec: string | null;
  sample_rate: number | null;
  channels: number | null;
  file_size: number | null;
  file_path: string | null;
  file_hash: string | null;
  storage_url: string | null;
  tempo: string | null;
  subgenres: string[] | null;
  moods: string[] | null;
  content_types: string[] | null;
  scene_fit: string[] | null;
  suitable_for: string[] | null;
  platforms_trending: string[] | null;
  source: string | null;
  license: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
};
