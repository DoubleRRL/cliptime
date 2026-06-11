"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import type { ConsoleClip, ConsoleSession, ConsoleSessionSettings } from "@/components/console/types";
import { ClipCard } from "@/components/console/clip-card";
import { ClipGridZoom } from "@/components/console/clip-grid-zoom";
import { CustomClipPanel } from "@/components/custom-clip-panel";
import {
  CLIP_GAP,
  DEFAULT_CLIP_ZOOM,
  useClipGridLayout,
} from "@/components/console/use-clip-grid-layout";

type CenterClipsProps = {
  className?: string;
  apiUrl: string;
  taskId: string | null;
  session: ConsoleSession | null;
  sessionSettings: ConsoleSessionSettings | null;
  clips: ConsoleClip[];
  activeClipId: string | null;
  onSelectClip: (id: string) => void;
  onClipReady?: (clip: Record<string, unknown>) => void;
};

export function CenterClips({
  className,
  apiUrl,
  taskId,
  session,
  sessionSettings,
  clips,
  activeClipId,
  onSelectClip,
  onClipReady,
}: CenterClipsProps) {
  const gridRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(DEFAULT_CLIP_ZOOM);
  const { rows, setContainerWidth } = useClipGridLayout(clips.length, zoom);

  useEffect(() => {
    const node = gridRef.current;
    if (!node) return;

    const updateWidth = () => setContainerWidth(node.clientWidth);
    updateWidth();

    const observer = new ResizeObserver(updateWidth);
    observer.observe(node);
    return () => observer.disconnect();
  }, [clips.length, setContainerWidth]);

  if (!taskId) {
    return (
      <main
        className={cn(
          "flex flex-col items-center justify-center bg-[var(--console-charcoal)] p-8 text-center",
          className,
        )}
      >
        <p className="max-w-sm text-[var(--console-text-muted)]">
          Start a session from the left rail — paste a YouTube link or drop a video file.
        </p>
      </main>
    );
  }

  const captionTemplate = sessionSettings?.captionTemplate ?? "riverside";
  const fontFamily = sessionSettings?.fontFamily ?? "TikTokSans-Regular";
  const fontSize = sessionSettings?.fontSize ?? 28;
  const fontColor = sessionSettings?.fontColor ?? "#FFFFFF";

  return (
    <main className={cn("flex min-h-0 flex-col bg-[var(--console-charcoal)]", className)}>
      <div className="border-b border-[var(--console-border)] px-4 py-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-medium text-[var(--console-text)]">
              {session?.title ?? "Session"}
            </h1>
            <p className="text-xs text-[var(--console-text-muted)]">
              {session?.status ?? "unknown"} · {clips.length} clip{clips.length === 1 ? "" : "s"}
            </p>
          </div>
          {clips.length > 0 && <ClipGridZoom zoom={zoom} onZoomChange={setZoom} />}
        </div>
      </div>

      <div ref={gridRef} className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {clips.length === 0 ? (
          <div className="flex h-full min-h-[240px] items-center justify-center rounded-xl border border-dashed border-[var(--console-border)] text-sm text-[var(--console-text-muted)]">
            Clips will appear here once processing finishes.
          </div>
        ) : (
          <div className="space-y-4">
            {rows.map((row) => (
              <div
                key={`row-${row.startIndex}`}
                className="flex flex-wrap justify-center"
                style={{ gap: CLIP_GAP }}
              >
                {clips.slice(row.startIndex, row.startIndex + row.count).map((clip) => {
                  const videoSrc = clip.videoUrl
                    ? `${apiUrl.replace(/\/$/, "")}${clip.videoUrl}`
                    : null;

                  return (
                    <ClipCard
                      key={clip.id}
                      clip={clip}
                      videoSrc={videoSrc}
                      width={row.cardWidth}
                      isActive={clip.id === activeClipId}
                      onClick={() => onSelectClip(clip.id)}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="console-action-panel shrink-0 border-t border-[var(--console-border)] px-4 py-5">
        <p className="mb-3 text-xs font-medium uppercase tracking-wider text-[var(--console-text-muted)]">
          Create more clips
        </p>
        <CustomClipPanel
          taskId={taskId}
          taskApiUrl="/api/tasks"
          captionTemplate={captionTemplate}
          fontFamily={fontFamily}
          fontSize={fontSize}
          fontColor={fontColor}
          emptyState={clips.length === 0}
          variant="console"
          onClipReady={onClipReady}
        />
      </div>
    </main>
  );
}
