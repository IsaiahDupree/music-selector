"use client";

import { useState } from "react";
import LibraryView from "@/components/LibraryView";
import type { Track } from "@/lib/supabase";

export default function Home() {
  const [selectedTrack, setSelectedTrack] = useState<Track | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setUploadError(null);

    const formData = new FormData(e.currentTarget);
    const file = formData.get("file") as File;
    const title = (formData.get("title") as string) || file.name;
    const artist = formData.get("artist") as string;
    const genre = formData.get("genre") as string;

    if (!file) {
      setUploadError("Please select a file");
      return;
    }

    try {
      setIsUploading(true);
      const uploadFormData = new FormData();
      uploadFormData.append("file", file);
      uploadFormData.append("title", title);
      uploadFormData.append("artist", artist);
      uploadFormData.append("genre", genre);

      const response = await fetch("/api/upload", {
        method: "POST",
        body: uploadFormData,
      });

      if (!response.ok) {
        const error = await response.json();
        setUploadError(error.error || "Upload failed");
        return;
      }

      setShowUpload(false);
      e.currentTarget.reset();
      window.location.reload();
    } catch (error) {
      setUploadError(
        error instanceof Error ? error.message : "Unknown error"
      );
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main style={styles.main}>
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>MusicLibrary</h1>
          <p style={styles.subtitle}>Audio Asset Manager for Video Production</p>
        </div>
        <button
          onClick={() => setShowUpload(!showUpload)}
          style={styles.uploadButton}
        >
          {showUpload ? "Cancel" : "Upload Audio"}
        </button>
      </header>

      {showUpload && (
        <section style={styles.uploadSection}>
          <h2>Upload Audio File</h2>
          <form onSubmit={handleUpload} style={styles.uploadForm}>
            <div style={styles.formGroup}>
              <label htmlFor="file">Audio File *</label>
              <input
                id="file"
                type="file"
                name="file"
                accept=".mp3,.wav,.aac,.flac"
                required
                style={styles.input}
              />
            </div>

            <div style={styles.formGroup}>
              <label htmlFor="title">Title</label>
              <input
                id="title"
                type="text"
                name="title"
                placeholder="Track title"
                style={styles.input}
              />
            </div>

            <div style={styles.formGroup}>
              <label htmlFor="artist">Artist</label>
              <input
                id="artist"
                type="text"
                name="artist"
                placeholder="Artist name"
                style={styles.input}
              />
            </div>

            <div style={styles.formGroup}>
              <label htmlFor="genre">Genre</label>
              <select name="genre" id="genre" style={styles.input}>
                <option value="">Select a genre</option>
                <option value="lofi">Lo-fi</option>
                <option value="electronic">Electronic</option>
                <option value="house">House</option>
                <option value="hip_hop">Hip Hop</option>
                <option value="cinematic">Cinematic</option>
                <option value="pop">Pop</option>
                <option value="ambient">Ambient</option>
              </select>
            </div>

            {uploadError && <div style={styles.error}>{uploadError}</div>}

            <button
              type="submit"
              disabled={isUploading}
              style={{
                ...styles.submitButton,
                opacity: isUploading ? 0.6 : 1,
              }}
            >
              {isUploading ? "Uploading..." : "Upload"}
            </button>
          </form>
        </section>
      )}

      <section style={styles.librarySection}>
        <LibraryView onSelectTrack={setSelectedTrack} />
      </section>

      {selectedTrack && (
        <aside style={styles.sidebar}>
          <button
            onClick={() => setSelectedTrack(null)}
            style={styles.closeButton}
          >
            ×
          </button>
          <h2>{selectedTrack.title}</h2>
          {selectedTrack.artist && <p><strong>Artist:</strong> {selectedTrack.artist}</p>}
          {selectedTrack.genre && <p><strong>Genre:</strong> {selectedTrack.genre}</p>}
          {selectedTrack.mood && <p><strong>Mood:</strong> {selectedTrack.mood}</p>}
          {selectedTrack.duration_sec && (
            <p>
              <strong>Duration:</strong> {Math.floor(selectedTrack.duration_sec / 60)}:
              {(selectedTrack.duration_sec % 60).toString().padStart(2, "0")}
            </p>
          )}
          {selectedTrack.energy_level !== null &&
            selectedTrack.energy_level !== undefined && (
              <p>
                <strong>Energy:</strong> {Math.round(
                  selectedTrack.energy_level * 100
                )}%
              </p>
            )}
        </aside>
      )}
    </main>
  );
}

const styles: Record<string, any> = {
  main: {
    minHeight: "100vh",
    backgroundColor: "#fafafa",
  },
  header: {
    backgroundColor: "white",
    padding: "20px",
    borderBottom: "1px solid #ddd",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    margin: 0,
    fontSize: "28px",
    fontWeight: "bold",
  },
  subtitle: {
    margin: "4px 0 0 0",
    color: "#666",
    fontSize: "14px",
  },
  uploadButton: {
    padding: "8px 16px",
    backgroundColor: "#28a745",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
  },
  uploadSection: {
    backgroundColor: "white",
    padding: "20px",
    borderBottom: "1px solid #ddd",
    margin: "20px",
    borderRadius: "8px",
  },
  uploadForm: {
    maxWidth: "500px",
  },
  formGroup: {
    marginBottom: "16px",
    display: "flex",
    flexDirection: "column",
  },
  input: {
    padding: "8px 12px",
    border: "1px solid #ddd",
    borderRadius: "4px",
    fontSize: "14px",
    marginTop: "4px",
  },
  error: {
    backgroundColor: "#fee",
    color: "#c00",
    padding: "12px",
    borderRadius: "4px",
    marginBottom: "16px",
  },
  submitButton: {
    padding: "10px 20px",
    backgroundColor: "#007bff",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
  },
  librarySection: {
    padding: "20px",
  },
  sidebar: {
    position: "fixed",
    right: 0,
    top: 0,
    width: "300px",
    height: "100vh",
    backgroundColor: "white",
    borderLeft: "1px solid #ddd",
    padding: "20px",
    overflowY: "auto",
    boxShadow: "-2px 0 4px rgba(0,0,0,0.1)",
  },
  closeButton: {
    position: "absolute",
    top: "10px",
    right: "10px",
    backgroundColor: "transparent",
    border: "none",
    fontSize: "24px",
    cursor: "pointer",
    color: "#666",
  },
};
