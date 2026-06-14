"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { formatBytes } from "@/lib/format-bytes";
import { STORAGE_BUCKETS, type OrphanFile, type StorageSummary } from "@/lib/storage-types";
import { cn } from "@/lib/utils";
import { FolderOpen, Loader2, Trash2 } from "lucide-react";
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
  const [deletingPath, setDeletingPath] = useState<string | null>(null);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);

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

  const orphanBytes = useMemo(
    () => summary?.breakdown.orphans ?? 0,
    [summary?.breakdown.orphans],
  );

  const cleanupOrphans = async (paths?: string[]) => {
    const isBulk = !paths;
    if (isBulk) {
      setCleaning(true);
    } else if (paths[0]) {
      setDeletingPath(paths[0]);
    }

    try {
      const response = await fetch("/api/storage/cleanup-orphans", {
        method: "POST",
        headers: paths ? { "Content-Type": "application/json" } : undefined,
        body: paths ? JSON.stringify({ paths }) : undefined,
      });
      if (!response.ok) {
        throw new Error("Failed to delete orphan files");
      }
      const data = (await response.json()) as StorageSummary;
      setSummary(data);
      onStorageChanged?.();
      toast.success(
        data.removed_files
          ? `Deleted ${data.removed_files} orphan file${data.removed_files === 1 ? "" : "s"} (${formatBytes(data.reclaimed_bytes ?? 0)})`
          : "No orphan files to delete",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setCleaning(false);
      setDeletingPath(null);
      setConfirmDeleteAll(false);
    }
  };

  const copyFolderPath = async () => {
    const folderPath = summary?.host_path || summary?.temp_dir;
    if (!folderPath) return;

    try {
      await navigator.clipboard.writeText(folderPath);
      toast.success("Folder path copied", {
        description: "Finder → Go → Go to Folder (⇧⌘G), then paste the path.",
      });
    } catch {
      toast.error("Could not copy path", {
        description: folderPath,
      });
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
  const orphanCount = summary.counts.orphan_files;
  const folderPath = summary.host_path || summary.temp_dir;

  return (
    <div className="console-theme space-y-5">
      <div>
        <p className="text-sm font-medium text-foreground">Disk usage</p>
        <p className="mt-1 text-2xl font-semibold text-foreground">
          {formatBytes(summary.total_bytes)}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {summary.counts.tasks} sessions · {summary.counts.clips} clips · {orphanCount} orphan
          file{orphanCount === 1 ? "" : "s"}
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
        <p>
          Orphan files are leftover media on disk that no longer belong to any session (deleted
          jobs, failed renders, stale caches). They are safe to delete if you do not need them.
        </p>
        <p className="mt-2">
          Files live under <code className="text-foreground">{folderPath}</code>. Deleting sessions
          removes their clips and unshared uploads from disk.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={() => void copyFolderPath()}>
          <FolderOpen className="mr-2 h-4 w-4" />
          Copy uploads folder path
        </Button>
        <Button
          type="button"
          variant="destructive"
          disabled={cleaning || orphanCount === 0}
          onClick={() => setConfirmDeleteAll(true)}
        >
          <Trash2 className="mr-2 h-4 w-4" />
          {cleaning ? "Deleting…" : "Delete all orphans"}
        </Button>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-medium text-foreground">Orphan files</p>
          <p className="text-xs text-muted-foreground">
            {orphanCount} file{orphanCount === 1 ? "" : "s"} · {formatBytes(orphanBytes)}
          </p>
        </div>

        {orphanCount === 0 ? (
          <div className="rounded-md border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">
            No orphan files
          </div>
        ) : (
          <div className="max-h-64 space-y-2 overflow-y-auto rounded-md border border-border p-2">
            {summary.orphan_files.map((file: OrphanFile) => (
              <div
                key={file.path}
                className="flex items-start justify-between gap-3 rounded-md bg-muted/20 px-3 py-2"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{file.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{file.relative_path}</p>
                  <p className="text-xs text-muted-foreground">{formatBytes(file.size_bytes)}</p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="shrink-0 text-red-500 hover:text-red-400"
                  disabled={cleaning || deletingPath === file.path}
                  onClick={() => void cleanupOrphans([file.path])}
                >
                  {deletingPath === file.path ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    "Delete"
                  )}
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      <AlertDialog open={confirmDeleteAll} onOpenChange={setConfirmDeleteAll}>
        <AlertDialogContent className="console-theme">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete all orphan files?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes {orphanCount} file{orphanCount === 1 ? "" : "s"} (
              {formatBytes(orphanBytes)}). Active session clips and uploads are not affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={cleaning}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={cleaning}
              className="bg-red-600 hover:bg-red-700"
              onClick={(event) => {
                event.preventDefault();
                void cleanupOrphans();
              }}
            >
              {cleaning ? "Deleting…" : "Delete all"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
