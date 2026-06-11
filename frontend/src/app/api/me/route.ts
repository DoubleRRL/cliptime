import { NextResponse } from "next/server";

import { getEffectiveSession } from "@/server/session";

export async function GET() {
  const session = await getEffectiveSession();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  return NextResponse.json({
    user: session.user,
  });
}
