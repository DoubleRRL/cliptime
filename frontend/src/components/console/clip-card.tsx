"use client";

import { motion } from "motion/react";
import { cn } from "@/lib/utils";
import type { ConsoleClip } from "@/components/console/types";
import { ClipVideoThumb } from "@/components/console/clip-video-thumb";
import { DurationBadge, ScoreBadge } from "@/components/console/clip-thumb-badges";
import { getClipDisplayTitle } from "@/lib/clip-display-title";
import { pressable, springSnappy } from "@/lib/motion";
import { CornerOrbitLoader } from "@/components/corner-orbit-loader";

type ClipCardProps = {
  clip: ConsoleClip;
  videoSrc: string | null;
  width?: number;
  isActive?: boolean;
  isRegenerating?: boolean;
  onClick?: () => void;
  className?: string;
  compact?: boolean;
};

export function ClipCard({
  clip,
  videoSrc,
  width,
  isActive = false,
  isRegenerating = false,
  onClick,
  className,
  compact = false,
}: ClipCardProps) {
  const displayTitle = getClipDisplayTitle(clip);

  return (
    <motion.button
      type="button"
      layout
      onClick={onClick}
      style={width ? { width } : undefined}
      whileHover={{ y: -3, transition: springSnappy }}
      whileTap={pressable.whileTap}
      transition={springSnappy}
      className={cn(
        "group flex min-w-0 max-w-full shrink-0 flex-col overflow-hidden rounded-2xl border p-2 text-left shadow-sm",
        "border-[var(--console-clip-card-border)] bg-[var(--console-clip-card-bg)]",
        "hover:border-[var(--console-clip-card-border-hover)] hover:shadow-lg",
        isActive &&
          "border-[var(--console-terracotta)] shadow-[0_0_0_1px_var(--console-terracotta)]",
        isRegenerating && "opacity-75",
        className,
      )}
    >
      <div className="relative aspect-[9/16] w-full overflow-hidden rounded-xl bg-black">
        <ClipVideoThumb src={videoSrc} />
        {isRegenerating && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50">
            <CornerOrbitLoader className="h-8 w-8" />
          </div>
        )}
        <ScoreBadge score={clip.viralityScore} />
        <DurationBadge durationSeconds={clip.durationSeconds} />
      </div>

      {!compact && (
        <div className="mt-2 flex min-h-[3rem] w-full min-w-0 items-start overflow-hidden border-t border-[var(--console-clip-card-title-divider)] pt-2">
          <p className="line-clamp-2 w-full text-base font-semibold leading-snug text-[var(--console-text)]">
            {displayTitle}
          </p>
        </div>
      )}
    </motion.button>
  );
}
