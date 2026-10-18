import { execSync } from "child_process";
import { access, constants } from "fs/promises";

export interface AudioMetadata {
  duration: number; // seconds
  bitrate: number; // kbps
  codec: string;
  sampleRate: number; // Hz
  channels: number;
  format: string;
  fileSize: number; // bytes
}

/**
 * Extract audio metadata using FFmpeg
 * Requires FFmpeg to be installed on the system
 *
 * @param filePath Path to audio file
 * @returns Audio metadata
 * @throws Error if FFmpeg not found or file cannot be read
 */
export async function extractAudioMetadata(
  filePath: string
): Promise<AudioMetadata> {
  // Check if FFmpeg is available
  try {
    execSync("which ffmpeg", { stdio: "ignore" });
  } catch {
    throw new Error(
      "FFmpeg not found. Install it with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
    );
  }

  // Verify file exists and is readable
  try {
    await access(filePath, constants.R_OK);
  } catch {
    throw new Error(`Audio file not readable: ${filePath}`);
  }

  try {
    // Run FFmpeg to extract metadata
    const output = execSync(
      `ffprobe -v error -show_format -show_streams -print_format json "${filePath}"`,
      { encoding: "utf-8" }
    );

    const probe = JSON.parse(output);

    if (!probe.streams || probe.streams.length === 0) {
      throw new Error("No audio streams found in file");
    }

    const audioStream = probe.streams.find(
      (s: any) => s.codec_type === "audio"
    );
    if (!audioStream) {
      throw new Error("No audio stream found in file");
    }

    const format = probe.format || {};

    // Parse metadata
    const metadata: AudioMetadata = {
      duration: Math.round(parseFloat(format.duration || "0")),
      bitrate: Math.round(
        (parseFloat(format.bit_rate || "0") || audioStream.bit_rate || 0) /
          1000
      ),
      codec: audioStream.codec_name || "unknown",
      sampleRate: audioStream.sample_rate || 44100,
      channels: audioStream.channels || 2,
      format: getAudioFormat(format.format_name || ""),
      fileSize: parseInt(format.size || "0"),
    };

    return metadata;
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`Failed to extract metadata: ${error.message}`);
    }
    throw error;
  }
}

/**
 * Parse audio format from FFprobe format name
 * @param formatName Format name from FFprobe
 * @returns Normalized format string
 */
function getAudioFormat(formatName: string): string {
  const formats: Record<string, string> = {
    "mp3,mpga": "MP3",
    "wav": "WAV",
    "aac": "AAC",
    "flac": "FLAC",
    "ogg": "OGG",
    "m4a": "M4A",
    "wma": "WMA",
  };

  const normalized = formatName.toLowerCase().split(",")[0];

  for (const [key, value] of Object.entries(formats)) {
    if (key.includes(normalized)) {
      return value;
    }
  }

  return formatName.toUpperCase() || "UNKNOWN";
}

/**
 * Estimate energy level based on audio characteristics
 * Uses loudness and dynamic range as proxies
 *
 * @param bitrate Audio bitrate in kbps
 * @param sampleRate Sample rate in Hz
 * @return Energy level from 0 to 1
 */
export function estimateEnergyLevel(
  bitrate: number,
  sampleRate: number
): number {
  // Simple heuristic: higher bitrate and sample rate suggest higher quality
  // and potentially more dynamic/energetic content
  // This is a placeholder - full implementation would analyze actual audio

  const bitrateScore = Math.min(bitrate / 320, 1); // Normalize to max 320kbps
  const sampleRateScore = Math.min(sampleRate / 48000, 1); // Normalize to 48kHz

  // Average the scores
  const energy = (bitrateScore + sampleRateScore) / 2;

  // Clamp between 0 and 1
  return Math.max(0, Math.min(1, energy));
}

/**
 * Validate audio metadata meets quality standards
 * @param metadata Audio metadata to validate
 * @returns Validation errors (empty if valid)
 */
export function validateAudioMetadata(metadata: AudioMetadata): string[] {
  const errors: string[] = [];

  if (metadata.duration <= 0) {
    errors.push("Duration must be greater than 0");
  }

  if (metadata.duration > 600) {
    // 10 minutes max
    errors.push("Duration exceeds maximum 10 minutes");
  }

  if (!metadata.codec) {
    errors.push("Codec not detected");
  }

  if (metadata.sampleRate < 8000) {
    errors.push("Sample rate too low (minimum 8000 Hz)");
  }

  if (metadata.channels < 1 || metadata.channels > 8) {
    errors.push("Invalid number of channels");
  }

  if (metadata.fileSize <= 0) {
    errors.push("File size not detected");
  }

  return errors;
}

/**
 * Format metadata for display
 * @param metadata Audio metadata
 * @returns Formatted metadata object
 */
export function formatMetadataForDisplay(metadata: AudioMetadata): Record<
  string,
  string | number
> {
  return {
    duration: `${Math.floor(metadata.duration / 60)}:${(metadata.duration % 60)
      .toString()
      .padStart(2, "0")}`,
    bitrate: `${metadata.bitrate} kbps`,
    codec: metadata.codec,
    sampleRate: `${metadata.sampleRate / 1000} kHz`,
    channels: metadata.channels === 1 ? "Mono" : `${metadata.channels}ch`,
    format: metadata.format,
    fileSize: `${(metadata.fileSize / 1024 / 1024).toFixed(2)} MB`,
  };
}

/**
 * Check if FFmpeg is installed
 * @returns true if ffprobe and ffmpeg are available
 */
export async function checkFFmpegInstalled(): Promise<boolean> {
  try {
    execSync("which ffmpeg", { stdio: "ignore" });
    execSync("which ffprobe", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}
