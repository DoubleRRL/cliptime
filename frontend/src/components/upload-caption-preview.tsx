"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { previewDisplayFontSize } from "@/lib/caption-fit";
import { buildPreviewCaptionStyles } from "@/lib/caption-preview-styles";
import { cropToBackgroundStyle, panelToVerticalCrop, type SpeakerPanel } from "@/lib/preview-crop";

export interface CaptionTemplatePreview {
  id: string;
  animation?: string;
  highlight_color?: string;
  stroke_color?: string | null;
  stroke_width?: number;
  position_y?: number;
  text_transform?: string;
  shadow?: boolean;
}

interface UploadCaptionPreviewProps {
  thumbnailUrl: string | null;
  frameWidth: number;
  frameHeight: number;
  panels: SpeakerPanel[];
  selectedPanelIndex: number;
  onPanelChange: (index: number) => void;
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  template: CaptionTemplatePreview | null;
  isLoading?: boolean;
  error?: string | null;
  compact?: boolean;
  isAdjustingSize?: boolean;
}

const PREVIEW_WIDTH = 270;
const PREVIEW_HEIGHT = 480;
const OUTPUT_HEIGHT = 720;

const SAMPLE_WORDS = ["HOW", "YOUR", "CAPTIONS", "LOOK"];
const WORD_CYCLE_MS = 650;

function buildCaptionText(template: CaptionTemplatePreview | null): string[] {
  if (template?.text_transform === "uppercase") {
    return SAMPLE_WORDS.map((w) => w.toUpperCase());
  }
  return SAMPLE_WORDS.map((w) => w.charAt(0) + w.slice(1).toLowerCase());
}

function centerCrop(frameWidth: number, frameHeight: number) {
  let cropH = frameHeight;
  let cropW = Math.floor(cropH * (9 / 16));
  if (cropW > frameWidth) {
    cropW = frameWidth;
    cropH = Math.floor(cropW * (16 / 9));
  }
  const x1 = Math.max(0, Math.floor((frameWidth - cropW) / 2));
  const y1 = Math.max(0, Math.floor((frameHeight - cropH) / 2));
  return { x1, y1, x2: x1 + cropW, y2: y1 + cropH, width: cropW, height: cropH };
}

export default function UploadCaptionPreview({
  thumbnailUrl,
  frameWidth,
  frameHeight,
  panels,
  selectedPanelIndex,
  onPanelChange,
  fontFamily,
  fontSize,
  fontColor,
  template,
  isLoading = false,
  error = null,
  compact = false,
  isAdjustingSize = false,
}: UploadCaptionPreviewProps) {
  const [activeWordIndex, setActiveWordIndex] = useState(0);

  const panel = panels[selectedPanelIndex] ?? panels[0];
  const crop =
    panel && frameWidth > 0 && frameHeight > 0
      ? panelToVerticalCrop(panel, frameWidth, frameHeight)
      : frameWidth > 0 && frameHeight > 0
        ? centerCrop(frameWidth, frameHeight)
        : null;

  const bgStyle =
    crop && thumbnailUrl
      ? cropToBackgroundStyle(frameWidth, frameHeight, crop, PREVIEW_WIDTH, PREVIEW_HEIGHT)
      : null;

  const positionY = template?.position_y ?? 0.75;
  const strokeWidth = template?.stroke_width ?? 0;
  const strokeColor = template?.stroke_color ?? "#000000";
  const highlightColor = template?.highlight_color ?? "#FFD700";
  const words = useMemo(() => buildCaptionText(template), [template]);
  const showKaraoke = template?.animation === "karaoke" && !isAdjustingSize;

  const displayFontSize = previewDisplayFontSize(
    fontSize,
    PREVIEW_HEIGHT,
    OUTPUT_HEIGHT,
    PREVIEW_WIDTH,
    words,
  );

  const captionStyle = buildPreviewCaptionStyles({
    fontFamily,
    displayFontSize,
    strokeWidth,
    strokeColor,
    shadow: template?.shadow ?? false,
  });

  useEffect(() => {
    if (!showKaraoke) {
      return;
    }
    const timer = window.setInterval(() => {
      setActiveWordIndex((prev) => (prev + 1) % words.length);
    }, WORD_CYCLE_MS);
    return () => window.clearInterval(timer);
  }, [showKaraoke, words.length]);

  return (
    <div className={compact ? "space-y-3" : "space-y-4"}>
      {!compact && (
        <div className="flex items-center justify-center gap-2 text-sm text-stone-400">
          <span>Caption Preview</span>
        </div>
      )}

      <style>{`
        @keyframes captionWordBounce {
          0% { transform: scale(1); }
          35% { transform: scale(1.22); }
          65% { transform: scale(1.08); }
          100% { transform: scale(1); }
        }
        .caption-active-word {
          display: inline-block;
          animation: captionWordBounce 0.55s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
      `}</style>

      <div className="mx-auto" style={{ width: PREVIEW_WIDTH }}>
        <div
          className="relative overflow-hidden rounded-2xl border border-stone-200 bg-stone-900 shadow-lg"
          style={{ width: PREVIEW_WIDTH, height: PREVIEW_HEIGHT }}
        >
          {isLoading ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-stone-800 text-stone-300">
              <Loader2 className="h-6 w-6 animate-spin" />
              <span className="text-xs">Uploading & analyzing…</span>
            </div>
          ) : thumbnailUrl && bgStyle ? (
            <>
              <div
                className="absolute inset-0 bg-no-repeat"
                style={{
                  backgroundImage: `url(${thumbnailUrl})`,
                  backgroundSize: bgStyle.backgroundSize,
                  backgroundPosition: bgStyle.backgroundPosition,
                }}
              />
              <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-black/60 to-transparent" />
            </>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center bg-stone-800 text-xs text-stone-400 px-4 text-center">
              {error || "Select a video to preview captions"}
            </div>
          )}

          {!isLoading && thumbnailUrl && (
            <div
              className="absolute left-0 right-0 z-10 px-3"
              style={{ top: `${positionY * 100}%`, transform: "translateY(-50%)" }}
            >
              <div
                style={{
                  ...captionStyle,
                  display: "flex",
                  flexWrap: "wrap",
                  justifyContent: "center",
                  gap: "0.25em",
                  maxWidth: "88%",
                  margin: "0 auto",
                }}
              >
                {words.map((word, index) => {
                  const isActive = showKaraoke && index === activeWordIndex;
                  return (
                    <span
                      key={`${word}-${index}`}
                      className={isActive ? "caption-active-word" : undefined}
                      style={{
                        color: isActive ? highlightColor : fontColor,
                        whiteSpace: "nowrap",
                        transition: "color 0.12s ease-out",
                      }}
                    >
                      {word}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {panels.length > 1 && !isLoading && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {panels.map((p, index) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onPanelChange(index)}
                className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                  index === selectedPanelIndex
                    ? "bg-stone-900 text-white"
                    : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        {!isLoading && thumbnailUrl && (
          <p className="mt-2 text-[11px] leading-snug text-stone-400">
            Layout detected from your video. Final clips may refine speaker assignment after
            transcription.
          </p>
        )}

        {error && thumbnailUrl && (
          <p className="mt-1 text-[11px] text-amber-700">{error}</p>
        )}
      </div>
    </div>
  );
}
