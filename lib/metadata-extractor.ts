import { AudioMetadata } from "./audio-metadata";

/**
 * Extract metadata from audio file buffer by reading file headers
 * This is a fallback method that works without FFmpeg
 *
 * @param buffer Audio file buffer
 * @param mimeType Audio file MIME type
 * @returns Estimated metadata
 */
export function extractMetadataFromBuffer(
  buffer: Uint8Array,
  mimeType: string
): Partial<AudioMetadata> {
  const metadata: Partial<AudioMetadata> = {
    format: getFormatFromMimeType(mimeType),
    channels: 2,
    sampleRate: 44100,
  };

  // Try to extract format-specific metadata from file headers
  if (mimeType.includes("mp3")) {
    extractMP3Metadata(buffer, metadata);
  } else if (mimeType.includes("wav")) {
    extractWAVMetadata(buffer, metadata);
  } else if (mimeType.includes("aac") || mimeType.includes("m4a")) {
    extractAACMetadata(buffer, metadata);
  } else if (mimeType.includes("flac")) {
    extractFLACMetadata(buffer, metadata);
  }

  return metadata;
}

/**
 * Extract metadata from MP3 file header
 * Reads ID3 tags and frame headers
 */
function extractMP3Metadata(
  buffer: Uint8Array,
  metadata: Partial<AudioMetadata>
): void {
  // Read first frame to estimate bitrate
  let offset = 0;

  // Skip ID3v2 tag if present
  if (buffer[0] === 0x49 && buffer[1] === 0x44 && buffer[2] === 0x33) {
    // ID3v2 header: "ID3"
    const size =
      ((buffer[6] & 0x7f) << 21) |
      ((buffer[7] & 0x7f) << 14) |
      ((buffer[8] & 0x7f) << 7) |
      (buffer[9] & 0x7f);
    offset = size + 10;
  }

  // Find first MP3 frame (0xFB or 0xFA as first byte, 0xE0+ as second)
  for (let i = offset; i < Math.min(offset + 10000, buffer.length - 3); i++) {
    if (
      (buffer[i] === 0xff || buffer[i] === 0xfb || buffer[i] === 0xfa) &&
      (buffer[i + 1] & 0xe0) === 0xe0
    ) {
      // Found frame sync
      const mpegVersion = (buffer[i + 1] >> 3) & 0x3; // 0=2.5, 1=?, 2=2, 3=1
      const bitrateIndex = (buffer[i + 2] >> 4) & 0xf;
      const samplerateIndex = (buffer[i + 2] >> 2) & 0x3;

      // Bitrate lookup table (in kbps)
      const bitrates = [
        [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
        [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
      ];
      const samplerates = [11025, 12000, 8000];

      if (bitrateIndex > 0 && bitrateIndex < 15) {
        const isV1 = mpegVersion === 3;
        metadata.bitrate = bitrates[isV1 ? 0 : 1][bitrateIndex];
        metadata.sampleRate = samplerates[samplerateIndex];
      }

      break;
    }
  }

  // Default to reasonable estimates if not extracted
  if (!metadata.bitrate) {
    metadata.bitrate = 128;
  }
  if (!metadata.sampleRate) {
    metadata.sampleRate = 44100;
  }
}

/**
 * Extract metadata from WAV file header
 * Reads RIFF/WAVE header
 */
function extractWAVMetadata(
  buffer: Uint8Array,
  metadata: Partial<AudioMetadata>
): void {
  // WAV header: "RIFF" at offset 0, "WAVE" at offset 8
  if (buffer.length < 44) return;

  // Read format chunk (starts at offset 12 usually)
  let offset = 12;
  while (offset + 8 < buffer.length) {
    const chunkId = String.fromCharCode(
      buffer[offset],
      buffer[offset + 1],
      buffer[offset + 2],
      buffer[offset + 3]
    );

    if (chunkId === "fmt ") {
      // Audio format chunk found
      const audioFormat = buffer[offset + 8] + (buffer[offset + 9] << 8); // 1 = PCM
      const numChannels = buffer[offset + 12] + (buffer[offset + 13] << 8);
      const sampleRate =
        buffer[offset + 16] +
        (buffer[offset + 17] << 8) +
        (buffer[offset + 18] << 16) +
        (buffer[offset + 19] << 24);
      const byteRate =
        buffer[offset + 24] +
        (buffer[offset + 25] << 8) +
        (buffer[offset + 26] << 16) +
        (buffer[offset + 27] << 24);

      metadata.channels = numChannels;
      metadata.sampleRate = sampleRate;
      metadata.bitrate = Math.round((byteRate * 8) / 1000); // Convert to kbps

      return;
    }

    // Move to next chunk
    const chunkSize =
      buffer[offset + 4] +
      (buffer[offset + 5] << 8) +
      (buffer[offset + 6] << 16) +
      (buffer[offset + 7] << 24);
    offset += 8 + chunkSize;
  }
}

/**
 * Extract metadata from AAC/M4A file (simplified)
 */
function extractAACMetadata(
  buffer: Uint8Array,
  metadata: Partial<AudioMetadata>
): void {
  // M4A/AAC files are complex; use reasonable defaults
  // A proper implementation would parse the 'moov' atom
  metadata.bitrate = 256; // Common AAC bitrate
  metadata.sampleRate = 44100;
  metadata.channels = 2;
}

/**
 * Extract metadata from FLAC file
 */
function extractFLACMetadata(
  buffer: Uint8Array,
  metadata: Partial<AudioMetadata>
): void {
  // FLAC header: "fLaC" at offset 0
  if (buffer.length < 34) return;

  // Metadata block header starts at offset 4
  // Byte 4-7: min/max block size info
  const minBlockSize = (buffer[4] << 8) + buffer[5];
  const maxBlockSize = (buffer[6] << 8) + buffer[7];
  const sampleRate =
    ((buffer[10] << 12) | (buffer[11] << 4) | (buffer[12] >> 4)) & 0xfffff;
  const channels = (((buffer[12] & 0x0f) >> 1) & 0x07) + 1;

  metadata.sampleRate = sampleRate;
  metadata.channels = channels;
  metadata.bitrate = 320; // Conservative estimate for FLAC
}

/**
 * Get format string from MIME type
 */
function getFormatFromMimeType(mimeType: string): string {
  if (mimeType.includes("mp3")) return "MP3";
  if (mimeType.includes("wav")) return "WAV";
  if (mimeType.includes("aac")) return "AAC";
  if (mimeType.includes("flac")) return "FLAC";
  if (mimeType.includes("ogg")) return "OGG";
  if (mimeType.includes("m4a")) return "M4A";
  return "UNKNOWN";
}

/**
 * Estimate duration from file size and bitrate
 * @param fileSize File size in bytes
 * @param bitrate Bitrate in kbps
 * @returns Estimated duration in seconds
 */
export function estimateDuration(
  fileSize: number,
  bitrate: number
): number {
  if (bitrate <= 0) return 0;
  // duration = (fileSize in bits) / (bitrate in bits per second)
  // = (fileSize * 8) / (bitrate * 1000)
  return Math.round((fileSize * 8) / (bitrate * 1000));
}
