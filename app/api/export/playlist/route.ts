import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase";

/**
 * POST /api/export/playlist
 * Export a complete playlist with all tracks and metadata
 *
 * Body:
 * {
 *   "playlistId": "uuid"
 * }
 *
 * Returns:
 * {
 *   "success": true,
 *   "playlist": {
 *     "id": "uuid",
 *     "name": "My Playlist",
 *     "description": "...",
 *     "trackCount": 5,
 *     "totalSize": 50000000,
 *     "tracks": [...]
 *   }
 * }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { playlistId } = body;

    if (!playlistId) {
      return NextResponse.json(
        { error: "playlistId required" },
        { status: 400 }
      );
    }

    if (!supabaseAdmin) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }

    // Fetch playlist with tracks in order
    const { data: playlist, error: playlistError } = await supabaseAdmin
      .from("playlists")
      .select(
        `
        id,
        name,
        description,
        created_at,
        updated_at,
        playlist_items(
          position,
          tracks(
            id,
            title,
            artist,
            genre,
            mood,
            energy_level,
            duration_sec,
            track_metadata(
              bitrate,
              codec,
              sample_rate,
              channels,
              file_size,
              storage_url
            )
          )
        )
      `
      )
      .eq("id", playlistId)
      .single();

    if (playlistError || !playlist) {
      return NextResponse.json(
        { error: "Playlist not found" },
        { status: 404 }
      );
    }

    // Sort tracks by position
    const sortedItems = (playlist.playlist_items || []).sort(
      (a: any, b: any) => a.position - b.position
    );

    // Format tracks
    const tracks = sortedItems.map((item: any, index: number) => {
      const track = item.tracks;
      const metadata = track?.track_metadata?.[0];
      const storageUrl = metadata?.storage_url;

      return {
        position: index + 1,
        id: track.id,
        title: track.title,
        artist: track.artist,
        genre: track.genre,
        mood: track.mood,
        energy_level: track.energy_level,
        duration_sec: track.duration_sec,
        downloadUrl: storageUrl || null,
        metadata: metadata
          ? {
              bitrate: metadata.bitrate,
              codec: metadata.codec,
              sample_rate: metadata.sample_rate,
              channels: metadata.channels,
              file_size: metadata.file_size,
            }
          : null,
      };
    });

    // Calculate total size
    const totalSize = tracks.reduce(
      (sum: number, t: any) => sum + (t.metadata?.file_size || 0),
      0
    );

    // Check total size limit (1GB for playlists)
    if (totalSize > 1024 * 1024 * 1024) {
      return NextResponse.json(
        {
          error: "Playlist export size exceeds 1GB limit",
          totalSize,
          limit: 1024 * 1024 * 1024,
        },
        { status: 413 }
      );
    }

    // Create playlist export metadata file
    const playlistMetadata = {
      name: playlist.name,
      description: playlist.description,
      trackCount: tracks.length,
      totalSize,
      created_at: playlist.created_at,
      updated_at: playlist.updated_at,
      exportDate: new Date().toISOString(),
      tracks: tracks.map((t: any) => ({
        position: t.position,
        title: t.title,
        artist: t.artist,
        duration_sec: t.duration_sec,
        genre: t.genre,
        mood: t.mood,
      })),
    };

    return NextResponse.json({
      success: true,
      playlist: {
        id: playlist.id,
        name: playlist.name,
        description: playlist.description,
        trackCount: tracks.length,
        totalSize,
        tracks,
      },
      playlistMetadataJson: playlistMetadata,
      note: "playlistMetadataJson can be included in ZIP export as playlist.json",
      clientImplementationExample: {
        library: "https://stuk.github.io/jszip/",
        usage: `
import JSZip from 'jszip';
const zip = new JSZip();

// Add playlist metadata
zip.file('playlist.json', JSON.stringify(response.playlistMetadataJson, null, 2));

// Add all track files
for (const track of response.playlist.tracks) {
  const response = await fetch(track.downloadUrl);
  const blob = await response.blob();
  const filename = \`\${track.position.toString().padStart(2, '0')} - \${track.artist} - \${track.title}.mp3\`;
  zip.file(filename, blob);
}

// Create download
const zipBlob = await zip.generateAsync({ type: 'blob' });
const url = URL.createObjectURL(zipBlob);
const a = document.createElement('a');
a.href = url;
a.download = \`\${response.playlist.name}.zip\`;
a.click();
      `,
      },
    });
  } catch (error) {
    console.error("Error exporting playlist:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
