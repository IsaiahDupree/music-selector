import { validateAudioFile, getAudioFileExtension } from "@/utils/audio-validation";

describe("Audio Validation", () => {
  describe("validateAudioFile", () => {
    it("should accept valid MP3 file", () => {
      const file = new File(["audio"], "song.mp3", { type: "audio/mpeg" });
      const result = validateAudioFile(file);
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it("should accept valid WAV file", () => {
      const file = new File(["audio"], "song.wav", { type: "audio/wav" });
      const result = validateAudioFile(file);
      expect(result.valid).toBe(true);
    });

    it("should reject unsupported format", () => {
      const file = new File(["text"], "song.txt", { type: "text/plain" });
      const result = validateAudioFile(file);
      expect(result.valid).toBe(false);
      expect(result.error).toContain("Unsupported format");
    });

    it("should reject files exceeding size limit", () => {
      const largeData = new ArrayBuffer(101 * 1024 * 1024);
      const file = new File([largeData], "large.mp3", { type: "audio/mpeg" });
      const result = validateAudioFile(file);
      expect(result.valid).toBe(false);
      expect(result.error).toContain("exceeds");
    });

    it("should reject files with wrong extension", () => {
      const file = new File(["audio"], "song.xyz", { type: "audio/mpeg" });
      const result = validateAudioFile(file);
      expect(result.valid).toBe(false);
      expect(result.error).toContain("Unsupported format");
    });
  });

  describe("getAudioFileExtension", () => {
    it("should return correct extension for audio/mpeg", () => {
      expect(getAudioFileExtension("audio/mpeg")).toBe("mp3");
    });

    it("should return correct extension for audio/wav", () => {
      expect(getAudioFileExtension("audio/wav")).toBe("wav");
    });

    it("should return correct extension for audio/aac", () => {
      expect(getAudioFileExtension("audio/aac")).toBe("aac");
    });

    it("should return default extension for unknown mime type", () => {
      expect(getAudioFileExtension("audio/unknown")).toBe("audio");
    });
  });
});
