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

    // Get unique genres
    const { data: genres, error: genreError } = await supabaseAdmin
      .from("tracks")
      .select("genre", { count: "exact" })
      .not("genre", "is", null);

    // Get unique moods
    const { data: moods, error: moodError } = await supabaseAdmin
      .from("tracks")
      .select("mood", { count: "exact" })
      .not("mood", "is", null);

    if (genreError || moodError) {
      return NextResponse.json(
        { error: "Failed to fetch filters" },
        { status: 400 }
      );
    }

    const genreList = [...new Set(genres.map(g => g.genre).filter(Boolean))];
    const moodList = [...new Set(moods.map(m => m.mood).filter(Boolean))];

    return NextResponse.json({
      genres: genreList,
      moods: moodList,
      durationRanges: [
        { label: "0-30s", min: 0, max: 30 },
        { label: "30s-1m", min: 30, max: 60 },
        { label: "1-5m", min: 60, max: 300 },
        { label: "5m+", min: 300, max: null },
      ],
      energyLevels: [
        { label: "Low", min: 0, max: 0.33 },
        { label: "Medium", min: 0.33, max: 0.67 },
        { label: "High", min: 0.67, max: 1.0 },
      ],
    });
  } catch (error) {
    console.error("Error fetching filters:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
