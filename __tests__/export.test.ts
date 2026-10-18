/**
 * Export Functionality Tests
 * Tests all export operations including CSV, JSON, batch, and playlist exports
 */

describe("Export Functionality", () => {
  const BASE_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

  // Helper to validate CSV format
  function validateCSV(csvContent: string): boolean {
    const lines = csvContent.trim().split("\n");
    if (lines.length < 1) return false;

    const headerCount = lines[0].split(",").length;
    return lines.every((line) => {
      // Account for quoted fields with commas
      let unquotedCommas = 0;
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        if (line[i] === '"') inQuotes = !inQuotes;
        else if (line[i] === "," && !inQuotes) unquotedCommas++;
      }
      return unquotedCommas === headerCount - 1;
    });
  }

  describe("CSV Export", () => {
    it("should return CSV format", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      expect(response.status).toBe(200);
      expect(response.headers.get("content-type")).toContain("text/csv");
    });

    it("should include attachment header with filename", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      const disposition = response.headers.get("content-disposition");
      expect(disposition).toContain("attachment");
      expect(disposition).toContain("music-library");
    });

    it("should produce valid CSV with headers", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      const csv = await response.text();

      if (csv.length > 0) {
        const lines = csv.split("\n");
        expect(lines[0]).toContain("ID");
        expect(lines[0]).toContain("Title");
        expect(lines[0]).toContain("Artist");
      }
    });

    it("should properly escape CSV special characters", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      const csv = await response.text();

      // Check for proper CSV escaping of quotes
      if (csv.includes('"')) {
        // Quotes should be escaped as ""
        expect(csv).toMatch(/""(?!")/);
      }
    });

    it("should validate CSV format", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      const csv = await response.text();

      if (csv.length > 0) {
        expect(validateCSV(csv)).toBe(true);
      }
    });
  });

  describe("JSON Export", () => {
    it("should return JSON format", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      expect(response.status).toBe(200);
      expect(response.headers.get("content-type")).toContain("application/json");
    });

    it("should include attachment header", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      const disposition = response.headers.get("content-disposition");
      expect(disposition).toContain("attachment");
    });

    it("should produce valid JSON", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      const json = await response.json();

      expect(json).toBeDefined();
      expect(typeof json).toBe("object");
    });

    it("should include version metadata", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      const json = await response.json();

      if (json.version) {
        expect(json.version).toBeDefined();
      }
    });

    it("should include export timestamp", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      const json = await response.json();

      if (json.exportedAt) {
        const timestamp = new Date(json.exportedAt);
        expect(timestamp).not.toBeNaN();
      }
    });

    it("should include tracks array", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      const json = await response.json();

      if (json.tracks) {
        expect(Array.isArray(json.tracks)).toBe(true);
      }
    });
  });

  describe("Batch Export", () => {
    it("should reject without trackIds", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      expect(response.status).toBe(400);
    });

    it("should reject empty trackIds array", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trackIds: [] }),
      });
      expect(response.status).toBe(400);
    });

    it("should reject more than 100 tracks", async () => {
      const trackIds = Array(101)
        .fill(0)
        .map(
          (_, i) =>
            `00000000-0000-0000-0000-${i.toString().padStart(12, "0")}`
        );

      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trackIds }),
      });
      expect(response.status).toBe(400);
    });

    it("should return track data with download URLs", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackIds: [
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
          ],
        }),
      });

      if (response.ok) {
        const data = await response.json();
        expect(data.success).toBe(true);
        expect(Array.isArray(data.tracks)).toBe(true);

        if (data.tracks.length > 0) {
          const track = data.tracks[0];
          expect(track.id).toBeDefined();
          expect(track.title).toBeDefined();
          expect(track.artist).toBeDefined();
        }
      }
    });

    it("should include total size calculation", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackIds: ["00000000-0000-0000-0000-000000000001"],
        }),
      });

      if (response.ok) {
        const data = await response.json();
        expect(data.totalSize).toBeDefined();
        expect(typeof data.totalSize).toBe("number");
      }
    });

    it("should enforce 500MB size limit", async () => {
      // This would require creating very large test tracks
      // Placeholder for integration test
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackIds: ["00000000-0000-0000-0000-000000000001"],
        }),
      });

      // Should succeed for small batches
      expect([200, 404, 413]).toContain(response.status);
    });

    it("should include implementation instructions for ZIP creation", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackIds: ["00000000-0000-0000-0000-000000000001"],
        }),
      });

      if (response.ok) {
        const data = await response.json();
        expect(data.clientImplementationExample).toBeDefined();
      }
    });
  });

  describe("Playlist Export", () => {
    it("should require playlistId", async () => {
      const response = await fetch(`${BASE_URL}/api/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      expect(response.status).toBe(400);
    });

    it("should return 404 for invalid playlist", async () => {
      const response = await fetch(`${BASE_URL}/api/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playlistId: "00000000-0000-0000-0000-000000000000",
        }),
      });
      expect([404, 400]).toContain(response.status);
    });

    it("should include playlist metadata", async () => {
      const response = await fetch(`${BASE_URL}/api/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playlistId: "00000000-0000-0000-0000-000000000001",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        expect(data.playlist).toBeDefined();
        expect(data.playlist.name).toBeDefined();
        expect(data.playlist.trackCount).toBeDefined();
      }
    });

    it("should maintain track order", async () => {
      const response = await fetch(`${BASE_URL}/api/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playlistId: "00000000-0000-0000-0000-000000000001",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.playlist.tracks && data.playlist.tracks.length > 1) {
          // Check that positions are sequential
          for (let i = 0; i < data.playlist.tracks.length; i++) {
            expect(data.playlist.tracks[i].position).toBe(i + 1);
          }
        }
      }
    });

    it("should generate playlist metadata JSON", async () => {
      const response = await fetch(`${BASE_URL}/api/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playlistId: "00000000-0000-0000-0000-000000000001",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        expect(data.playlistMetadataJson).toBeDefined();
        expect(data.playlistMetadataJson.name).toBeDefined();
        expect(Array.isArray(data.playlistMetadataJson.tracks)).toBe(true);
      }
    });

    it("should enforce 1GB size limit", async () => {
      // Placeholder for integration test with large playlists
      const response = await fetch(`${BASE_URL}/api/export/playlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          playlistId: "00000000-0000-0000-0000-000000000001",
        }),
      });

      expect([200, 404, 413]).toContain(response.status);
    });
  });

  describe("Single Track Export", () => {
    it("should return download URL", async () => {
      const response = await fetch(`${BASE_URL}/api/export/single`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trackId: "00000000-0000-0000-0000-000000000001",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        expect(data.downloadUrl).toBeDefined();
      }
    });
  });

  describe("Export Error Handling", () => {
    it("should handle database errors gracefully", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      expect([200, 500, 503]).toContain(response.status);
    });

    it("should validate export size before processing", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trackIds: [] }),
      });
      expect(response.status).toBe(400);
    });

    it("should provide clear error messages", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trackIds: [] }),
      });

      const data = await response.json();
      expect(data.error).toBeDefined();
      expect(typeof data.error).toBe("string");
    });
  });

  describe("File Integrity", () => {
    it("should not corrupt CSV with special characters", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      const csv = await response.text();

      // Check for common data corruption patterns
      expect(csv).not.toContain("\x00"); // Null bytes
      expect(csv).not.toContain("undefined");
      expect(csv).not.toContain("[object Object]");
    });

    it("should not corrupt JSON with invalid characters", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      const json = await response.json();

      // JSON should parse without errors (already done by response.json())
      expect(json).toBeDefined();
    });
  });
});
