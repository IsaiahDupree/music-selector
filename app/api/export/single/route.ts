import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase";

export async function POST(request: NextRequest) {
  try {
    const { trackId } = await request.json();

    if (!trackId) {
      return NextResponse.json(
        { error: "Track ID is required" },
        { status: 400 }
      );
    }

    if (!supabaseAdmin) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }

    // Get track metadata with storage URL
    const { data: metadata, error: metadataError } = await supabaseAdmin
      .from("track_metadata")
      .select("storage_url, file_path")
      .eq("track_id", trackId)
      .single();

    if (metadataError || !metadata?.storage_url) {
      return NextResponse.json(
        { error: "Track not found or no file available" },
        { status: 404 }
      );
    }

    // Return metadata for client-side download
    return NextResponse.json({
      success: true,
      downloadUrl: metadata.storage_url,
      trackId,
    });
  } catch (error) {
    console.error("Error exporting single track:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
