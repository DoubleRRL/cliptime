import { NextRequest, NextResponse } from "next/server";

import { createProxyResponse, fetchBackend } from "@/server/backend-api";
import { getEffectiveSession } from "@/server/session";

export async function GET(request: NextRequest) {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit");
  const offset = searchParams.get("offset");
  const query = new URLSearchParams();
  if (limit) query.set("limit", limit);
  if (offset) query.set("offset", offset);

  const upstream = await fetchBackend(query.toString() ? `/tasks/?${query.toString()}` : "/tasks/", {
    method: "GET",
    userId: session.user.id,
    cache: "no-store",
  });

  return createProxyResponse(upstream);
}
