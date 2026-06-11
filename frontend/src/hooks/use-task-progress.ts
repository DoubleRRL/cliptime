"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type TaskProgressState = {
  progress: number;
  message: string;
  status: string | null;
  activityLog: string[];
};

type UseTaskProgressOptions = {
  taskId: string | null;
  /** Current task status; the stream only runs while queued/processing. */
  taskStatus: string | null;
  /** Server-persisted progress (hydrated after reload). */
  initialProgress?: number;
  initialMessage?: string;
  onClipReady?: (clip: Record<string, unknown>) => void;
  /** Called once when the task reaches a terminal state (completed/error/cancelled). */
  onFinished?: (status: string) => void;
};

const ACTIVE_STATUSES = new Set(["queued", "processing"]);
const MAX_RECONNECT_DELAY_MS = 15_000;

/**
 * Subscribe to a task's SSE progress stream with automatic reconnect + backoff.
 * Terminal states surface through `onFinished`. Progress hydrates from the server on remount.
 */
export function useTaskProgress({
  taskId,
  taskStatus,
  initialProgress = 0,
  initialMessage = "",
  onClipReady,
  onFinished,
}: UseTaskProgressOptions): TaskProgressState {
  const [progress, setProgress] = useState(initialProgress);
  const [message, setMessage] = useState(initialMessage);
  const [status, setStatus] = useState<string | null>(taskStatus);
  const [activityLog, setActivityLog] = useState<string[]>(
    initialMessage ? [initialMessage] : [],
  );

  const callbacksRef = useRef({ onClipReady, onFinished });
  callbacksRef.current = { onClipReady, onFinished };
  const previousTaskIdRef = useRef<string | null>(null);

  const appendActivity = useCallback((entry: string) => {
    if (!entry) return;
    setActivityLog((previous) => {
      if (previous[previous.length - 1] === entry) return previous;
      return [...previous.slice(-19), entry];
    });
  }, []);

  useEffect(() => {
    setStatus(taskStatus);

    const previousTaskId = previousTaskIdRef.current;
    const taskChanged = taskId !== previousTaskId;
    previousTaskIdRef.current = taskId;

    if (taskChanged) {
      if (taskId && taskStatus && ACTIVE_STATUSES.has(taskStatus)) {
        setProgress(initialProgress);
        setMessage(initialMessage);
        setActivityLog(initialMessage ? [initialMessage] : []);
      } else if (!taskId) {
        setActivityLog([]);
        setProgress(0);
        setMessage("");
      }
    }
  }, [taskId, taskStatus, initialProgress, initialMessage]);

  // Hydrate when API values arrive after mount (same task, remount, or list refresh).
  useEffect(() => {
    if (!taskId || !taskStatus || !ACTIVE_STATUSES.has(taskStatus)) return;

    if (initialProgress > 0) {
      setProgress((current) => (current > 0 ? current : initialProgress));
    }
    if (initialMessage) {
      setMessage((current) => current || initialMessage);
      setActivityLog((log) => (log.length === 0 ? [initialMessage] : log));
    }
  }, [taskId, taskStatus, initialProgress, initialMessage]);

  useEffect(() => {
    if (!taskId || !taskStatus || !ACTIVE_STATUSES.has(taskStatus)) return;

    let eventSource: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let reconnectAttempt = 0;
    let finished = false;
    let disposed = false;

    const finish = (finalStatus: string) => {
      if (finished) return;
      finished = true;
      setStatus(finalStatus);
      callbacksRef.current.onFinished?.(finalStatus);
    };

    const handleUpdate = (data: Record<string, unknown>) => {
      reconnectAttempt = 0;
      if (typeof data.progress === "number") setProgress(data.progress);
      if (typeof data.message === "string" && data.message) {
        setMessage(data.message);
        appendActivity(data.message);
      }
      if (typeof data.status === "string" && data.status) {
        setStatus(data.status);
        if (!ACTIVE_STATUSES.has(data.status)) {
          finish(data.status);
        }
      }
    };

    const connect = () => {
      if (disposed || finished) return;
      eventSource = new EventSource(`/api/tasks/${taskId}/progress`);

      const onJson = (handler: (data: Record<string, unknown>) => void) =>
        (event: MessageEvent<string>) => {
          try {
            handler(JSON.parse(event.data));
          } catch {
            // Ignore malformed events.
          }
        };

      eventSource.addEventListener("status", onJson(handleUpdate));
      eventSource.addEventListener("progress", onJson(handleUpdate));

      eventSource.addEventListener(
        "clip_ready",
        onJson((data) => {
          reconnectAttempt = 0;
          const clip = data.clip as Record<string, unknown> | undefined;
          if (clip) callbacksRef.current.onClipReady?.(clip);
        }),
      );

      eventSource.addEventListener(
        "close",
        onJson((data) => {
          eventSource?.close();
          finish(String(data.status || "completed"));
        }),
      );

      eventSource.onerror = () => {
        eventSource?.close();
        if (disposed || finished) return;
        const delay = Math.min(
          1000 * 2 ** reconnectAttempt,
          MAX_RECONNECT_DELAY_MS,
        );
        reconnectAttempt += 1;
        reconnectTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      disposed = true;
      eventSource?.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [taskId, taskStatus, appendActivity]);

  return { progress, message, status, activityLog };
}
