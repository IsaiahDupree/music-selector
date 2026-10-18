import { NextRequest, NextResponse } from "next/server";
import { validateAudioFile } from "@/utils/audio-validation";
import { uploadAudioFile, ensureAudioBucket } from "@/lib/supabase-storage";
import { supabaseAdmin } from "@/lib/supabase";

// Max duration for file upload: 300 seconds
export const maxDuration = 300;

export async function POST(request: NextRequest) {
  try {
    // Get form data
    const formData = await request.formData();
    const file = formData.get("file") as File;
    const title = (formData.get("title") as string) || file.name;
    const artist = (formData.get("artist") as string) || "";
    const genre = (formData.get("genre") as string) || null;

    if (!file) {
      return NextResponse.json(
        { error: "No file provided" },
        { status: 400 }
      );
    }

    // Validate file
    const validation = validateAudioFile(file);
    if (!validation.valid) {
      return NextResponse.json(
        { error: validation.error },
        { status: 400 }
      );
    }

    // Ensure bucket exists
    const bucketReady = await ensureAudioBucket();
    if (!bucketReady) {
      return NextResponse.json(
        { error: "Storage service unavailable" },
        { status: 503 }
      );
    }

    // Use a default user ID for now (no auth yet)
    const userId = "default-user";

    // Upload file
    const uploadResult = await uploadAudioFile(file, userId);
    if (!uploadResult) {
      return NextResponse.json(
        { error: "Failed to upload file" },
        { status: 500 }
      );
    }

    // Create track record
    if (!supabaseAdmin) {
      return NextResponse.json(
        { error: "Database unavailable" },
        { status: 503 }
      );
    }

    const { data: track, error: trackError } = await supabaseAdmin
      .from("tracks")
      .insert({
        title,
        artist,
        genre,
        user_id: userId,
      })
      .select()
      .single();

    if (trackError || !track) {
      // Cleanup uploaded file
      await supabaseAdmin.storage
        .from("audio-files")
        .remove([uploadResult.path]);

      return NextResponse.json(
        { error: "Failed to create track record" },
        { status: 500 }
      );
    }

    // Create metadata record
    const { data: metadata, error: metadataError } = await supabaseAdmin
      .from("track_metadata")
      .insert({
        track_id: track.id,
        file_path: uploadResult.path,
        storage_url: uploadResult.url,
        file_size: uploadResult.size,
      })
      .select()
      .single();

    if (metadataError) {
      console.error("Metadata creation error:", metadataError);
    }

    return NextResponse.json(
      {
        id: track.id,
        title: track.title,
        artist: track.artist,
        genre: track.genre,
        storage_url: uploadResult.url,
      },
      { status: 201 }
    );
  } catch (error) {
    console.error("Upload error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
