"use client";

import { useCallback, useEffect, useState } from "react";
import { ConsoleShell } from "@/components/console/console-shell";
import type { ConsoleSession, ConsoleClip, ConsoleSessionSettings } from "@/components/console/types";

const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function mapClip(raw: Record<string, unknown>, index: number): ConsoleClip {
  return {
    id: String(raw.id),
    title: String(raw.title || raw.text || `Clip ${index + 1}`),
    postTitle: String(raw.post_title || ""),
    startTime: String(raw.start_time || ""),
    endTime: String(raw.end_time || ""),
    durationSeconds: Number(raw.duration ?? 0),
    viralityScore: Number(raw.virality_score ?? 0),
    filename: String(raw.filename || ""),
    videoUrl: String(raw.video_url || ""),
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

  const loadSessions = useCallback(async () => {
    try {
      const response = await fetch("/api/tasks");
      if (!response.ok) return;
      const data = await response.json();
      const tasks = (data.tasks || data || []) as Array<Record<string, unknown>>;
      const mapped: ConsoleSession[] = tasks.map((task) => ({
        id: String(task.id),
        title: String(task.source_title || task.title || "Untitled"),
        status: String(task.status || "unknown"),
        clipsCount: Number(task.clips_count ?? 0),
        createdAt: String(task.created_at || ""),
      }));
      setSessions(mapped);
      setActiveSessionId((current) => {
        if (current && mapped.some((session) => session.id === current)) {
          return current;
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

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (activeSessionId) {
      void loadClips(activeSessionId);
    } else {
      setClips([]);
      setSessionSettings(null);
    }
  }, [activeSessionId, loadClips]);

  return (
    <ConsoleShell
      apiUrl={apiUrl}
      sessions={sessions}
      activeSessionId={activeSessionId}
      onSelectSession={setActiveSessionId}
      clips={clips}
      onClipsChange={setClips}
      sessionSettings={sessionSettings}
      loading={loading}
      onRefresh={loadSessions}
      onSessionCreated={(sessionId) => {
        setActiveSessionId(sessionId);
        void loadSessions();
      }}
      onClipReady={handleClipReady}
      onClipUpdated={handleClipUpdated}
      onClipCreated={handleClipCreated}
    />
  );
}
