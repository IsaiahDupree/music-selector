import { supabaseAdmin } from "./supabase";

/**
 * Index a track in the database after upload
 */
export async function indexTrack(
  trackId: string,
  metadata: {
    title: string;
    artist?: string | null;
    genre?: string | null;
    mood?: string | null;
    energy_level?: number | null;
    duration_sec?: number | null;
    bpm?: number | null;
  }
) {
  if (!supabaseAdmin) {
    throw new Error("Supabase admin client not available");
  }

  try {
    // Update track with metadata
    const { error: updateError } = await supabaseAdmin
      .from("tracks")
      .update({
        title: metadata.title,
        artist: metadata.artist,
        genre: metadata.genre,
        mood: metadata.mood,
        energy_level: metadata.energy_level,
        duration_sec: metadata.duration_sec,
        bpm: metadata.bpm,
        updated_at: new Date().toISOString(),
      })
      .eq("id", trackId);

    if (updateError) {
      throw new Error(`Failed to index track: ${updateError.message}`);
    }

    return { success: true, trackId };
  } catch (error) {
    console.error("Error indexing track:", error);
    throw error;
  }
}

/**
 * Re-index all tracks (useful for batch updates)
 */
export async function reindexAllTracks() {
  if (!supabaseAdmin) {
    throw new Error("Supabase admin client not available");
  }

  try {
    const { data: tracks, error } = await supabaseAdmin
      .from("tracks")
      .select("id");

    if (error) {
      throw new Error(`Failed to fetch tracks: ${error.message}`);
    }

    const results = {
      total: tracks.length,
      indexed: 0,
      failed: 0,
    };

    for (const track of tracks) {
      try {
        // Mark as updated to refresh full-text search indexes
        await supabaseAdmin
          .from("tracks")
          .update({ updated_at: new Date().toISOString() })
          .eq("id", track.id);

        results.indexed++;
      } catch (error) {
        console.error(`Failed to reindex track ${track.id}:`, error);
        results.failed++;
      }
    }

    return results;
  } catch (error) {
    console.error("Error reindexing tracks:", error);
    throw error;
  }
}

/**
 * Get track count and statistics
 */
export async function getLibraryStats() {
  if (!supabaseAdmin) {
    throw new Error("Supabase admin client not available");
  }

  try {
    const { data: tracks, count, error } = await supabaseAdmin
      .from("tracks")
      .select("*", { count: "exact" });

    if (error) {
      throw new Error(`Failed to fetch stats: ${error.message}`);
    }

    if (!tracks) {
      return {
        totalTracks: 0,
        genres: [],
        moods: [],
        totalDuration: 0,
        averageDuration: 0,
        trendingTracks: 0,
      };
    }

    const genres = [...new Set(tracks.map(t => t.genre).filter(Boolean))];
    const moods = [...new Set(tracks.map(t => t.mood).filter(Boolean))];
    const totalDuration = tracks.reduce((sum, t) => sum + (t.duration_sec || 0), 0);
    const averageDuration = tracks.length > 0 ? totalDuration / tracks.length : 0;
    const trendingTracks = tracks.filter(t => t.is_trending).length;

    return {
      totalTracks: count || 0,
      genres,
      moods,
      totalDuration,
      averageDuration: Math.round(averageDuration),
      trendingTracks,
    };
  } catch (error) {
    console.error("Error getting library stats:", error);
    throw error;
  }
}
