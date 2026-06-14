"use client";

import { useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { previewDisplayFontSize, RENDER_HEIGHT } from "@/lib/caption-fit";
import { buildPreviewCaptionStyles, hexToRgba } from "@/lib/caption-preview-styles";
import { cropToBackgroundStyle, panelToVerticalCrop, type SpeakerPanel } from "@/lib/preview-crop";

export interface CaptionTemplatePreview {
  id: string;
  animation?: string;
  highlight_color?: string;
  background_color?: string;
  pill_style?: boolean;
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
  highlightColor?: string;
  pillColor?: string;
  template: CaptionTemplatePreview | null;
  isLoading?: boolean;
  error?: string | null;
  compact?: boolean;
  isAdjustingSize?: boolean;
}

const PREVIEW_WIDTH = 270;
const PREVIEW_HEIGHT = 480;

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
  highlightColor: highlightColorProp,
  pillColor: pillColorProp,
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
  const highlightColor = highlightColorProp ?? template?.highlight_color ?? "#8B5CF6";
  const pillColor = pillColorProp ?? template?.background_color ?? "#1A1A1ACC";
  const pillStyle = Boolean(template?.pill_style);
  const words = useMemo(() => buildCaptionText(template), [template]);
  const showKaraoke = template?.animation === "karaoke" && !isAdjustingSize;

  const displayFontSize = previewDisplayFontSize(
    fontSize,
    PREVIEW_HEIGHT,
    RENDER_HEIGHT,
    PREVIEW_WIDTH,
    words,
  );

  const captionStyle = buildPreviewCaptionStyles({
    fontFamily,
    displayFontSize,
    strokeWidth,
    strokeColor,
    shadow: template?.shadow ?? false,
    pillStyle,
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
        <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
          <span>Caption Preview</span>
        </div>
      )}

      <style>{`
        @keyframes captionWordPop {
          0% { transform: scale(1); }
          40% { transform: scale(1.12); }
          100% { transform: scale(1); }
        }
        .caption-active-word {
          display: inline-block;
          animation: captionWordPop 0.18s ease-out;
        }
      `}</style>

      <div className="mx-auto" style={{ width: PREVIEW_WIDTH }}>
        <div
          className="relative overflow-hidden rounded-2xl border border-border bg-card shadow-lg"
          style={{ width: PREVIEW_WIDTH, height: PREVIEW_HEIGHT }}
        >
          {isLoading ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-muted text-muted-foreground">
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
            <div className="absolute inset-0 flex items-center justify-center bg-muted text-xs text-muted-foreground px-4 text-center">
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
                  display: "inline-flex",
                  flexWrap: "wrap",
                  justifyContent: "center",
                  gap: pillStyle ? "0.15em" : "0.25em",
                  maxWidth: "88%",
                  margin: "0 auto",
                  ...(pillStyle
                    ? {
                        backgroundColor: hexToRgba(pillColor, "rgba(26,26,26,0.8)"),
                        borderRadius: `${Math.max(8, displayFontSize * 0.45)}px`,
                        padding: `${displayFontSize * 0.28}px ${displayFontSize * 0.5}px`,
                      }
                    : {}),
                }}
              >
                {words.map((word, index) => {
                  const isActive = showKaraoke && index === activeWordIndex;
                  return (
                    <span
                      key={`${word}-${index}`}
                      className={isActive && !pillStyle ? "caption-active-word" : isActive ? "caption-active-word" : undefined}
                      style={{
                        color: fontColor,
                        whiteSpace: "nowrap",
                        borderRadius: pillStyle ? `${Math.max(4, displayFontSize * 0.18)}px` : undefined,
                        padding: pillStyle ? "0.05em 0.2em" : undefined,
                        backgroundColor:
                          pillStyle && isActive
                            ? highlightColor
                            : "transparent",
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
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        {!isLoading && thumbnailUrl && (
          <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
            Layout detected from your video. Final clips may refine speaker assignment after
            transcription.
          </p>
        )}

        {error && thumbnailUrl && (
          <p className="mt-1 text-[11px] text-amber-400/90">{error}</p>
        )}
      </div>
    </div>
  );
}
