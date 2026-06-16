"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  CaptionStylePreview,
  type CaptionStyleTemplate,
} from "@/components/console/caption-style-preview";
import { burnedInToBase } from "@/lib/caption-fit";
import { cn } from "@/lib/utils";

const SAMPLE_WORDS = ["Your", "subtitle", "here"];
const CAPTION_SETTINGS_PREVIEW_IMAGE = "/images/caption-settings-preview.jpg";
const DEFAULT_FRAME_WIDTH = 300;
const MIN_FRAME_WIDTH = 220;
const MAX_FRAME_WIDTH = 420;

type SettingsCaptionPreviewProps = {
  fontFamily: string;
  burnedInPx: number;
  fontColor: string;
  highlightColor: string;
  textBackgroundColor: string;
  template: CaptionStyleTemplate | null;
  positionY: number;
};

export function SettingsCaptionPreview({
  fontFamily,
  burnedInPx,
  fontColor,
  highlightColor,
  textBackgroundColor,
  template,
  positionY,
}: SettingsCaptionPreviewProps) {
  const [frameWidth, setFrameWidth] = useState(DEFAULT_FRAME_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const baseFontSize = burnedInToBase(burnedInPx);

  const clampWidth = useCallback((width: number) => {
    const containerMax = containerRef.current?.clientWidth ?? MAX_FRAME_WIDTH;
    const maxWidth = Math.min(MAX_FRAME_WIDTH, containerMax);
    return Math.max(MIN_FRAME_WIDTH, Math.min(maxWidth, Math.round(width)));
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handlePointerMove = (event: PointerEvent) => {
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const nextWidth = (event.clientX - centerX) * 2;
      setFrameWidth(clampWidth(nextWidth));
    };

    const handlePointerUp = () => setIsResizing(false);

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [clampWidth, isResizing]);

  return (
    <div className="space-y-2" data-testid="settings-caption-preview" ref={containerRef}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-foreground">Caption preview</p>
        <p className="text-[11px] text-muted-foreground">Drag corner to resize</p>
      </div>
      <div className="flex justify-center">
        <div
          className="relative"
          data-testid="caption-preview-frame"
          style={{ width: frameWidth, aspectRatio: "9 / 16" }}
        >
          <div
            className={cn(
              "relative h-full w-full overflow-hidden rounded-xl bg-black",
              "ring-2 ring-border ring-offset-2 ring-offset-[var(--console-beige,var(--background))]",
            )}
          >
            <CaptionStylePreview
              fontFamily={fontFamily}
              fontSize={baseFontSize}
              fontColor={fontColor}
              highlightColor={highlightColor}
              textBackgroundColor={textBackgroundColor}
              template={template}
              positionY={positionY}
              sampleWords={SAMPLE_WORDS.map((word) => word.toUpperCase())}
              emphasisCallouts
              frameWidth={frameWidth}
              backgroundImageUrl={CAPTION_SETTINGS_PREVIEW_IMAGE}
              showPositionGuide
            />
            <span
              className="absolute right-2 top-2 z-20 rounded-md bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white"
              data-testid="export-px-badge"
            >
              {burnedInPx}px
            </span>
          </div>
          <button
            type="button"
            aria-label="Resize caption preview"
            data-testid="preview-resize-handle"
            className={cn(
              "absolute -bottom-1 -right-1 z-30 h-4 w-4 cursor-se-resize rounded-sm",
              "border border-border bg-[var(--console-beige,var(--background))]",
              isResizing && "bg-[var(--console-terracotta,var(--primary))]",
            )}
            onPointerDown={(event) => {
              event.preventDefault();
              setIsResizing(true);
            }}
          />
        </div>
      </div>
    </div>
  );
}
