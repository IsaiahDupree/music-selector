import { NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/supabase";

export async function GET() {
  const timestamp = new Date().toISOString();
  const health = {
    status: "ok",
    timestamp,
    services: {
      api: "ok",
      database: "checking",
    },
  };

  try {
    if (supabaseAdmin) {
      const { data, error } = await supabaseAdmin
        .from("tracks")
        .select("id")
        .limit(1);

      if (error) {
        health.services.database = "error";
        return NextResponse.json(
          { ...health, error: error.message },
          { status: 500 }
        );
      }
      health.services.database = "ok";
    }

    return NextResponse.json(health, { status: 200 });
  } catch (error) {
    return NextResponse.json(
      {
        ...health,
        status: "error",
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    );
  }
}
