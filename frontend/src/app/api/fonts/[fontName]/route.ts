import { NextResponse } from "next/server";

import { buildBackendAuthHeaders } from "@/lib/backend-auth";
import { getEffectiveSession } from "@/server/session";

interface Params {
  params: Promise<{ fontName: string }>;
}

export async function GET(_: Request, { params }: Params) {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { fontName } = await params;
  const apiUrl =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
  const normalizedApiUrl = apiUrl.replace(/\/$/, "");
  const encodedFontName = encodeURIComponent(fontName);
  const backendAuthHeaders = buildBackendAuthHeaders(session.user.id);

  let upstream = await fetch(`${normalizedApiUrl}/fonts/${encodedFontName}`, {
    headers: {
      ...backendAuthHeaders,
    },
    cache: "force-cache",
  });

  if (upstream.status === 404) {
    upstream = await fetch(`${normalizedApiUrl}/api/fonts/${encodedFontName}`, {
      headers: {
        ...backendAuthHeaders,
      },
      cache: "force-cache",
    });
  }

  const arrayBuffer = await upstream.arrayBuffer();
  return new NextResponse(arrayBuffer, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/octet-stream",
      "Cache-Control": upstream.headers.get("cache-control") || "public, max-age=31536000",
    },
  });
}
