"use client";

import LandingPage from "@/components/landing-page";
import { ConsoleApp } from "@/components/console/console-app";
import { isLandingOnlyModeEnabled, isLocalSingleUserMode } from "@/lib/app-flags";
import { useEffectiveSession } from "@/hooks/use-effective-session";
import { Skeleton } from "@/components/ui/skeleton";

export default function HomePage() {
  const { user, isPending } = useEffectiveSession();

  if (isLandingOnlyModeEnabled) {
    return <LandingPage />;
  }

  if (isLocalSingleUserMode) {
    return <ConsoleApp />;
  }

  if (isPending) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-4">
        <div className="space-y-4">
          <Skeleton className="h-4 w-32 mx-auto" />
          <Skeleton className="h-4 w-48 mx-auto" />
          <Skeleton className="h-4 w-24 mx-auto" />
        </div>
      </div>
    );
  }

  if (!user) {
    return <LandingPage />;
  }

  return <ConsoleApp />;
}
