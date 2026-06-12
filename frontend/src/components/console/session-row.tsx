"use client";

import { Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConsoleSession } from "@/components/console/types";
import { formatRelativeTime } from "@/lib/format-relative-time";
import { formatLlmModel } from "@/lib/format-llm-model";
import { Button } from "@/components/ui/button";

type SessionRowProps = {
  session: ConsoleSession;
  isActive: boolean;
  onSelect: () => void;
  onDelete?: () => void;
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

export function SessionRow({ session, isActive, onSelect, onDelete }: SessionRowProps) {
  const modelLabel = formatLlmModel(session.llmModel);

  return (
    <div
      className={cn(
        "console-rail-hover group flex items-stretch gap-1 rounded-lg border transition-colors",
        isActive
          ? "console-rail-active border-[var(--console-terracotta)]/30"
          : "border-transparent",
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        className="min-w-0 flex-1 rounded-lg px-3 py-2.5 text-left"
      >
        <div className="truncate text-sm font-medium text-[var(--console-text)]">
          {session.title}
        </div>
        <div className="mt-1 flex items-center justify-between gap-2 text-xs">
          <span className={cn("capitalize", statusClass(session.status))}>
            {session.status}
            <span className="text-[var(--console-text-muted)]">
              {" · "}
              {modelLabel}
            </span>
          </span>
          <span className="shrink-0 text-[var(--console-text-muted)]">
            {session.clipsCount} clip{session.clipsCount === 1 ? "" : "s"}
            {session.createdAt ? ` · ${formatRelativeTime(session.createdAt)}` : ""}
          </span>
        </div>
      </button>
      {onDelete && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="my-1.5 mr-1 h-7 w-7 shrink-0 text-[var(--console-text-muted)] opacity-0 transition-opacity hover:bg-[var(--console-rail-hover)] hover:text-[var(--console-status-error)] group-hover:opacity-100"
          onClick={(event) => {
            event.stopPropagation();
            onDelete();
          }}
          title="Delete session"
          aria-label="Delete session"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  );
}
