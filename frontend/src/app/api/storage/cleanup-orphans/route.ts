import { NextResponse } from "next/server";

import { createProxyResponse, fetchBackend } from "@/server/backend-api";
import { getEffectiveSession } from "@/server/session";

export async function POST() {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const upstream = await fetchBackend("/storage/cleanup-orphans", {
    method: "POST",
    userId: session.user.id,
  });

  return createProxyResponse(upstream);
}
