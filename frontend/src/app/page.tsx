"use client";

import { useSession } from "@/lib/auth-client";
import LandingPage from "@/components/landing-page";
import { ConsoleApp } from "@/components/console/console-app";
import { isLandingOnlyModeEnabled } from "@/lib/app-flags";
import { Skeleton } from "@/components/ui/skeleton";

export default function HomePage() {
  const { data: session, isPending } = useSession();

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

  if (isLandingOnlyModeEnabled || !session?.user) {
    return <LandingPage />;
  }

  return <ConsoleApp />;
}
