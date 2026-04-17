import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase";

const DEFAULT_PAGE_SIZE = 20;

export async function GET(request: NextRequest) {
  try {
    if (!supabaseAdmin) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }

    const searchParams = request.nextUrl.searchParams;
    const page = parseInt(searchParams.get("page") || "1");
    const limit = parseInt(searchParams.get("limit") || String(DEFAULT_PAGE_SIZE));
    const offset = (page - 1) * limit;

    // Get filters
    const genre = searchParams.get("genre");
    const mood = searchParams.get("mood");
    const minDuration = searchParams.get("minDuration");
    const maxDuration = searchParams.get("maxDuration");
    const minEnergy = searchParams.get("minEnergy");
    const maxEnergy = searchParams.get("maxEnergy");

    // Build query
    let query = supabaseAdmin
      .from("tracks")
      .select("*", { count: "exact" })
      .order("created_at", { ascending: false });

    // Apply filters
    if (genre) {
      query = query.eq("genre", genre);
    }
    if (mood) {
      query = query.eq("mood", mood);
    }
    if (minDuration) {
      query = query.gte("duration_sec", parseInt(minDuration));
    }
    if (maxDuration) {
      query = query.lte("duration_sec", parseInt(maxDuration));
    }
    if (minEnergy) {
      query = query.gte("energy_level", parseFloat(minEnergy));
    }
    if (maxEnergy) {
      query = query.lte("energy_level", parseFloat(maxEnergy));
    }

    // Apply pagination
    const { data: tracks, count, error } = await query
      .range(offset, offset + limit - 1);

    if (error) {
      return NextResponse.json(
        { error: error.message },
        { status: 400 }
      );
    }

    const totalPages = count ? Math.ceil(count / limit) : 0;

    return NextResponse.json({
      tracks,
      pagination: {
        page,
        limit,
        total: count,
        totalPages,
      },
    });
  } catch (error) {
    console.error("Error fetching tracks:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
