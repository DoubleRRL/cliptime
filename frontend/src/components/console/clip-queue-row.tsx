"use client";

import { cn } from "@/lib/utils";
import type { ConsoleClip } from "@/components/console/types";
import { ClipVideoThumb } from "@/components/console/clip-video-thumb";
import { DurationBadge, ScoreBadge } from "@/components/console/clip-thumb-badges";
import { getClipDisplayTitle } from "@/lib/clip-display-title";
import { Checkbox } from "@/components/ui/checkbox";

type ClipQueueRowProps = {
  clip: ConsoleClip;
  videoSrc: string | null;
  isActive: boolean;
  onSelect: () => void;
  onToggleSelected: () => void;
};

export function ClipQueueRow({
  clip,
  videoSrc,
  isActive,
  onSelect,
  onToggleSelected,
}: ClipQueueRowProps) {
  const displayTitle = getClipDisplayTitle(clip);

  return (
    <li
      className={cn(
        "console-rail-hover flex items-start gap-2 rounded-lg border px-2 py-2 transition-colors",
        isActive
          ? "console-rail-active border-[var(--console-terracotta)]/30"
          : "border-transparent",
      )}
    >
      <Checkbox
        checked={clip.selected}
        onCheckedChange={onToggleSelected}
        className="mt-1 border-[var(--console-border)]"
      />
      <button type="button" className="min-w-0 flex-1 text-left" onClick={onSelect}>
        <div className="relative mb-1.5 aspect-[9/16] w-12 overflow-hidden rounded-md bg-black">
          <ClipVideoThumb src={videoSrc} />
          <ScoreBadge score={clip.viralityScore} className="top-1 right-1 px-1 py-0 text-[9px]" />
          <DurationBadge
            durationSeconds={clip.durationSeconds}
            className="bottom-1 right-1 px-1 py-0 text-[8px]"
          />
        </div>
        <div className="min-w-0 w-full overflow-hidden">
          <p className="block w-full truncate text-xs font-semibold text-[var(--console-text)]">
            {displayTitle}
          </p>
        </div>
      </button>
    </li>
  );
}
