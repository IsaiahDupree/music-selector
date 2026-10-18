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

    // Fetch all tracks
    const { data: tracks, error } = await supabaseAdmin
      .from("tracks")
      .select("*");

    if (error) {
      return NextResponse.json(
        { error: error.message },
        { status: 400 }
      );
    }

    // Create CSV
    const headers = [
      "ID",
      "Title",
      "Artist",
      "Genre",
      "Mood",
      "Energy Level",
      "Duration (s)",
      "BPM",
      "Trending",
      "Created",
    ];

    const rows = tracks.map(t => [
      t.id,
      `"${(t.title || "").replace(/"/g, '""')}"`,
      `"${(t.artist || "").replace(/"/g, '""')}"`,
      t.genre || "",
      t.mood || "",
      t.energy_level !== null ? t.energy_level : "",
      t.duration_sec || "",
      t.bpm || "",
      t.is_trending ? "Yes" : "No",
      new Date(t.created_at).toISOString(),
    ]);

    const csv = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");

    return new NextResponse(csv, {
      status: 200,
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="music-library-${Date.now()}.csv"`,
      },
    });
  } catch (error) {
    console.error("Error exporting CSV:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
