import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase";

export async function GET(request: NextRequest) {
  try {
    if (!supabaseAdmin) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }

    // Fetch all tracks with metadata
    const { data: tracks, error: tracksError } = await supabaseAdmin
      .from("tracks")
      .select("*");

    if (tracksError) {
      return NextResponse.json(
        { error: tracksError.message },
        { status: 400 }
      );
    }

    // Fetch metadata for all tracks
    const { data: metadata, error: metadataError } = await supabaseAdmin
      .from("track_metadata")
      .select("*");

    if (metadataError) {
      console.error("Metadata fetch error:", metadataError);
    }

    // Combine tracks with metadata
    const trackMap = new Map();
    metadata?.forEach(m => {
      trackMap.set(m.track_id, m);
    });

    const enrichedTracks = tracks.map(t => ({
      ...t,
      metadata: trackMap.get(t.id) || null,
    }));

    const exportData = {
      version: "1.0",
      exportDate: new Date().toISOString(),
      totalTracks: enrichedTracks.length,
      tracks: enrichedTracks,
    };

    return NextResponse.json(exportData, {
      status: 200,
      headers: {
        "Content-Disposition": `attachment; filename="music-library-${Date.now()}.json"`,
      },
    });
  } catch (error) {
    console.error("Error exporting JSON:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
