"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { formatBytes } from "@/lib/format-bytes";
import { STORAGE_BUCKETS, type StorageSummary } from "@/lib/storage-types";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

type StorageDetailsSectionProps = {
  refreshKey?: number;
  onStorageChanged?: () => void;
};

export function StorageDetailsSection({
  refreshKey = 0,
  onStorageChanged,
}: StorageDetailsSectionProps) {
  const [summary, setSummary] = useState<StorageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [cleaning, setCleaning] = useState(false);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/storage", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("Failed to load storage summary");
      }
      setSummary((await response.json()) as StorageSummary);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load storage");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary, refreshKey]);

  const handleCleanup = async () => {
    setCleaning(true);
    try {
      const response = await fetch("/api/storage/cleanup-orphans", { method: "POST" });
      if (!response.ok) {
        throw new Error("Failed to clean orphan files");
      }
      const data = (await response.json()) as StorageSummary & {
        removed_files?: number;
        reclaimed_bytes?: number;
      };
      setSummary(data);
      onStorageChanged?.();
      toast.success(
        data.removed_files
          ? `Reclaimed ${formatBytes(data.reclaimed_bytes ?? 0)} from ${data.removed_files} orphan file${data.removed_files === 1 ? "" : "s"}`
          : "No orphan files to remove",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Cleanup failed");
    } finally {
      setCleaning(false);
    }
  };

  if (loading && !summary) {
    return (
      <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading storage usage…
      </div>
    );
  }

  if (!summary) {
    return (
      <Alert>
        <AlertDescription>Storage summary is unavailable right now.</AlertDescription>
      </Alert>
    );
  }

  const total = Math.max(summary.total_bytes, 1);

  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium text-foreground">Disk usage</p>
        <p className="mt-1 text-2xl font-semibold text-foreground">
          {formatBytes(summary.total_bytes)}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {summary.counts.tasks} sessions · {summary.counts.clips} clips ·{" "}
          {summary.counts.orphan_files} orphan file
          {summary.counts.orphan_files === 1 ? "" : "s"}
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex h-3 overflow-hidden rounded-full bg-muted">
          {STORAGE_BUCKETS.map((bucket) => {
            const bytes = summary.breakdown[bucket.key] ?? 0;
            if (bytes <= 0) return null;
            return (
              <div
                key={bucket.key}
                className={cn(bucket.color, "h-full")}
                style={{ width: `${(bytes / total) * 100}%` }}
                title={`${bucket.label}: ${formatBytes(bytes)}`}
              />
            );
          })}
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {STORAGE_BUCKETS.map((bucket) => (
            <div
              key={bucket.key}
              className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <span className={cn("h-2.5 w-2.5 rounded-full", bucket.color)} />
                <span>{bucket.label}</span>
              </div>
              <span className="text-muted-foreground">
                {formatBytes(summary.breakdown[bucket.key] ?? 0)}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
        Media files live under <code className="text-foreground">{summary.temp_dir}</code>.
        Deleting sessions removes their clips and unshared uploads from disk.
      </div>

      <Button
        type="button"
        variant="outline"
        disabled={cleaning || summary.counts.orphan_files === 0}
        onClick={() => void handleCleanup()}
      >
        {cleaning ? "Cleaning…" : "Reclaim orphan files"}
      </Button>
    </div>
  );
}
