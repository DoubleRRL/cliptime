"use client";

import { cn } from "@/lib/utils";
import type { ConsoleSession } from "@/components/console/types";
import { formatRelativeTime } from "@/lib/format-relative-time";

type SessionRowProps = {
  session: ConsoleSession;
  isActive: boolean;
  onSelect: () => void;
};

function statusClass(status: string): string {
  switch (status) {
    case "completed":
      return "text-[var(--console-status-completed)]";
    case "processing":
      return "text-[var(--console-status-processing)]";
    case "error":
    case "cancelled":
      return "text-[var(--console-status-error)]";
    default:
      return "text-[var(--console-status-queued)]";
  }
}

export function SessionRow({ session, isActive, onSelect }: SessionRowProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "console-rail-hover w-full rounded-lg border px-3 py-2.5 text-left transition-colors",
        isActive
          ? "console-rail-active border-[var(--console-terracotta)]/30"
          : "border-transparent",
      )}
    >
      <div className="truncate text-sm font-medium text-[var(--console-text)]">
        {session.title}
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 text-xs">
        <span className={cn("capitalize", statusClass(session.status))}>{session.status}</span>
        <span className="text-[var(--console-text-muted)]">
          {session.clipsCount} clip{session.clipsCount === 1 ? "" : "s"}
          {session.createdAt ? ` · ${formatRelativeTime(session.createdAt)}` : ""}
        </span>
      </div>
    </button>
  );
}
