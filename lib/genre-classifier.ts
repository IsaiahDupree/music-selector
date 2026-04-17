/**
 * Genre Classifier
 * Automatic audio genre classification
 */

import { supabaseAdmin } from './supabase';

export interface GenreClassification {
  genre: string;
  confidence: number;
  alternatives?: Array<{ genre: string; confidence: number }>;
}

/**
 * Analyze audio and classify genre
 * In production, this would use ML models like Essentia or MusicCaps
 */
export async function classifyGenre(
  audioPath: string,
  audioData?: { bitrate?: number; codec?: string; sample_rate?: number }
): Promise<GenreClassification> {
  // Feature extraction placeholder
  // In production, would use audio analysis libraries
  const features = await extractAudioFeatures(audioPath, audioData);

  // Get genre prediction
  return predictGenreFromFeatures(features);
}

/**
 * Extract audio features for classification
 */
async function extractAudioFeatures(
  audioPath: string,
  audioData?: { bitrate?: number; codec?: string; sample_rate?: number }
): Promise<Record<string, number>> {
  // Placeholder feature extraction
  // In production, would analyze:
  // - Spectral features (MFCC, spectral centroid, etc.)
  // - Temporal features (RMS energy, zero crossing rate)
  // - Pitch and harmony information

  return {
    spectralCentroid: Math.random() * 10000,
    mfcc_mean: Math.random() * 100,
    zcrMean: Math.random() * 0.5,
    rmsMean: Math.random() * 1,
    tempoEstimate: 60 + Math.random() * 120,
  };
}

/**
 * Predict genre from extracted features
 */
function predictGenreFromFeatures(
  features: Record<string, number>
): GenreClassification {
  // Genre probability estimates based on audio characteristics
  const genreScores: Record<string, number> = {
    lofi: calculateGenreScore(features, 'lofi'),
    electronic: calculateGenreScore(features, 'electronic'),
    house: calculateGenreScore(features, 'house'),
    hip_hop: calculateGenreScore(features, 'hip_hop'),
    cinematic: calculateGenreScore(features, 'cinematic'),
    pop: calculateGenreScore(features, 'pop'),
    ambient: calculateGenreScore(features, 'ambient'),
  };

  // Get top genres
  const sorted = Object.entries(genreScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);

  const topGenre = sorted[0];
  const confidence = Math.min(0.99, topGenre[1] / 100);

  return {
    genre: topGenre[0],
    confidence,
    alternatives: sorted.slice(1).map(([genre, score]) => ({
      genre,
      confidence: Math.min(0.99, score / 100),
    })),
  };
}

/**
 * Calculate genre probability score
 */
function calculateGenreScore(
  features: Record<string, number>,
  genre: string
): number {
  // Simple scoring based on feature ranges
  // In production, would use trained ML model

  const spectralCentroid = features.spectralCentroid || 0;
  const tempoEstimate = features.tempoEstimate || 0;
  const rmsMean = features.rmsMean || 0;

  let score = 50; // Base score

  switch (genre) {
    case 'lofi':
      // Lower spectral content, chill tempo
      if (spectralCentroid < 5000) score += 20;
      if (tempoEstimate < 100) score += 15;
      break;

    case 'electronic':
      // Broader spectral range, moderate tempo
      score += 10;
      if (tempoEstimate > 100 && tempoEstimate < 140) score += 15;
      break;

    case 'house':
      // Higher tempo, consistent energy
      if (tempoEstimate > 120) score += 20;
      if (rmsMean > 0.6) score += 15;
      break;

    case 'hip_hop':
      // Varied tempo, percussive elements
      score += 10;
      if (tempoEstimate > 85 && tempoEstimate < 115) score += 15;
      break;

    case 'cinematic':
      // Broader frequency range, dynamic
      if (spectralCentroid > 4000) score += 15;
      score += 10;
      break;

    case 'pop':
      // Regular structure, moderate tempo
      if (tempoEstimate > 90 && tempoEstimate < 130) score += 20;
      break;

    case 'ambient':
      // Lower energy, sustained tones
      if (rmsMean < 0.4) score += 20;
      if (spectralCentroid < 6000) score += 15;
      break;
  }

  // Add randomness for realism (remove in production with real model)
  return score + (Math.random() * 20 - 10);
}

/**
 * Classify and store genre in database
 */
export async function classifyAndStoreGenre(
  trackId: string,
  audioPath: string,
  allowManualOverride: boolean = true
): Promise<GenreClassification> {
  if (!supabaseAdmin) {
    throw new Error('Database not available');
  }

  // Classify genre
  const classification = await classifyGenre(audioPath);

  // Store in database
  const { error } = await supabaseAdmin
    .from('tracks')
    .update({
      genre: classification.genre,
      updated_at: new Date().toISOString(),
    })
    .eq('id', trackId);

  if (error) {
    console.error('Failed to store genre classification:', error);
    throw error;
  }

  return classification;
}

/**
 * Get multi-label genre classifications
 */
export function classifyMultipleGenres(
  classification: GenreClassification,
  confidenceThreshold: number = 0.3
): string[] {
  const genres = [classification.genre];

  if (classification.alternatives) {
    genres.push(
      ...classification.alternatives
        .filter(alt => alt.confidence >= confidenceThreshold)
        .map(alt => alt.genre)
    );
  }

  return genres;
}
