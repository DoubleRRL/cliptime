import { NextResponse } from "next/server";
import { fetchBackend } from "@/server/backend-api";
import { getEffectiveSession } from "@/server/session";

export async function GET() {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const response = await fetchBackend("/caption-templates", {
    userId: session.user.id,
  });
  const data = await response.json().catch(() => ({}));
  return NextResponse.json(data, { status: response.status });
}
