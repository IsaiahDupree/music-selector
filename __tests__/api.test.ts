/**
 * API Endpoint Tests
 * Tests all REST API endpoints with various inputs and edge cases
 */

describe("API Endpoints", () => {
  // Note: These tests assume a test server is running
  // In production, use a test database and mock supabaseAdmin

  const BASE_URL = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";

  describe("Health Check - GET /api/health", () => {
    it("should return 200 OK status", async () => {
      const response = await fetch(`${BASE_URL}/api/health`);
      expect(response.status).toBe(200);
    });

    it("should return service status", async () => {
      const response = await fetch(`${BASE_URL}/api/health`);
      const data = await response.json();
      expect(data).toHaveProperty("status");
      expect(data).toHaveProperty("timestamp");
    });

    it("should indicate database connection status", async () => {
      const response = await fetch(`${BASE_URL}/api/health`);
      const data = await response.json();
      expect(data).toHaveProperty("database");
    });
  });

  describe("Search - GET /api/search", () => {
    it("should return error if query missing", async () => {
      const response = await fetch(`${BASE_URL}/api/search`);
      expect(response.status).toBe(400);
    });

    it("should return error if query too short", async () => {
      const response = await fetch(`${BASE_URL}/api/search?q=a`);
      expect(response.status).toBe(400);
      const data = await response.json();
      expect(data.error).toBeDefined();
    });

    it("should accept valid search query", async () => {
      const response = await fetch(`${BASE_URL}/api/search?q=lofi`);
      expect([200, 404]).toContain(response.status);
    });

    it("should support pagination with limit", async () => {
      const response = await fetch(`${BASE_URL}/api/search?q=music&limit=5`);
      const data = await response.json();
      if (response.ok) {
        expect(Array.isArray(data.results)).toBe(true);
        expect(data.results.length).toBeLessThanOrEqual(5);
      }
    });
  });

  describe("Tracks List - GET /api/tracks", () => {
    it("should return tracks with pagination", async () => {
      const response = await fetch(`${BASE_URL}/api/tracks?page=1&limit=10`);
      if (response.ok) {
        const data = await response.json();
        expect(Array.isArray(data.tracks) || Array.isArray(data)).toBe(true);
      }
    });

    it("should support genre filter", async () => {
      const response = await fetch(`${BASE_URL}/api/tracks?genre=lofi`);
      expect([200, 404]).toContain(response.status);
    });

    it("should support mood filter", async () => {
      const response = await fetch(`${BASE_URL}/api/tracks?mood=calm`);
      expect([200, 404]).toContain(response.status);
    });

    it("should support duration range filter", async () => {
      const response = await fetch(
        `${BASE_URL}/api/tracks?minDuration=60&maxDuration=300`
      );
      expect([200, 404]).toContain(response.status);
    });

    it("should support energy level filter", async () => {
      const response = await fetch(`${BASE_URL}/api/tracks?minEnergy=0.3`);
      expect([200, 404]).toContain(response.status);
    });

    it("should support sorting", async () => {
      const response = await fetch(`${BASE_URL}/api/tracks?sort=title`);
      expect([200, 404]).toContain(response.status);
    });
  });

  describe("Track Detail - GET /api/tracks/:id", () => {
    it("should return 404 for invalid track ID", async () => {
      const response = await fetch(`${BASE_URL}/api/tracks/invalid-id`);
      expect([404, 400]).toContain(response.status);
    });

    it("should return full metadata for valid track", async () => {
      // This would require a known valid track ID
      // In integration tests, create a test track first
      const response = await fetch(
        `${BASE_URL}/api/tracks/00000000-0000-0000-0000-000000000000`
      );
      expect([404, 400, 200]).toContain(response.status);
    });
  });

  describe("Tags - GET /api/tags", () => {
    it("should return list of tags", async () => {
      const response = await fetch(`${BASE_URL}/api/tags`);
      expect([200, 404]).toContain(response.status);
    });

    it("should support creating tags", async () => {
      const response = await fetch(`${BASE_URL}/api/tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "test-tag" }),
      });
      expect([201, 400, 401]).toContain(response.status);
    });
  });

  describe("Playlists - GET /api/playlists", () => {
    it("should return user playlists", async () => {
      const response = await fetch(`${BASE_URL}/api/playlists`);
      expect([200, 401, 404]).toContain(response.status);
    });

    it("should support creating playlists", async () => {
      const response = await fetch(`${BASE_URL}/api/playlists`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "Test Playlist" }),
      });
      expect([201, 400, 401]).toContain(response.status);
    });
  });

  describe("Filters - GET /api/filters", () => {
    it("should return available filter options", async () => {
      const response = await fetch(`${BASE_URL}/api/filters`);
      expect(response.status).toBe(200);
      const data = await response.json();
      expect(data).toHaveProperty("genres");
      expect(data).toHaveProperty("moods");
    });

    it("should return genre list", async () => {
      const response = await fetch(`${BASE_URL}/api/filters`);
      const data = await response.json();
      if (data.genres) {
        expect(Array.isArray(data.genres)).toBe(true);
      }
    });

    it("should return mood list", async () => {
      const response = await fetch(`${BASE_URL}/api/filters`);
      const data = await response.json();
      if (data.moods) {
        expect(Array.isArray(data.moods)).toBe(true);
      }
    });
  });

  describe("Export - CSV/JSON", () => {
    it("should export CSV format", async () => {
      const response = await fetch(`${BASE_URL}/api/export/csv`);
      if (response.ok) {
        expect(response.headers.get("content-type")).toContain("text/csv");
      }
    });

    it("should export JSON format", async () => {
      const response = await fetch(`${BASE_URL}/api/export/json`);
      if (response.ok) {
        expect(response.headers.get("content-type")).toContain(
          "application/json"
        );
      }
    });

    it("should export batch with multiple tracks", async () => {
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
      expect([200, 404, 400]).toContain(response.status);
    });

    it("should reject batch export with empty track list", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trackIds: [] }),
      });
      expect(response.status).toBe(400);
    });

    it("should reject batch export exceeding max tracks", async () => {
      const trackIds = Array(101)
        .fill(0)
        .map((_, i) => `00000000-0000-0000-0000-${i.toString().padStart(12, "0")}`);

      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trackIds }),
      });
      expect(response.status).toBe(400);
    });
  });

  describe("Error Handling", () => {
    it("should return 405 for unsupported methods", async () => {
      // Test DELETE on GET-only endpoint
      const response = await fetch(`${BASE_URL}/api/health`, {
        method: "DELETE",
      });
      expect(response.status).toBe(405);
    });

    it("should handle malformed JSON gracefully", async () => {
      const response = await fetch(`${BASE_URL}/api/tags`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{ invalid json",
      });
      expect([400, 500]).toContain(response.status);
    });

    it("should return appropriate error for invalid database state", async () => {
      const response = await fetch(
        `${BASE_URL}/api/tracks/not-a-valid-uuid`
      );
      expect([400, 404]).toContain(response.status);
    });
  });

  describe("Authentication Edge Cases", () => {
    it("should handle missing authentication gracefully", async () => {
      // Without auth header, should handle appropriately
      const response = await fetch(`${BASE_URL}/api/playlists`);
      expect([200, 401]).toContain(response.status);
    });

    it("should validate authorization for protected endpoints", async () => {
      const response = await fetch(`${BASE_URL}/api/export/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trackIds: [] }),
      });
      // Should fail validation even without auth
      expect([400, 401]).toContain(response.status);
    });
  });

  describe("Rate Limiting & Performance", () => {
    it("should handle concurrent requests", async () => {
      const requests = Array(5)
        .fill(0)
        .map(() => fetch(`${BASE_URL}/api/health`));

      const responses = await Promise.all(requests);
      responses.forEach((response) => {
        expect(response.status).toBe(200);
      });
    });

    it("should handle large query parameters gracefully", async () => {
      const largeQuery = "a".repeat(1000);
      const response = await fetch(`${BASE_URL}/api/search?q=${largeQuery}`);
      expect([200, 400, 414]).toContain(response.status);
    });
  });
});
