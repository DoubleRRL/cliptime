import { NextRequest, NextResponse } from "next/server";

import { createProxyResponse, fetchBackend } from "@/server/backend-api";
import { getEffectiveSession } from "@/server/session";

export async function POST(request: NextRequest) {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: string | undefined;
  try {
    const payload = await request.json();
    if (payload && typeof payload === "object") {
      body = JSON.stringify(payload);
    }
  } catch {
    body = undefined;
  }

  const upstream = await fetchBackend("/storage/cleanup-orphans", {
    method: "POST",
    userId: session.user.id,
    body,
    headers: body ? { "Content-Type": "application/json" } : undefined,
  });

  return createProxyResponse(upstream);
}
