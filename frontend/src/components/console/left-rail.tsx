"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { ConsoleClip, ConsoleSession } from "@/components/console/types";
import { Button } from "@/components/ui/button";
import { Download, FolderOpen, Plus, RefreshCw } from "lucide-react";
import { NewSessionDialog } from "@/components/console/new-session-dialog";
import { SessionRow } from "@/components/console/session-row";
import { ClipQueueRow } from "@/components/console/clip-queue-row";
import { toast } from "sonner";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";
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

type LeftRailProps = {
  className?: string;
  taskId: string | null;
  sessions: ConsoleSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  clips: ConsoleClip[];
  onClipsChange: (clips: ConsoleClip[]) => void;
  activeClipId: string | null;
  loading: boolean;
  onRefresh: () => void;
  onSessionCreated: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onSelectClip: (clipId: string) => void;
  regeneratingClipId?: string | null;
};

export function LeftRail({
  className,
  taskId,
  sessions,
  activeSessionId,
  onSelectSession,
  clips,
  onClipsChange,
  activeClipId,
  loading,
  onRefresh,
  onSessionCreated,
  onDeleteSession,
  onSelectClip,
  regeneratingClipId = null,
}: LeftRailProps) {
  const [newSessionOpen, setNewSessionOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const deleteTarget = sessions.find((session) => session.id === deleteTargetId) ?? null;
  const activeClipRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    activeClipRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeClipId]);
  const selectedClips = clips.filter((clip) => clip.selected);
  const selectedCount = selectedClips.length;

  const toggleClip = (clipId: string) => {
    onClipsChange(
      clips.map((clip) =>
        clip.id === clipId ? { ...clip, selected: !clip.selected } : clip,
      ),
    );
  };

  const handleExportSelected = async () => {
    if (!taskId || selectedCount === 0) return;
    setExporting(true);
    try {
      for (const clip of selectedClips) {
        const response = await fetch(
          `/api/tasks/${taskId}/clips/${clip.id}/export?preset=tiktok`,
        );
        if (!response.ok) {
          const parsed = await parseApiError(
            response,
            `Export failed for ${clip.filename || clip.id}`,
          );
          throw new Error(formatSupportMessage(parsed));
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = clip.filename || `${clip.id}.mp4`;
        anchor.click();
        URL.revokeObjectURL(url);
      }
      toast.success(
        selectedCount === 1
          ? "Clip exported"
          : `Exported ${selectedCount} clips`,
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <aside
        className={cn(
          "flex w-72 shrink-0 flex-col border-r border-[var(--console-border)] bg-[var(--console-rail-bg)]",
          className,
        )}
      >
        <div className="border-b border-[var(--console-border)] p-3">
          <Button
            type="button"
            className="w-full bg-[var(--console-terracotta)] shadow-sm transition-transform active:scale-[0.98] hover:bg-[var(--console-terracotta-muted)]"
            onClick={() => setNewSessionOpen(true)}
          >
            <Plus className="mr-2 h-4 w-4" />
            New session
          </Button>
        </div>

        <div className="flex items-center justify-between border-b border-[var(--console-border)] px-3 py-2">
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
            Sessions
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 transition-colors hover:bg-[var(--console-rail-hover)]"
            onClick={onRefresh}
            title="Refresh sessions"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          </Button>
        </div>

        <div className="max-h-[38%] overflow-y-auto p-2">
          <ul className="space-y-1.5">
            {sessions.map((session) => (
              <li key={session.id}>
                <SessionRow
                  session={session}
                  isActive={session.id === activeSessionId}
                  onSelect={() => onSelectSession(session.id)}
                  onDelete={() => setDeleteTargetId(session.id)}
                />
              </li>
            ))}
            {sessions.length === 0 && !loading && (
              <li className="rounded-xl border border-dashed border-[var(--console-border)] px-3 py-6 text-center text-xs text-[var(--console-text-muted)]">
                No sessions yet. Start one with a YouTube link or video upload.
              </li>
            )}
          </ul>
        </div>

        <div className="border-t border-[var(--console-border)] px-3 py-2">
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
            Clip queue
          </span>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {clips.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--console-border)] px-3 py-6 text-center text-xs text-[var(--console-text-muted)]">
              Clips appear here after processing finishes.
            </div>
          ) : (
            <ul className="space-y-1.5">
              {clips.map((clip) => (
                <li
                  key={clip.id}
                  ref={clip.id === activeClipId ? activeClipRef : undefined}
                >
                  <ClipQueueRow
                    clip={clip}
                    videoSrc={clip.videoUrl || null}
                    isActive={clip.id === activeClipId}
                    isRegenerating={clip.id === regeneratingClipId}
                    onSelect={() => onSelectClip(clip.id)}
                    onToggleSelected={() => toggleClip(clip.id)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border-t border-[var(--console-border)] p-3">
          <Button
            type="button"
            className="w-full bg-[var(--console-terracotta)] transition-transform active:scale-[0.98] hover:bg-[var(--console-terracotta-muted)]"
            disabled={selectedCount === 0 || exporting}
            onClick={() => void handleExportSelected()}
          >
            {exporting ? (
              <Download className="mr-2 h-4 w-4 animate-pulse" />
            ) : (
              <FolderOpen className="mr-2 h-4 w-4" />
            )}
            Export {selectedCount > 0 ? selectedCount : ""} selected
          </Button>
        </div>
      </aside>

      <NewSessionDialog
        open={newSessionOpen}
        onOpenChange={setNewSessionOpen}
        onCreated={onSessionCreated}
      />

      <AlertDialog
        open={deleteTargetId != null}
        onOpenChange={(open) => {
          if (!open) setDeleteTargetId(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete session?</AlertDialogTitle>
            <AlertDialogDescription>
              Delete &ldquo;{deleteTarget?.title ?? "this session"}&rdquo; and its clips?
              Uploaded source video will be removed if no other session uses it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (deleteTargetId) {
                  onDeleteSession(deleteTargetId);
                  setDeleteTargetId(null);
                }
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
