export default function Home() {
  return (
    <main style={{ padding: "2rem" }}>
      <h1>MusicLibrary — Audio Asset Manager</h1>
      <p>Background music recommendation engine for video content creation.</p>

      <section>
        <h2>Features</h2>
        <ul>
          <li>Upload and manage audio files</li>
          <li>Automatic metadata extraction (duration, bitrate, codec)</li>
          <li>Full-text search across titles, artists, and tags</li>
          <li>Advanced filtering by genre, mood, duration, and energy</li>
          <li>Tagging and playlist management</li>
          <li>Export in multiple formats (MP3, WAV, AAC, FLAC)</li>
          <li>CSV and JSON export for metadata</li>
        </ul>
      </section>

      <section>
        <h2>Getting Started</h2>
        <p>
          API Health: <a href="/api/health">/api/health</a>
        </p>
      </section>
    </main>
  );
}
