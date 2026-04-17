"use client";

import { useState, useEffect } from "react";
import TrackCard from "./TrackCard";
import type { Track } from "@/lib/supabase";

interface LibraryViewProps {
  onSelectTrack?: (track: Track) => void;
}

export default function LibraryView({ onSelectTrack }: LibraryViewProps) {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [sortBy, setSortBy] = useState<string>("created_at");
  const [filters, setFilters] = useState({
    genre: "",
    mood: "",
    minDuration: "",
    maxDuration: "",
  });

  const fetchTracks = async () => {
    try {
      setIsLoading(true);
      const params = new URLSearchParams();

      if (filters.genre) params.append("genre", filters.genre);
      if (filters.mood) params.append("mood", filters.mood);
      if (filters.minDuration) params.append("minDuration", filters.minDuration);
      if (filters.maxDuration) params.append("maxDuration", filters.maxDuration);

      const response = await fetch(`/api/tracks?${params.toString()}`);
      if (!response.ok) throw new Error("Failed to fetch tracks");

      const data = await response.json();
      setTracks(data.tracks);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTracks();
  }, [filters]);

  const handleSelectTrack = (id: string) => {
    const track = tracks.find(t => t.id === id);
    if (track) {
      onSelectTrack?.(track);
    }
  };

  if (isLoading) {
    return <div style={styles.center}>Loading tracks...</div>;
  }

  return (
    <div style={styles.container}>
      <div style={styles.controls}>
        <div style={styles.controlGroup}>
          <button
            onClick={() => setViewMode("grid")}
            style={{
              ...styles.button,
              backgroundColor: viewMode === "grid" ? "#007bff" : "#ddd",
              color: viewMode === "grid" ? "white" : "black",
            }}
          >
            Grid
          </button>
          <button
            onClick={() => setViewMode("list")}
            style={{
              ...styles.button,
              backgroundColor: viewMode === "list" ? "#007bff" : "#ddd",
              color: viewMode === "list" ? "white" : "black",
            }}
          >
            List
          </button>
        </div>

        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          style={styles.select}
        >
          <option value="created_at">Recently Added</option>
          <option value="title">Title</option>
          <option value="artist">Artist</option>
          <option value="duration_sec">Duration</option>
        </select>
      </div>

      <div style={styles.filters}>
        <select
          value={filters.genre}
          onChange={e => setFilters({ ...filters, genre: e.target.value })}
          style={styles.select}
        >
          <option value="">All Genres</option>
          <option value="lofi">Lo-fi</option>
          <option value="electronic">Electronic</option>
          <option value="house">House</option>
          <option value="hip_hop">Hip Hop</option>
          <option value="cinematic">Cinematic</option>
          <option value="pop">Pop</option>
          <option value="ambient">Ambient</option>
        </select>

        <select
          value={filters.mood}
          onChange={e => setFilters({ ...filters, mood: e.target.value })}
          style={styles.select}
        >
          <option value="">All Moods</option>
          <option value="calm">Calm</option>
          <option value="energetic">Energetic</option>
          <option value="happy">Happy</option>
          <option value="inspiring">Inspiring</option>
          <option value="dramatic">Dramatic</option>
        </select>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {tracks.length === 0 ? (
        <div style={styles.center}>No tracks found</div>
      ) : (
        <div
          style={
            viewMode === "grid" ? styles.gridContainer : styles.listContainer
          }
        >
          {tracks.map(track => (
            <TrackCard
              key={track.id}
              {...track}
              onSelect={handleSelectTrack}
            />
          ))}
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    padding: "20px",
  },
  controls: {
    display: "flex",
    gap: "16px",
    marginBottom: "20px",
    alignItems: "center",
  },
  controlGroup: {
    display: "flex",
    gap: "8px",
  },
  button: {
    padding: "8px 16px",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
  },
  select: {
    padding: "8px 12px",
    borderRadius: "4px",
    border: "1px solid #ddd",
    cursor: "pointer",
  },
  filters: {
    display: "flex",
    gap: "12px",
    marginBottom: "20px",
    flexWrap: "wrap" as const,
  },
  gridContainer: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
    gap: "16px",
  },
  listContainer: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "12px",
  },
  center: {
    textAlign: "center" as const,
    padding: "40px",
    color: "#666",
  },
  error: {
    backgroundColor: "#fee",
    color: "#c00",
    padding: "12px",
    borderRadius: "4px",
    marginBottom: "16px",
  },
};
