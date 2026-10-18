/**
 * music-selector — Remotion adapter type definitions
 */

export interface MusicSelectOptions {
  mood?: 'energetic' | 'calm' | 'inspiring' | 'dramatic' | 'uplifting' | 'happy' | 'focused';
  energy?: number;          // 0.0–1.0
  duration?: number;        // seconds
  platform?: 'instagram' | 'tiktok' | 'youtube' | 'linkedin' | 'twitter' | 'facebook';
  contentType?:
    | 'viral_short' | 'reels' | 'tutorial' | 'educational'
    | 'product_demo' | 'dev_vlog' | 'storytelling' | 'brand'
    | 'montage' | 'shorts' | 'background';
  pacing?: 'slow' | 'medium' | 'fast' | 'very_fast';
  transcript?: string;
  trending?: boolean;
  top?: number;
}

export interface ScoreBreakdown {
  mood: number;
  energy: number;
  duration: number;
  pacing: number;
  content_type: number;
}

export interface MusicTrack {
  id: string;
  title: string;
  artist: string;
  local_path: string;
  resolved_path: string;
  genre: string;
  subgenres: string[];
  mood: string;
  moods: string[];
  energy_level: number;
  tempo: string;
  bpm: number | null;
  duration_sec: number | null;
  source: string;
  license: string;
  is_trending: boolean;
  platforms_trending: string[];
  suitable_for: string[];
  scene_fit: string[];
  usage_count: number;
  score: number;
  score_breakdown: ScoreBreakdown;
}

export function selectMusic(opts?: MusicSelectOptions): Promise<MusicTrack | null>;
export function selectMusicSync(opts?: MusicSelectOptions): MusicTrack | null;
export function selectMusicTopN(opts?: MusicSelectOptions, n?: number): MusicTrack[];
export function getStaticPath(track: MusicTrack, publicDir?: string): string;
export function resolveTrackPath(localPath: string): string;
