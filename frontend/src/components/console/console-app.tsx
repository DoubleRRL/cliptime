"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ConsoleShell } from "@/components/console/console-shell";
import type { ConsoleSession, ConsoleClip, ConsoleSessionSettings } from "@/components/console/types";
import { useTaskProgress } from "@/hooks/use-task-progress";

const ACTIVE_SESSION_KEY = "supoclip:activeSessionId";

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

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? null;

  const loadSessions = useCallback(async () => {
    try {
      const response = await fetch("/api/tasks");
      if (!response.ok) return;
      const data = await response.json();
      const tasks = (data.tasks || data || []) as Array<Record<string, unknown>>;
      const mapped = tasks.map(mapTaskToSession);
      setSessions(mapped);
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
    }
  }, []);

  const loadClips = useCallback(async (taskId: string) => {
    const response = await fetch(`/api/tasks/${taskId}`);
    if (!response.ok) return;
    const task = await response.json();
    const rawClips = (task.clips || []) as Array<Record<string, unknown>>;
    setSessionSettings({
      fontFamily: String(task.font_family || "TikTokSans-Regular"),
      fontSize: Number(task.font_size ?? 28),
      fontColor: String(task.font_color || "#FFFFFF"),
      captionTemplate: String(task.caption_template || "riverside"),
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

  const handleClipCreated = useCallback((newClip: ConsoleClip) => {
    setClips((previous) => {
      if (previous.some((clip) => clip.id === newClip.id)) {
        return previous.map((clip) => (clip.id === newClip.id ? { ...clip, ...newClip } : clip));
      }
      return [...previous, newClip];
    });
  }, []);

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
      activeSessionId={activeSessionId}
      onSelectSession={handleSelectSession}
      clips={clips}
      onClipsChange={setClips}
      sessionSettings={sessionSettings}
      loading={loading}
      progress={progressState}
      onRefresh={loadSessions}
      onSessionCreated={(sessionId) => {
        setActiveSessionId(sessionId);
        void loadSessions();
      }}
      onDeleteSession={(sessionId) => void handleDeleteSession(sessionId)}
      onClipReady={handleClipReady}
      onClipUpdated={handleClipUpdated}
      onClipCreated={handleClipCreated}
    />
  );
}
