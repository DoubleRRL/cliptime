"use client";

import { useCallback, useEffect, useState } from "react";
import { HardDrive } from "lucide-react";
import { formatBytes } from "@/lib/format-bytes";
import type { StorageSummary } from "@/lib/storage-types";
import { cn } from "@/lib/utils";

type StorageSummaryBarProps = {
  className?: string;
  refreshKey?: number;
  onOpenStorage?: () => void;
};

export function StorageSummaryBar({
  className,
  refreshKey = 0,
  onOpenStorage,
}: StorageSummaryBarProps) {
  const [summary, setSummary] = useState<StorageSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/storage", { cache: "no-store" });
      if (!response.ok) return;
      setSummary((await response.json()) as StorageSummary);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary, refreshKey]);

  const label = loading
    ? "Calculating storage…"
    : summary
      ? `${formatBytes(summary.total_bytes)} used · ${summary.counts.tasks} sessions · ${summary.counts.clips} clips`
      : "Storage unavailable";

  return (
    <button
      type="button"
      onClick={onOpenStorage}
      className={cn(
        "flex w-full items-start gap-2 rounded-lg border border-[var(--console-border)] px-3 py-2 text-left text-xs text-[var(--console-text-muted)] transition-colors hover:bg-[var(--console-rail-hover)] hover:text-[var(--console-text)]",
        className,
      )}
      title="Open storage details"
    >
      <HardDrive className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span className="leading-relaxed">{label}</span>
    </button>
  );
}
