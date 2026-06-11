import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_FILE = /\.(.*)$/;
const PUBLIC_PATHS = new Set(["/", "/sign-in", "/sign-up"]);

function isLocalSingleUserModeEnabled(): boolean {
  const value = process.env.NEXT_PUBLIC_LOCAL_SINGLE_USER;
  if (value === undefined || value === "") return true;
  const normalized = value.trim().toLowerCase();
  return !["0", "false", "no", "off"].includes(normalized);
}

export function middleware(request: NextRequest) {
  const isLandingOnlyModeEnabled =
    process.env.NEXT_PUBLIC_LANDING_ONLY_MODE === "true";

  if (isLandingOnlyModeEnabled) {
    const { pathname } = request.nextUrl;

    if (
      pathname === "/" ||
      pathname.startsWith("/_next") ||
      PUBLIC_FILE.test(pathname)
    ) {
      return NextResponse.next();
    }

    if (pathname.startsWith("/api")) {
      return NextResponse.json(
        { error: "SupoClip is in landing-page-only mode." },
        { status: 503 },
      );
    }

    const url = request.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (isLocalSingleUserModeEnabled()) {
    return NextResponse.next();
  }

  const { pathname } = request.nextUrl;
  const hasSession = Boolean(
    request.cookies.get("better-auth.session_token")?.value ||
      request.cookies.get("__Secure-better-auth.session_token")?.value,
  );

  if (
    !hasSession &&
    !PUBLIC_PATHS.has(pathname) &&
    !pathname.startsWith("/api/auth") &&
    !pathname.startsWith("/_next") &&
    !PUBLIC_FILE.test(pathname)
  ) {
    const url = request.nextUrl.clone();
    url.pathname = "/sign-in";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/:path*",
};
