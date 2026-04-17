/**
 * Energy Analyzer
 * Audio energy level analysis and classification
 */

import { supabaseAdmin } from './supabase';

export type EnergyLevel = 'low' | 'medium' | 'high';

export interface EnergyAnalysis {
  level: EnergyLevel;
  score: number; // 0-1
  metrics?: {
    rms: number; // Root mean square energy
    peakEnergy: number;
    averageEnergy: number;
    energyVariance: number;
  };
}

/**
 * Analyze audio energy level
 */
export async function analyzeEnergy(
  audioPath: string,
  audioData?: { bitrate?: number; codec?: string; sample_rate?: number }
): Promise<EnergyAnalysis> {
  // Calculate energy metrics
  const metrics = await calculateEnergyMetrics(audioPath, audioData);

  // Classify energy level
  return classifyEnergyLevel(metrics);
}

/**
 * Calculate energy metrics from audio
 */
async function calculateEnergyMetrics(
  audioPath: string,
  audioData?: { bitrate?: number; codec?: string; sample_rate?: number }
): Promise<{
  rms: number;
  peakEnergy: number;
  averageEnergy: number;
  energyVariance: number;
}> {
  // Placeholder energy calculation
  // In production would analyze actual audio waveform
  // RMS (Root Mean Square) = sqrt(mean of squared samples)

  const rms = Math.random() * 0.8; // 0-0.8 typical range
  const peakEnergy = rms + Math.random() * 0.2; // Peaks above RMS
  const averageEnergy = rms * 0.8;
  const energyVariance = Math.random() * 0.1; // How much energy varies

  return {
    rms,
    peakEnergy,
    averageEnergy,
    energyVariance,
  };
}

/**
 * Classify energy level from metrics
 */
function classifyEnergyLevel(metrics: {
  rms: number;
  peakEnergy: number;
  averageEnergy: number;
  energyVariance: number;
}): EnergyAnalysis {
  // Classify based on RMS energy
  // Low: RMS < 0.3
  // Medium: 0.3 <= RMS < 0.6
  // High: RMS >= 0.6

  let level: EnergyLevel;
  let score: number;

  if (metrics.rms < 0.3) {
    level = 'low';
    score = metrics.rms / 0.3; // 0-1 within low range
  } else if (metrics.rms < 0.6) {
    level = 'medium';
    score = (metrics.rms - 0.3) / 0.3; // 0-1 within medium range
  } else {
    level = 'high';
    score = Math.min(1, metrics.rms / 0.8); // 0-1 within high range
  }

  return {
    level,
    score,
    metrics,
  };
}

/**
 * Analyze and store energy level
 */
export async function analyzeAndStoreEnergy(
  trackId: string,
  audioPath: string
): Promise<EnergyAnalysis> {
  if (!supabaseAdmin) {
    throw new Error('Database not available');
  }

  // Analyze energy
  const analysis = await analyzeEnergy(audioPath);

  // Convert level to numeric for storage
  const energyLevelMap = { low: 0.33, medium: 0.67, high: 1.0 };
  const energyLevelValue = energyLevelMap[analysis.level];

  // Store in database
  const { error } = await supabaseAdmin
    .from('tracks')
    .update({
      energy_level: energyLevelValue,
      updated_at: new Date().toISOString(),
    })
    .eq('id', trackId);

  if (error) {
    console.error('Failed to store energy analysis:', error);
    throw error;
  }

  return analysis;
}

/**
 * Get energy level description
 */
export function getEnergyDescription(level: EnergyLevel): string {
  const descriptions: Record<EnergyLevel, string> = {
    low: 'Low energy - calm, ambient, introspective',
    medium: 'Medium energy - moderate, balanced, general use',
    high: 'High energy - intense, dynamic, uplifting',
  };

  return descriptions[level];
}

/**
 * Get energy level recommendations
 */
export function getEnergyRecommendations(
  level: EnergyLevel
): Array<{ context: string; suitability: string }> {
  const recommendations: Record<
    EnergyLevel,
    Array<{ context: string; suitability: string }>
  > = {
    low: [
      { context: 'Meditation/Relaxation', suitability: 'Excellent' },
      { context: 'Studying/Focus', suitability: 'Good' },
      { context: 'Sleep/Ambient', suitability: 'Excellent' },
      { context: 'Action/Gaming', suitability: 'Poor' },
    ],
    medium: [
      { context: 'Casual Videos', suitability: 'Excellent' },
      { context: 'Background Music', suitability: 'Excellent' },
      { context: 'Studying', suitability: 'Good' },
      { context: 'Action Scenes', suitability: 'Fair' },
    ],
    high: [
      { context: 'Action/Trailers', suitability: 'Excellent' },
      { context: 'Gaming', suitability: 'Excellent' },
      { context: 'Sports Videos', suitability: 'Excellent' },
      { context: 'Meditation', suitability: 'Poor' },
    ],
  };

  return recommendations[level] || [];
}

/**
 * Filter tracks by energy level
 */
export function filterByEnergyLevel(
  tracks: Array<{ energy_level: number | null }>,
  targetLevel: EnergyLevel
): Array<{ energy_level: number | null }> {
  const levelRanges: Record<EnergyLevel, { min: number; max: number }> = {
    low: { min: 0, max: 0.4 },
    medium: { min: 0.4, max: 0.7 },
    high: { min: 0.7, max: 1 },
  };

  const range = levelRanges[targetLevel];

  return tracks.filter(track => {
    if (track.energy_level === null || track.energy_level === undefined) {
      return false;
    }
    return track.energy_level >= range.min && track.energy_level <= range.max;
  });
}
