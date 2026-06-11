import { cn } from "@/lib/utils";
import { formatClipDuration } from "@/lib/format-clip-duration";
import { getScoreBadgeClass } from "@/lib/virality-score";

type ScoreBadgeProps = {
  score: number;
  className?: string;
};

export function ScoreBadge({ score, className }: ScoreBadgeProps) {
  if (score <= 0) return null;

  return (
    <span
      className={cn(
        "absolute top-2 right-2 z-10 rounded-md px-1.5 py-0.5 text-xs font-semibold tabular-nums shadow-sm backdrop-blur-sm",
        getScoreBadgeClass(score),
        className,
      )}
    >
      {score}
    </span>
  );
}

type DurationBadgeProps = {
  durationSeconds: number;
  className?: string;
};

export function DurationBadge({ durationSeconds, className }: DurationBadgeProps) {
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) return null;

  return (
    <span
      className={cn(
        "absolute bottom-2 right-2 z-10 rounded-md px-1.5 py-0.5 text-[11px] font-medium tabular-nums shadow-sm backdrop-blur-sm",
        "bg-[var(--console-duration-bg)] text-[var(--console-duration-fg)]",
        className,
      )}
    >
      {formatClipDuration(durationSeconds)}
    </span>
  );
}
