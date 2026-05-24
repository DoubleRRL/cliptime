"use client";

import { cn } from "@/lib/utils";

interface CornerOrbitLoaderProps {
  className?: string;
}

export function CornerOrbitLoader({ className }: CornerOrbitLoaderProps) {
  return <span className={cn("corner-orbit-loader inline-block shrink-0", className)} aria-hidden />;
}
