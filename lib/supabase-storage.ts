import { supabaseAdmin } from "./supabase";
import { getAudioFileExtension } from "@/utils/audio-validation";

const BUCKET_NAME = "audio-files";

export async function ensureAudioBucket() {
  if (!supabaseAdmin) return false;

  try {
    const { data: buckets } = await supabaseAdmin.storage.listBuckets();
    const bucketExists = buckets?.some((b) => b.name === BUCKET_NAME);

    if (!bucketExists) {
      await supabaseAdmin.storage.createBucket(BUCKET_NAME, {
        public: true,
        allowedMimeTypes: [
          "audio/mpeg",
          "audio/wav",
          "audio/aac",
          "audio/flac",
          "audio/x-wav",
          "audio/x-flac",
        ],
      });
    }
    return true;
  } catch (error) {
    console.error("Error ensuring audio bucket:", error);
    return false;
  }
}

export async function uploadAudioFile(
  file: File,
  userId: string,
  options?: { onProgress?: (progress: number) => void }
): Promise<{ url: string; path: string; size: number } | null> {
  if (!supabaseAdmin) {
    console.error("Supabase admin client not available");
    return null;
  }

  try {
    const ext = getAudioFileExtension(file.type);
    const fileName = `${userId}/${Date.now()}-${file.name.replace(/\.[^/.]+$/, "")}.${ext}`;

    const { data, error } = await supabaseAdmin.storage
      .from(BUCKET_NAME)
      .upload(fileName, file, {
        contentType: file.type,
        upsert: false,
      });

    if (error) {
      console.error("Upload error:", error);
      return null;
    }

    // Get public URL
    const { data: publicUrlData } = supabaseAdmin.storage
      .from(BUCKET_NAME)
      .getPublicUrl(data.path);

    return {
      url: publicUrlData.publicUrl,
      path: data.path,
      size: file.size,
    };
  } catch (error) {
    console.error("Error uploading audio file:", error);
    return null;
  }
}

export async function deleteAudioFile(filePath: string): Promise<boolean> {
  if (!supabaseAdmin) return false;

  try {
    const { error } = await supabaseAdmin.storage
      .from(BUCKET_NAME)
      .remove([filePath]);

    if (error) {
      console.error("Delete error:", error);
      return false;
    }
    return true;
  } catch (error) {
    console.error("Error deleting audio file:", error);
    return false;
  }
}
