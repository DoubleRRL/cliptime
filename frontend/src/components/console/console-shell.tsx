"use client";

import { LeftRail } from "@/components/console/left-rail";
import { CenterClips } from "@/components/console/center-clips";
import { ClipEditorModal } from "@/components/console/clip-editor-modal";
import type { ConsoleClip, ConsoleSession, ConsoleSessionSettings } from "@/components/console/types";
import { ThemeToggle } from "@/components/theme-toggle";
import Link from "next/link";
import { useState } from "react";

type ConsoleShellProps = {
  apiUrl: string;
  sessions: ConsoleSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  clips: ConsoleClip[];
  onClipsChange: (clips: ConsoleClip[]) => void;
  sessionSettings: ConsoleSessionSettings | null;
  loading: boolean;
  onRefresh: () => void;
  onSessionCreated: (sessionId: string) => void;
  onClipReady?: (clip: Record<string, unknown>) => void;
  onClipUpdated: (clip: ConsoleClip) => void;
  onClipCreated: (clip: ConsoleClip) => void;
};

export function ConsoleShell({
  apiUrl,
  sessions,
  activeSessionId,
  onSelectSession,
  clips,
  onClipsChange,
  sessionSettings,
  loading,
  onRefresh,
  onSessionCreated,
  onClipReady,
  onClipUpdated,
  onClipCreated,
}: ConsoleShellProps) {
  const [activeClipId, setActiveClipId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);

  const activeClip = clips.find((clip) => clip.id === activeClipId) ?? null;
  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;

  const handleSelectClip = (clipId: string) => {
    setActiveClipId(clipId);
    setEditorOpen(true);
  };

  return (
    <div className="console-theme flex h-screen flex-col overflow-hidden">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-[var(--console-border)] px-4">
        <div className="flex items-center gap-3">
          <Link href="/" className="font-semibold tracking-tight text-[var(--console-text)]">
            SupoClip
          </Link>
        </div>
        <ThemeToggle />
      </header>

      <div className="flex min-h-0 flex-1">
        <LeftRail
          className="console-left-rail"
          apiUrl={apiUrl}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={onSelectSession}
          clips={clips}
          onClipsChange={onClipsChange}
          activeClipId={activeClipId}
          loading={loading}
          onRefresh={onRefresh}
          onSessionCreated={onSessionCreated}
          onSelectClip={handleSelectClip}
        />
        <CenterClips
          className="console-center-panel min-w-0 flex-1"
          apiUrl={apiUrl}
          taskId={activeSessionId}
          session={activeSession}
          sessionSettings={sessionSettings}
          clips={clips}
          activeClipId={activeClipId}
          onSelectClip={handleSelectClip}
          onClipReady={onClipReady}
        />
      </div>

      <ClipEditorModal
        apiUrl={apiUrl}
        taskId={activeSessionId}
        clip={activeClip}
        sessionSettings={sessionSettings}
        open={editorOpen}
        onOpenChange={setEditorOpen}
        onClipUpdated={onClipUpdated}
        onClipCreated={(clip) => {
          onClipCreated(clip);
          setActiveClipId(clip.id);
        }}
      />
    </div>
  );
}
