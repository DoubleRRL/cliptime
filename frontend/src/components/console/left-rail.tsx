"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { ConsoleClip, ConsoleSession } from "@/components/console/types";
import { Button } from "@/components/ui/button";
import { FolderOpen, Plus, RefreshCw } from "lucide-react";
import { NewSessionDialog } from "@/components/console/new-session-dialog";
import { SessionRow } from "@/components/console/session-row";
import { ClipQueueRow } from "@/components/console/clip-queue-row";

type LeftRailProps = {
  className?: string;
  apiUrl: string;
  sessions: ConsoleSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  clips: ConsoleClip[];
  onClipsChange: (clips: ConsoleClip[]) => void;
  activeClipId: string | null;
  loading: boolean;
  onRefresh: () => void;
  onSessionCreated: (sessionId: string) => void;
  onSelectClip: (clipId: string) => void;
};

export function LeftRail({
  className,
  apiUrl,
  sessions,
  activeSessionId,
  onSelectSession,
  clips,
  onClipsChange,
  activeClipId,
  loading,
  onRefresh,
  onSessionCreated,
  onSelectClip,
}: LeftRailProps) {
  const [newSessionOpen, setNewSessionOpen] = useState(false);
  const selectedCount = clips.filter((clip) => clip.selected).length;

  const toggleClip = (clipId: string) => {
    onClipsChange(
      clips.map((clip) =>
        clip.id === clipId ? { ...clip, selected: !clip.selected } : clip,
      ),
    );
  };

  return (
    <>
      <aside
        className={cn(
          "flex w-72 shrink-0 flex-col border-r border-[var(--console-border)] bg-[var(--console-rail-bg)] transition-all duration-300",
          className,
        )}
      >
        <div className="border-b border-[var(--console-border)] p-3">
          <Button
            type="button"
            className="w-full bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]"
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
            className="h-7 w-7"
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
                />
              </li>
            ))}
            {sessions.length === 0 && !loading && (
              <li className="rounded-lg border border-dashed border-[var(--console-border)] px-3 py-6 text-center text-xs text-[var(--console-text-muted)]">
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
            <div className="rounded-lg border border-dashed border-[var(--console-border)] px-3 py-6 text-center text-xs text-[var(--console-text-muted)]">
              Clips appear here after processing finishes.
            </div>
          ) : (
            <ul className="space-y-1.5">
              {clips.map((clip) => {
                const videoSrc = clip.videoUrl
                  ? `${apiUrl.replace(/\/$/, "")}${clip.videoUrl}`
                  : null;
                return (
                  <ClipQueueRow
                    key={clip.id}
                    clip={clip}
                    videoSrc={videoSrc}
                    isActive={clip.id === activeClipId}
                    onSelect={() => onSelectClip(clip.id)}
                    onToggleSelected={() => toggleClip(clip.id)}
                  />
                );
              })}
            </ul>
          )}
        </div>

        <div className="border-t border-[var(--console-border)] p-3">
          <Button
            type="button"
            className="w-full bg-[var(--console-terracotta)] hover:bg-[var(--console-terracotta-muted)]"
            disabled={selectedCount === 0}
          >
            <FolderOpen className="mr-2 h-4 w-4" />
            Export {selectedCount > 0 ? selectedCount : ""} selected
          </Button>
        </div>
      </aside>

      <NewSessionDialog
        open={newSessionOpen}
        onOpenChange={setNewSessionOpen}
        onCreated={onSessionCreated}
      />
    </>
  );
}
