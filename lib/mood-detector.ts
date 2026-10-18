/**
 * Mood Detector
 * Automatic audio mood detection
 */

import { supabaseAdmin } from './supabase';

export interface MoodDetection {
  mood: string;
  confidence: number;
  emotionalProfile?: Record<string, number>;
  alternatives?: Array<{ mood: string; confidence: number }>;
}

export type MoodType =
  | 'happy'
  | 'sad'
  | 'calm'
  | 'energetic'
  | 'angry'
  | 'romantic'
  | 'melancholic';

/**
 * Analyze audio and detect mood
 */
export async function detectMood(
  audioPath: string,
  audioData?: { bitrate?: number; codec?: string; sample_rate?: number }
): Promise<MoodDetection> {
  // Extract emotional features
  const features = await extractEmotionalFeatures(audioPath, audioData);

  // Classify mood
  return classifyMoodFromFeatures(features);
}

/**
 * Extract emotional features from audio
 */
async function extractEmotionalFeatures(
  audioPath: string,
  audioData?: { bitrate?: number; codec?: string; sample_rate?: number }
): Promise<Record<string, number>> {
  // Placeholder feature extraction
  // In production would analyze:
  // - Valence (positive vs negative emotions)
  // - Arousal (energy level)
  // - Timbre characteristics
  // - Harmony and chord progressions

  return {
    valence: Math.random(), // 0-1: negative to positive
    arousal: Math.random(), // 0-1: low to high energy
    brightness: Math.random(), // 0-1: dark to bright
    stability: Math.random(), // 0-1: unstable to stable
    complexity: Math.random(), // 0-1: simple to complex
  };
}

/**
 * Classify mood from extracted emotional features
 */
function classifyMoodFromFeatures(
  features: Record<string, number>
): MoodDetection {
  const valence = features.valence || 0.5;
  const arousal = features.arousal || 0.5;
  const brightness = features.brightness || 0.5;
  const stability = features.stability || 0.5;

  // Map feature space to mood categories
  // Using valence-arousal model similar to psychology of music
  const moodScores = calculateMoodScores(
    valence,
    arousal,
    brightness,
    stability
  );

  // Get top mood
  const sorted = Object.entries(moodScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  const topMood = sorted[0];
  const confidence = Math.min(0.99, topMood[1] / 100);

  // Build emotional profile
  const emotionalProfile: Record<string, number> = {
    valence: Math.round(valence * 100),
    arousal: Math.round(arousal * 100),
    brightness: Math.round(brightness * 100),
    stability: Math.round(stability * 100),
  };

  return {
    mood: topMood[0],
    confidence,
    emotionalProfile,
    alternatives: sorted.slice(1).map(([mood, score]) => ({
      mood,
      confidence: Math.min(0.99, score / 100),
    })),
  };
}

/**
 * Calculate mood probability scores based on features
 */
function calculateMoodScores(
  valence: number,
  arousal: number,
  brightness: number,
  stability: number
): Record<MoodType, number> {
  const scores: Record<MoodType, number> = {
    happy: 50,
    sad: 50,
    calm: 50,
    energetic: 50,
    angry: 50,
    romantic: 50,
    melancholic: 50,
  };

  // Happy: high valence + moderate-high arousal + bright
  if (valence > 0.6 && arousal > 0.4) {
    scores.happy += (valence - 0.6) * 30 + brightness * 20;
  }

  // Sad: low valence + low arousal + dark
  if (valence < 0.4 && arousal < 0.4) {
    scores.sad += (0.4 - valence) * 30 + (1 - brightness) * 20;
  }

  // Calm: moderate valence + low arousal + stable
  if (arousal < 0.3 && stability > 0.6) {
    scores.calm += (0.3 - arousal) * 40 + (stability - 0.6) * 20;
  }

  // Energetic: any valence + high arousal + bright
  if (arousal > 0.7) {
    scores.energetic += (arousal - 0.7) * 40 + brightness * 20;
  }

  // Angry: low valence + high arousal + dark + unstable
  if (valence < 0.4 && arousal > 0.7 && stability < 0.4) {
    scores.angry += Math.abs(valence - 0.5) * 30 + arousal * 20;
  }

  // Romantic: moderate-high valence + moderate arousal + stable
  if (valence > 0.5 && arousal < 0.6 && stability > 0.6) {
    scores.romantic += (valence - 0.5) * 20 + brightness * 10;
  }

  // Melancholic: low-moderate valence + low arousal
  if (valence < 0.6 && arousal < 0.5) {
    scores.melancholic += (0.6 - valence) * 25 + stability * 15;
  }

  return scores;
}

/**
 * Detect and store mood in database
 */
export async function detectAndStoreMood(
  trackId: string,
  audioPath: string,
  allowManualOverride: boolean = true
): Promise<MoodDetection> {
  if (!supabaseAdmin) {
    throw new Error('Database not available');
  }

  // Detect mood
  const detection = await detectMood(audioPath);

  // Store in database
  const { error } = await supabaseAdmin
    .from('tracks')
    .update({
      mood: detection.mood,
      updated_at: new Date().toISOString(),
    })
    .eq('id', trackId);

  if (error) {
    console.error('Failed to store mood detection:', error);
    throw error;
  }

  return detection;
}

/**
 * Get mood confidence score
 */
export function getMoodConfidenceScore(detection: MoodDetection): number {
  return Math.round(detection.confidence * 100);
}

/**
 * Get mood descriptors
 */
export function getMoodDescriptors(mood: MoodType): string[] {
  const descriptorMap: Record<MoodType, string[]> = {
    happy: ['cheerful', 'uplifting', 'joyful', 'optimistic'],
    sad: ['sorrowful', 'melancholic', 'touching', 'emotional'],
    calm: ['peaceful', 'serene', 'relaxing', 'soothing'],
    energetic: ['dynamic', 'vibrant', 'intense', 'driving'],
    angry: ['aggressive', 'fierce', 'powerful', 'tense'],
    romantic: ['intimate', 'passionate', 'sensual', 'warm'],
    melancholic: ['introspective', 'wistful', 'nostalgic', 'reflective'],
  };

  return descriptorMap[mood] || [];
}
