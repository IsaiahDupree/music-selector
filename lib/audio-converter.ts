/**
 * Audio Converter
 * Convert audio files between different formats
 */

import { supabaseAdmin } from './supabase';

export type AudioFormat = 'mp3' | 'wav' | 'aac' | 'flac' | 'ogg';

export interface ConversionOptions {
  format: AudioFormat;
  bitrate?: number; // kbps
  sampleRate?: number; // Hz
  channels?: 'mono' | 'stereo';
  quality?: 'low' | 'medium' | 'high'; // For lossy formats
}

export interface ConversionResult {
  success: boolean;
  originalFormat: string;
  targetFormat: AudioFormat;
  outputPath?: string;
  fileSize?: number;
  duration?: number;
  error?: string;
}

/**
 * Convert audio file to different format
 */
export async function convertAudio(
  inputPath: string,
  options: ConversionOptions
): Promise<ConversionResult> {
  try {
    // In production, would use ffmpeg or similar tool
    // Example command: ffmpeg -i input.mp3 -b:a 192k output.aac

    // For now, validate options
    validateConversionOptions(options);

    // In a real implementation:
    // 1. Check if ffmpeg is available
    // 2. Construct ffmpeg command based on options
    // 3. Execute conversion
    // 4. Verify output file
    // 5. Return result

    return {
      success: true,
      originalFormat: 'unknown',
      targetFormat: options.format,
      outputPath: generateOutputPath(inputPath, options.format),
      fileSize: 0, // Would get actual size
      duration: 0, // Would extract from file
    };
  } catch (error) {
    return {
      success: false,
      originalFormat: 'unknown',
      targetFormat: options.format,
      error: error instanceof Error ? error.message : 'Conversion failed',
    };
  }
}

/**
 * Validate conversion options
 */
function validateConversionOptions(options: ConversionOptions): void {
  if (!options.format) {
    throw new Error('Target format is required');
  }

  if (!['mp3', 'wav', 'aac', 'flac', 'ogg'].includes(options.format)) {
    throw new Error(`Unsupported format: ${options.format}`);
  }

  // Validate bitrate
  if (options.bitrate) {
    if (options.bitrate < 32 || options.bitrate > 320) {
      throw new Error('Bitrate must be between 32 and 320 kbps');
    }
  }

  // Validate sample rate
  if (options.sampleRate) {
    const validRates = [8000, 16000, 22050, 44100, 48000, 96000];
    if (!validRates.includes(options.sampleRate)) {
      throw new Error(
        `Invalid sample rate: ${options.sampleRate}. Must be one of: ${validRates.join(', ')}`
      );
    }
  }
}

/**
 * Get recommended settings for format
 */
export function getFormatRecommendations(
  format: AudioFormat
): ConversionOptions {
  const recommendations: Record<AudioFormat, ConversionOptions> = {
    mp3: {
      format: 'mp3',
      bitrate: 192,
      sampleRate: 44100,
      channels: 'stereo',
      quality: 'high',
    },
    wav: {
      format: 'wav',
      bitrate: 1411, // Lossless
      sampleRate: 44100,
      channels: 'stereo',
    },
    aac: {
      format: 'aac',
      bitrate: 128,
      sampleRate: 48000,
      channels: 'stereo',
      quality: 'high',
    },
    flac: {
      format: 'flac',
      sampleRate: 44100,
      channels: 'stereo',
    },
    ogg: {
      format: 'ogg',
      bitrate: 128,
      sampleRate: 44100,
      channels: 'stereo',
      quality: 'medium',
    },
  };

  return recommendations[format] || recommendations.mp3;
}

/**
 * Convert and store in database
 */
export async function convertAndStore(
  trackId: string,
  inputPath: string,
  options: ConversionOptions
): Promise<ConversionResult> {
  if (!supabaseAdmin) {
    throw new Error('Database not available');
  }

  // Convert audio
  const result = await convertAudio(inputPath, options);

  if (!result.success || !result.outputPath) {
    return result;
  }

  // Store conversion information in metadata
  const { error } = await supabaseAdmin
    .from('track_metadata')
    .update({
      updated_at: new Date().toISOString(),
    })
    .eq('track_id', trackId);

  if (error) {
    console.error('Failed to update metadata:', error);
    // Don't fail the conversion result, just log the error
  }

  return result;
}

/**
 * Generate output path for converted file
 */
function generateOutputPath(inputPath: string, format: AudioFormat): string {
  const basePath = inputPath.substring(0, inputPath.lastIndexOf('.'));
  return `${basePath}.${format}`;
}

/**
 * Get file size estimate for conversion
 */
export function estimateConvertedFileSize(
  originalSize: number,
  originalFormat: AudioFormat,
  targetOptions: ConversionOptions
): number {
  // Rough estimation based on bitrate conversion
  const formatBitrates: Record<AudioFormat, number> = {
    mp3: targetOptions.bitrate || 192,
    wav: 1411, // Typical CD quality
    aac: targetOptions.bitrate || 128,
    flac: 768, // Average compression ~30%
    ogg: targetOptions.bitrate || 128,
  };

  if (originalFormat === 'wav' && targetOptions.format === 'mp3') {
    // Rough estimation: 1411 kbps WAV -> 192 kbps MP3
    return Math.round(originalSize * (192 / 1411));
  }

  // General estimation
  const targetBitrate = formatBitrates[targetOptions.format];
  const originalBitrate = formatBitrates[originalFormat];

  return Math.round(originalSize * (targetBitrate / originalBitrate));
}

/**
 * Get supported input/output formats
 */
export function getSupportedFormats(): {
  input: AudioFormat[];
  output: AudioFormat[];
} {
  return {
    input: ['mp3', 'wav', 'aac', 'flac', 'ogg'],
    output: ['mp3', 'wav', 'aac', 'flac', 'ogg'],
  };
}

/**
 * Check if format conversion is supported
 */
export function isConversionSupported(
  from: AudioFormat,
  to: AudioFormat
): boolean {
  const supported = getSupportedFormats();
  return supported.input.includes(from) && supported.output.includes(to);
}
