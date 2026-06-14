"use client";

import LandingPage from "@/components/landing-page";
import { ConsoleApp } from "@/components/console/console-app";
import { isLandingOnlyModeEnabled } from "@/lib/app-flags";

export default function HomePage() {
  if (isLandingOnlyModeEnabled) {
    return <LandingPage />;
  }

  return <ConsoleApp />;
}
