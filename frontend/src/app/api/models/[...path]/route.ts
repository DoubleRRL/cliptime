import { NextResponse } from "next/server";

import { fetchBackend } from "@/server/backend-api";
import { getEffectiveSession } from "@/server/session";

const ALLOWED_PATHS = new Set(["installed", "recommendations", "pull"]);

async function proxyModelsRequest(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { path } = await params;
  const endpoint = path.join("/");
  if (!ALLOWED_PATHS.has(endpoint)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.text();

  const upstream = await fetchBackend(`/models/${endpoint}`, {
    method: request.method,
    userId: session.user.id,
    extraHeaders: body ? { "Content-Type": "application/json" } : undefined,
    body,
    cache: "no-store",
  });

  const contentType = upstream.headers.get("content-type") || "application/json";

  // Stream SSE responses (model pull progress) straight through.
  if (contentType.includes("text/event-stream")) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  }

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": contentType },
  });
}

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyModelsRequest(request, context);
}

export async function POST(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  return proxyModelsRequest(request, context);
}
