"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ConsoleShell } from "@/components/console/console-shell";
import type { ConsoleSession, ConsoleClip, ConsoleSessionSettings } from "@/components/console/types";
import { useTaskProgress } from "@/hooks/use-task-progress";
import { RIVERSIDE_CAPTION_DEFAULTS } from "@/lib/caption-defaults";
import { formatSupportMessage, parseApiError } from "@/lib/api-error";

const ACTIVE_SESSION_KEY = "supoclip:activeSessionId";
const SESSION_PAGE_SIZE = 100;

function mapTaskToSession(task: Record<string, unknown>): ConsoleSession {
  const progressRaw = task.progress;
  const progress =
    typeof progressRaw === "number"
      ? progressRaw
      : progressRaw != null && progressRaw !== ""
        ? Number(progressRaw)
        : undefined;

  return {
    id: String(task.id),
    title: String(task.source_title || task.title || "Untitled"),
    status: String(task.status || "unknown"),
    clipsCount: Number(task.clips_count ?? 0),
    createdAt: String(task.created_at || ""),
    progress: Number.isFinite(progress) ? progress : undefined,
    progressMessage: String(task.progress_message || ""),
    llmModel:
      task.llm_model != null && task.llm_model !== ""
        ? String(task.llm_model)
        : null,
  };
}

function mapClip(raw: Record<string, unknown>, index: number): ConsoleClip {
  return {
    id: String(raw.id),
    title: String(raw.title || raw.text || `Clip ${index + 1}`),
    postTitle: String(raw.post_title || ""),
    startTime: String(raw.start_time || ""),
    endTime: String(raw.end_time || ""),
    durationSeconds: Number(raw.duration ?? 0),
    viralityScore: Number(raw.virality_score ?? 0),
    hookScore: Number(raw.hook_score ?? 0),
    engagementScore: Number(raw.engagement_score ?? 0),
    valueScore: Number(raw.value_score ?? 0),
    shareabilityScore: Number(raw.shareability_score ?? 0),
    clipOrder: Number(raw.clip_order ?? index + 1),
    filename: String(raw.filename || ""),
    videoUrl: raw.video_url ? `/api${String(raw.video_url)}` : "",
    text: String(raw.text || ""),
    reasoning: String(raw.reasoning || ""),
    hookType: raw.hook_type ? String(raw.hook_type) : null,
    selected: false,
    parentClipId: raw.parent_clip_id ? String(raw.parent_clip_id) : undefined,
  };
}

