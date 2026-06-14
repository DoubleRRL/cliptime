"use client";

import { cn } from "@/lib/utils";
import type { ConsoleClip } from "@/components/console/types";
import { ClipVideoThumb } from "@/components/console/clip-video-thumb";
import { DurationBadge, ScoreBadge } from "@/components/console/clip-thumb-badges";
import { getClipDisplayTitle } from "@/lib/clip-display-title";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2 } from "lucide-react";

type ClipQueueRowProps = {
  clip: ConsoleClip;
  videoSrc: string | null;
  isActive: boolean;
  isRegenerating?: boolean;
  onSelect: () => void;
  onToggleSelected: () => void;
};

export function ClipQueueRow({
  clip,
  videoSrc,
  isActive,
  isRegenerating = false,
  onSelect,
  onToggleSelected,
}: ClipQueueRowProps) {
  const displayTitle = getClipDisplayTitle(clip);

  return (
    <div
      className={cn(
        "console-rail-hover flex items-start gap-2 rounded-lg border px-2 py-2 transition-colors",
        isRegenerating && "opacity-80",
        isActive
          ? "console-rail-active border-[var(--console-terracotta)]/30"
          : "border-transparent",
      )}
    >
      <Checkbox
        checked={clip.selected}
        onCheckedChange={onToggleSelected}
        disabled={isRegenerating}
        className="mt-1 border-[var(--console-border)]"
      />
      <button
        type="button"
        className="min-w-0 flex-1 text-left"
        onClick={onSelect}
        disabled={isRegenerating}
      >
        <div className="relative mb-1.5 aspect-[9/16] w-12 overflow-hidden rounded-md bg-black">
          <ClipVideoThumb src={videoSrc} />
          {isRegenerating && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50">
              <Loader2 className="h-4 w-4 animate-spin text-[var(--console-terracotta)]" />
            </div>
          )}
          <ScoreBadge score={clip.viralityScore} className="top-1 right-1 px-1 py-0 text-[9px]" />
          <DurationBadge
            durationSeconds={clip.durationSeconds}
            className="bottom-1 right-1 px-1 py-0 text-[8px]"
          />
        </div>
        <div className="min-w-0 w-full overflow-hidden">
          <p className="line-clamp-2 w-full text-sm font-semibold leading-snug text-[var(--console-text)]">
            {displayTitle}
          </p>
          {isRegenerating && (
            <p className="mt-0.5 animate-pulse text-[10px] text-[var(--console-terracotta)]">
              Rendering…
            </p>
          )}
        </div>
      </button>
    </div>
  );
}
