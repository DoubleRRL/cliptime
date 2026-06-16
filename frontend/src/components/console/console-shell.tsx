"use client";

import { LeftRail } from "@/components/console/left-rail";
import { CenterClips } from "@/components/console/center-clips";
import { ClipEditorModal } from "@/components/console/clip-editor-modal";
import { SettingsModal } from "@/components/console/settings-modal";
import type { ConsoleClip, ConsoleSession, ConsoleSessionSettings } from "@/components/console/types";
import { ThemeToggle } from "@/components/theme-toggle";
import type { TaskProgressState } from "@/hooks/use-task-progress";
import Link from "next/link";
import { Menu, Settings } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type SettingsSection = "defaults" | "storage" | "admin";

type ConsoleShellProps = {
  sessions: ConsoleSession[];
  sessionTotal: number;
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  clips: ConsoleClip[];
  onClipsChange: (clips: ConsoleClip[]) => void;
  sessionSettings: ConsoleSessionSettings | null;
  loading: boolean;
  loadingMoreSessions?: boolean;
  storageRefreshKey?: number;
  onStorageChanged?: () => void;
  progress: TaskProgressState;
  onRefresh: () => void;
  onSessionCreated: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onCancelSession?: (sessionId: string) => void;
  cancellingSessionId?: string | null;
  onClipReady?: (clip: Record<string, unknown>) => void;
  onClipUpdated: (clip: ConsoleClip) => void;
  onClipCreated: (clip: ConsoleClip) => void;
  onClipDeleted?: (clipId: string) => void;
  regeneratingClipId?: string | null;
  onRegeneratingChange?: (clipId: string | null) => void;
};

export function ConsoleShell({
  sessions,
  sessionTotal,
  activeSessionId,
  onSelectSession,
  clips,
  onClipsChange,
  sessionSettings,
  loading,
  loadingMoreSessions = false,
  storageRefreshKey = 0,
  onStorageChanged,
  progress,
  onRefresh,
  onSessionCreated,
  onDeleteSession,
  onCancelSession,
  cancellingSessionId = null,
  onClipReady,
  onClipUpdated,
  onClipCreated,
  onClipDeleted,
  regeneratingClipId = null,
  onRegeneratingChange,
}: ConsoleShellProps) {
  const [activeClipId, setActiveClipId] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [mobileRailOpen, setMobileRailOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>("defaults");

  const activeClip = clips.find((clip) => clip.id === activeClipId) ?? null;
  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;

  const handleSelectClip = (clipId: string) => {
    setActiveClipId(clipId);
    setEditorOpen(true);
    setMobileRailOpen(false);
  };

  const handleSelectSession = (id: string) => {
    setEditorOpen(false);
    setActiveClipId(null);
    onSelectSession(id);
    setMobileRailOpen(false);
  };

  const openSettings = (section: SettingsSection = "defaults") => {
    setSettingsSection(section);
    setSettingsOpen(true);
  };

  useEffect(() => {
    setEditorOpen(false);
    setActiveClipId(null);
  }, [activeSessionId]);

  return (
    <div className="console-theme flex h-[100dvh] flex-col overflow-hidden">
      <header className="relative z-[60] flex h-12 shrink-0 items-center justify-between border-b border-[var(--console-border)] px-3 sm:px-4">
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 md:hidden"
            onClick={() => setMobileRailOpen((open) => !open)}
            aria-label="Toggle sessions panel"
          >
            <Menu className="h-4 w-4" />
          </Button>
          <Link
            href="/"
            className="font-display text-base font-semibold tracking-tight text-[var(--console-text)] transition-opacity hover:opacity-80"
          >
            Cliptime
          </Link>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            className="h-8 gap-1.5 px-3 text-sm text-[var(--console-text-muted)] hover:text-[var(--console-text)]"
            onClick={() => openSettings("defaults")}
          >
            <Settings className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Settings</span>
          </Button>
          <ThemeToggle />
        </div>
      </header>

      <div className="relative flex min-h-0 flex-1">
        {mobileRailOpen && (
          <button
            type="button"
            className="absolute inset-0 z-20 bg-black/50 backdrop-blur-[2px] md:hidden"
            aria-label="Close sessions panel"
            onClick={() => setMobileRailOpen(false)}
          />
        )}

        <LeftRail
          className={cn(
            "console-left-rail z-30 transition-transform duration-300 ease-out",
            "max-md:absolute max-md:inset-y-0 max-md:left-0 max-md:shadow-2xl",
            mobileRailOpen ? "max-md:translate-x-0" : "max-md:-translate-x-full",
          )}
          taskId={activeSessionId}
          sessions={sessions}
          sessionTotal={sessionTotal}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          clips={clips}
          onClipsChange={onClipsChange}
          activeClipId={activeClipId}
          loading={loading}
          loadingMoreSessions={loadingMoreSessions}
          storageRefreshKey={storageRefreshKey}
          onOpenStorage={() => openSettings("storage")}
          onRefresh={onRefresh}
          onSessionCreated={onSessionCreated}
          onDeleteSession={onDeleteSession}
          onCancelSession={onCancelSession}
          cancellingSessionId={cancellingSessionId}
          onSelectClip={handleSelectClip}
          regeneratingClipId={regeneratingClipId}
        />

        <CenterClips
          className="console-center-panel min-w-0 flex-1"
          taskId={activeSessionId}
          session={activeSession}
          sessionSettings={sessionSettings}
          clips={clips}
          activeClipId={activeClipId}
          progress={progress}
          regeneratingClipId={regeneratingClipId}
          onSelectClip={handleSelectClip}
          onClipReady={onClipReady}
          onCancelSession={
            activeSessionId && onCancelSession
              ? () => onCancelSession(activeSessionId)
              : undefined
          }
          isCancelling={Boolean(activeSessionId && cancellingSessionId === activeSessionId)}
        />
      </div>

      <ClipEditorModal
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
        onClipDeleted={(clipId) => {
          onClipDeleted?.(clipId);
          setActiveClipId(null);
          setEditorOpen(false);
        }}
        onRegeneratingChange={onRegeneratingChange}
      />

      <SettingsModal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        initialSection={settingsSection}
        storageRefreshKey={storageRefreshKey}
        onStorageChanged={onStorageChanged}
      />
    </div>
  );
}