export function ConsoleApp() {
  const [sessions, setSessions] = useState<ConsoleSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [clips, setClips] = useState<ConsoleClip[]>([]);
  const [sessionSettings, setSessionSettings] = useState<ConsoleSessionSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMoreSessions, setLoadingMoreSessions] = useState(false);
  const [sessionTotal, setSessionTotal] = useState(0);
  const [storageRefreshKey, setStorageRefreshKey] = useState(0);
  const [regeneratingClipId, setRegeneratingClipId] = useState<string | null>(null);
  const [cancellingSessionId, setCancellingSessionId] = useState<string | null>(null);

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const allTasks: Array<Record<string, unknown>> = [];
      let offset = 0;
      let total = 0;

      while (true) {
        if (offset > 0) {
          setLoadingMoreSessions(true);
        }

        const response = await fetch(
          `/api/tasks?limit=${SESSION_PAGE_SIZE}&offset=${offset}`,
        );
        if (!response.ok) {
          break;
        }

        const data = await response.json();
        const page = (data.tasks || []) as Array<Record<string, unknown>>;
        total = Number(data.total ?? page.length);
        allTasks.push(...page);

        const hasMore = Boolean(data.has_more);
        if (!hasMore || page.length === 0) {
          break;
        }
        offset += SESSION_PAGE_SIZE;
      }

      const mapped = allTasks.map(mapTaskToSession);
      setSessions(mapped);
      setSessionTotal(total);
      setActiveSessionId((current) => {
        if (current && mapped.some((session) => session.id === current)) {
          return current;
        }
        const stored =
          typeof window !== "undefined"
            ? window.sessionStorage.getItem(ACTIVE_SESSION_KEY)
            : null;
        if (stored && mapped.some((session) => session.id === stored)) {
          return stored;
        }
        return mapped[0]?.id ?? null;
      });
    } finally {
      setLoading(false);
      setLoadingMoreSessions(false);
    }
  }, []);

  const loadClips = useCallback(async (taskId: string) => {
    const response = await fetch(`/api/tasks/${taskId}`);
    if (!response.ok) return;
    const task = await response.json();
    const rawClips = (task.clips || []) as Array<Record<string, unknown>>;
    setSessionSettings({
      fontFamily: String(task.font_family || "TikTokSans-Regular"),
      fontSize: Number(task.font_size ?? RIVERSIDE_CAPTION_DEFAULTS.fontSize),
      fontColor: String(task.font_color || "#FFFFFF"),
      captionTemplate: String(task.caption_template || "riverside"),
      tightCuts: task.tight_cuts !== false,
    });
    setClips((previous) => {
      const selectedById = new Map(previous.map((clip) => [clip.id, clip.selected]));
      return rawClips.map((clip, index) => ({
        ...mapClip(clip, index),
        selected: selectedById.get(String(clip.id)) ?? false,
      }));
    });
    const hydrated = mapTaskToSession({ ...task, clips_count: rawClips.length });
    setSessions((previous) =>
      previous.map((session) =>
        session.id === taskId
          ? {
              ...session,
              ...hydrated,
              clipsCount: rawClips.length,
            }
          : session,
      ),
    );
  }, []);

  const handleClipReady = useCallback(
    (clipData: Record<string, unknown>) => {
      const clip = mapClip(clipData, clips.length);
      setClips((previous) => {
        if (previous.some((entry) => entry.id === clip.id)) return previous;
        return [...previous, clip];
      });
      if (activeSessionId) {
        void loadClips(activeSessionId);
      }
    },
    [activeSessionId, clips.length, loadClips],
  );

  const handleFinished = useCallback(
    (status: string) => {
      if (activeSessionId) {
        setSessions((previous) =>
          previous.map((session) =>
            session.id === activeSessionId ? { ...session, status } : session,
          ),
        );
        void loadClips(activeSessionId);
        void loadSessions();
      }
    },
    [activeSessionId, loadClips, loadSessions],
  );

  const progressState = useTaskProgress({
    taskId: activeSessionId,
    taskStatus: activeSession?.status ?? null,
    initialProgress: activeSession?.progress ?? 0,
    initialMessage: activeSession?.progressMessage ?? "",
    onClipReady: handleClipReady,
    onFinished: handleFinished,
  });

  const handleClipUpdated = useCallback((updated: ConsoleClip) => {
    setClips((previous) =>
      previous.map((clip) => (clip.id === updated.id ? { ...clip, ...updated } : clip)),
    );
  }, []);

  const handleClipCreated = useCallback(
    (newClip: ConsoleClip) => {
      setClips((previous) => {
        if (previous.some((clip) => clip.id === newClip.id)) {
          return previous.map((clip) => (clip.id === newClip.id ? { ...clip, ...newClip } : clip));
        }
        return [...previous, newClip];
      });
      if (activeSessionId) {
        void loadClips(activeSessionId);
      }
    },
    [activeSessionId, loadClips],
  );

  const handleClipDeleted = useCallback(
    (clipId: string) => {
      setClips((previous) => previous.filter((clip) => clip.id !== clipId));
      if (activeSessionId) {
        void loadClips(activeSessionId);
      }
    },
    [activeSessionId, loadClips],
  );

  const handleSelectSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
  }, []);

  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      const response = await fetch(`/api/tasks/${sessionId}`, { method: "DELETE" });
      if (!response.ok) {
        const detail =
          response.status === 403
            ? "Not authorized to delete this session"
            : response.status === 404
              ? "Session not found"
              : "Failed to delete session";
        toast.error(detail);
        return;
      }

      setSessions((previous) => {
        const remaining = previous.filter((session) => session.id !== sessionId);
        setSessionTotal((current) => Math.max(0, current - 1));
        setStorageRefreshKey((current) => current + 1);
        setActiveSessionId((current) => {
          if (current !== sessionId) return current;
          if (current === sessionId) {
            setClips([]);
            setSessionSettings(null);
          }
          return remaining[0]?.id ?? null;
        });
        return remaining;
      });
      toast.success("Session deleted");
    },
    [],
  );

  const handleCancelSession = useCallback(
    async (sessionId: string) => {
      setCancellingSessionId(sessionId);
      try {
        const response = await fetch(`/api/tasks/${sessionId}/cancel`, { method: "POST" });
        if (!response.ok) {
          const parsed = await parseApiError(response, "Failed to stop generation");
          toast.error(formatSupportMessage(parsed));
          return;
        }

        setSessions((previous) =>
          previous.map((session) =>
            session.id === sessionId
              ? {
                  ...session,
                  status: "cancelled",
                  progressMessage: "Cancelled by user",
                }
              : session,
          ),
        );

        if (sessionId === activeSessionId) {
          handleFinished("cancelled");
        }

        toast.success("Generation stopped");
        void loadSessions();
      } finally {
        setCancellingSessionId(null);
      }
    },
    [activeSessionId, handleFinished, loadSessions],
  );

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (activeSessionId) {
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
      }
      void loadClips(activeSessionId);
    } else {
      if (typeof window !== "undefined") {
        window.sessionStorage.removeItem(ACTIVE_SESSION_KEY);
      }
      setClips([]);
      setSessionSettings(null);
    }
  }, [activeSessionId, loadClips]);

  return (
    <ConsoleShell
      sessions={sessions}
      sessionTotal={sessionTotal}
      activeSessionId={activeSessionId}
      onSelectSession={handleSelectSession}
      clips={clips}
      onClipsChange={setClips}
      sessionSettings={sessionSettings}
      loading={loading}
      loadingMoreSessions={loadingMoreSessions}
      storageRefreshKey={storageRefreshKey}
      onStorageChanged={() => setStorageRefreshKey((current) => current + 1)}
      progress={progressState}
      onRefresh={loadSessions}
      onSessionCreated={(sessionId) => {
        setActiveSessionId(sessionId);
        void loadSessions();
      }}
      onDeleteSession={(sessionId) => void handleDeleteSession(sessionId)}
      onCancelSession={(sessionId) => void handleCancelSession(sessionId)}
      cancellingSessionId={cancellingSessionId}
      onClipReady={handleClipReady}
      onClipUpdated={handleClipUpdated}
      onClipCreated={handleClipCreated}
      onClipDeleted={handleClipDeleted}
      regeneratingClipId={regeneratingClipId}
      onRegeneratingChange={setRegeneratingClipId}
    />
  );
}
