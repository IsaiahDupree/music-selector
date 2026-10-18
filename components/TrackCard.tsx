"use client";

interface TrackCardProps {
  id: string;
  title: string;
  artist?: string | null;
  genre?: string | null;
  mood?: string | null;
  energy_level?: number | null;
  duration_sec?: number | null;
  is_trending?: boolean;
  onSelect?: (id: string) => void;
}

export default function TrackCard({
  id,
  title,
  artist,
  genre,
  mood,
  energy_level,
  duration_sec,
  is_trending,
  onSelect,
}: TrackCardProps) {
  const formatDuration = (seconds?: number | null) => {
    if (!seconds) return "?";
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div
      style={styles.card}
      onClick={() => onSelect?.(id)}
      role="button"
      tabIndex={0}
    >
      <div style={styles.header}>
        <h3 style={styles.title}>{title}</h3>
        {is_trending && <span style={styles.badge}>🔥 Trending</span>}
      </div>

      {artist && <p style={styles.artist}>{artist}</p>}

      <div style={styles.metadata}>
        {genre && <span style={styles.tag}>{genre}</span>}
        {mood && <span style={styles.tag}>{mood}</span>}
        {duration_sec && (
          <span style={styles.tag}>{formatDuration(duration_sec)}</span>
        )}
      </div>

      {energy_level !== undefined && energy_level !== null && (
        <div style={styles.energyBar}>
          <label style={styles.label}>Energy:</label>
          <div style={styles.barBackground}>
            <div
              style={{
                ...styles.barFill,
                width: `${energy_level * 100}%`,
              }}
            />
          </div>
          <span style={styles.energyLabel}>
            {Math.round(energy_level * 100)}%
          </span>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, any> = {
  card: {
    border: "1px solid #ddd",
    borderRadius: "8px",
    padding: "16px",
    backgroundColor: "white",
    cursor: "pointer",
    transition: "all 0.2s ease",
    ":hover": {
      boxShadow: "0 4px 8px rgba(0,0,0,0.1)",
      borderColor: "#007bff",
    },
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "8px",
  },
  title: {
    margin: 0,
    fontSize: "16px",
    fontWeight: "bold",
    flexGrow: 1,
  },
  badge: {
    backgroundColor: "#ff6b6b",
    color: "white",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "12px",
    whiteSpace: "nowrap",
  },
  artist: {
    margin: "4px 0 8px 0",
    fontSize: "14px",
    color: "#666",
  },
  metadata: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    marginBottom: "12px",
  },
  tag: {
    backgroundColor: "#f0f0f0",
    padding: "4px 8px",
    borderRadius: "4px",
    fontSize: "12px",
    color: "#555",
  },
  energyBar: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginTop: "8px",
  },
  label: {
    fontSize: "12px",
    fontWeight: "bold",
    color: "#666",
  },
  barBackground: {
    flexGrow: 1,
    height: "6px",
    backgroundColor: "#e0e0e0",
    borderRadius: "3px",
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    backgroundColor: "#007bff",
    transition: "width 0.2s ease",
  },
  energyLabel: {
    fontSize: "12px",
    color: "#666",
    minWidth: "35px",
  },
};
