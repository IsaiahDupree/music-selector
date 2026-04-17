import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase";

/**
 * POST /api/export/batch
 * Export multiple tracks as individual files with metadata
 *
 * Body:
 * {
 *   "trackIds": ["id1", "id2", "id3"],
 *   "format": "original" | "json"  // optional
 * }
 *
 * Returns:
 * {
 *   "success": true,
 *   "count": 3,
 *   "tracks": [
 *     {
 *       "id": "uuid",
 *       "title": "Track Title",
 *       "artist": "Artist Name",
 *       "downloadUrl": "https://...",
 *       "metadata": {...}
 *     }
 *   ],
 *   "totalSize": 15000000
 * }
 *
 * Note: For true ZIP download, use client-side library or backend with archiver package
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { trackIds, format = "original" } = body;

    if (!trackIds || !Array.isArray(trackIds) || trackIds.length === 0) {
      return NextResponse.json(
        { error: "trackIds array required with at least 1 track" },
        { status: 400 }
      );
    }

    if (trackIds.length > 100) {
      return NextResponse.json(
        { error: "Maximum 100 tracks per batch export" },
        { status: 400 }
      );
    }

    if (!supabaseAdmin) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }

    // Fetch track metadata
    const { data: tracks, error: tracksError } = await supabaseAdmin
      .from("tracks")
      .select(
        `
        id,
        title,
        artist,
        genre,
        mood,
        energy_level,
        duration_sec,
        created_at,
        track_metadata(
          bitrate,
          codec,
          sample_rate,
          channels,
          file_size,
          storage_url
        )
      `
      )
      .in("id", trackIds);

    if (tracksError) {
      return NextResponse.json(
        { error: tracksError.message },
        { status: 400 }
      );
    }

    if (!tracks || tracks.length === 0) {
      return NextResponse.json(
        { error: "No tracks found" },
        { status: 404 }
      );
    }

    // Generate download URLs and format response
    const result = tracks.map((track: any) => {
      const metadata = track.track_metadata?.[0];
      const storageUrl = metadata?.storage_url;

      return {
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
    const totalSize = result.reduce(
      (sum: number, t: any) => sum + (t.metadata?.file_size || 0),
      0
    );

    // Check total size limit (500MB)
    if (totalSize > 500 * 1024 * 1024) {
      return NextResponse.json(
        {
          error: "Total export size exceeds 500MB limit",
          totalSize,
          limit: 500 * 1024 * 1024,
        },
        { status: 413 }
      );
    }

    return NextResponse.json({
      success: true,
      count: result.length,
      totalSize,
      tracks: result,
      note: "For ZIP download, implement client-side ZIP creation using JSZip library",
      clientImplementationExample: {
        library: "https://stuk.github.io/jszip/",
        usage: `
import JSZip from 'jszip';
const zip = new JSZip();
for (const track of tracks) {
  const response = await fetch(track.downloadUrl);
  const blob = await response.blob();
  zip.file(\`\${track.artist} - \${track.title}.mp3\`, blob);
}
const zipBlob = await zip.generateAsync({ type: 'blob' });
// Download zipBlob
      `,
      },
    });
  } catch (error) {
    console.error("Error exporting batch:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
