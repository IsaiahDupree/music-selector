const SUPPORTED_FORMATS = ["mp3", "wav", "aac", "flac"];
const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100 MB

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

export function validateAudioFile(
  file: File
): ValidationResult {
  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    return {
      valid: false,
      error: `File size exceeds ${MAX_FILE_SIZE / (1024 * 1024)}MB limit`,
    };
  }

  // Check file type
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!extension || !SUPPORTED_FORMATS.includes(extension)) {
    return {
      valid: false,
      error: `Unsupported format. Supported: ${SUPPORTED_FORMATS.join(", ")}`,
    };
  }

  // Check MIME type
  const expectedMimeTypes = [
    "audio/mpeg",
    "audio/wav",
    "audio/aac",
    "audio/flac",
    "audio/x-wav",
    "audio/x-flac",
  ];
  if (!expectedMimeTypes.includes(file.type)) {
    return {
      valid: false,
      error: "Invalid audio file MIME type",
    };
  }

  return { valid: true };
}

export function getAudioFileExtension(mimeType: string): string {
  const mimeToExt: Record<string, string> = {
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/aac": "aac",
    "audio/flac": "flac",
    "audio/x-wav": "wav",
    "audio/x-flac": "flac",
  };
  return mimeToExt[mimeType] || "audio";
}
