import { NextResponse } from "next/server";

import { buildBackendAuthHeaders } from "@/lib/backend-auth";
import { getEffectiveSession } from "@/server/session";

export async function POST(request: Request) {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = await request.text();
  const apiUrl =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";

  const upstream = await fetch(`${apiUrl}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildBackendAuthHeaders(session.user.id),
    },
    body: payload,
  });

  const responseText = await upstream.text();
  return new NextResponse(responseText, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("content-type") || "application/json",
    },
  });
}
