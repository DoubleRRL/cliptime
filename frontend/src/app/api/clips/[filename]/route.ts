import { NextResponse } from "next/server";

import { fetchBackend } from "@/server/backend-api";
import { getEffectiveSession } from "@/server/session";

const FORWARDED_HEADERS = [
  "content-type",
  "content-length",
  "content-range",
  "accept-ranges",
  "cache-control",
  "content-disposition",
] as const;

export async function GET(
  request: Request,
  { params }: { params: Promise<{ filename: string }> },
) {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { filename } = await params;
  const range = request.headers.get("range");

  const upstream = await fetchBackend(`/clips/${encodeURIComponent(filename)}`, {
    method: "GET",
    userId: session.user.id,
    extraHeaders: range ? { Range: range } : undefined,
    cache: "no-store",
  });

  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) headers.set(name, value);
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers,
  });
}
