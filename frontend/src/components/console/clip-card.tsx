"use client";

import { cn } from "@/lib/utils";
import type { ConsoleClip } from "@/components/console/types";
import { ClipVideoThumb } from "@/components/console/clip-video-thumb";
import { DurationBadge, ScoreBadge } from "@/components/console/clip-thumb-badges";
import { getClipDisplayTitle } from "@/lib/clip-display-title";

type ClipCardProps = {
  clip: ConsoleClip;
  videoSrc: string | null;
  width?: number;
  isActive?: boolean;
  onClick?: () => void;
  className?: string;
  compact?: boolean;
};

export function ClipCard({
  clip,
  videoSrc,
  width,
  isActive = false,
  onClick,
  className,
  compact = false,
}: ClipCardProps) {
  const displayTitle = getClipDisplayTitle(clip);

  return (
    <button
      type="button"
      onClick={onClick}
      style={width ? { width } : undefined}
      className={cn(
        "group flex min-w-0 max-w-full shrink-0 flex-col overflow-hidden rounded-2xl border p-2 text-left shadow-sm transition-all",
        "border-[var(--console-clip-card-border)] bg-[var(--console-clip-card-bg)]",
        "hover:border-[var(--console-clip-card-border-hover)] hover:shadow-md",
        isActive &&
          "border-[var(--console-terracotta)] shadow-[0_0_0_1px_var(--console-terracotta)]",
        className,
      )}
    >
      <div className="relative aspect-[9/16] w-full overflow-hidden rounded-xl bg-black">
        <ClipVideoThumb src={videoSrc} />
        <ScoreBadge score={clip.viralityScore} />
        <DurationBadge durationSeconds={clip.durationSeconds} />
      </div>

      {!compact && (
        <div className="mt-2 flex min-h-[2.25rem] w-full min-w-0 items-center overflow-hidden border-t border-[var(--console-clip-card-title-divider)] pt-2">
          <p className="block w-full truncate text-sm font-semibold leading-snug text-[var(--console-text)]">
            {displayTitle}
          </p>
        </div>
      )}
    </button>
  );
}
