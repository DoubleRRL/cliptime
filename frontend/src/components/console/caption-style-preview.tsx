"use client";

import { useEffect, useMemo, useState } from "react";
import { previewDisplayFontSize } from "@/lib/caption-fit";
import { buildPreviewCaptionStyles, hexToRgba } from "@/lib/caption-preview-styles";

export type CaptionStyleTemplate = {
  id: string;
  name?: string;
  animation?: string;
  highlight_color?: string;
  background_color?: string;
  pill_style?: boolean;
  stroke_color?: string | null;
  stroke_width?: number;
  position_y?: number;
  text_transform?: string;
  shadow?: boolean;
};

type CaptionStylePreviewProps = {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  highlightColor: string;
  pillColor: string;
  template: CaptionStyleTemplate | null;
  sampleWords?: string[];
  className?: string;
};

const PREVIEW_WIDTH = 240;
const PREVIEW_HEIGHT = 427;
const OUTPUT_HEIGHT = 720;
const DEFAULT_WORDS = ["YOUR", "CAPTION", "HERE"];
const WORD_CYCLE_MS = 650;

function buildWords(template: CaptionStyleTemplate | null, sampleWords?: string[]): string[] {
  const base = sampleWords?.length ? sampleWords : DEFAULT_WORDS;
  if (template?.text_transform === "uppercase") {
    return base.map((word) => word.toUpperCase());
  }
  return base.map((word) => word.charAt(0) + word.slice(1).toLowerCase());
}

export function CaptionStylePreview({
  fontFamily,
  fontSize,
  fontColor,
  highlightColor,
  pillColor,
  template,
  sampleWords,
  className,
}: CaptionStylePreviewProps) {
  const [activeWordIndex, setActiveWordIndex] = useState(0);
  const words = useMemo(() => buildWords(template, sampleWords), [template, sampleWords]);
  const showKaraoke = template?.animation === "karaoke";
  const positionY = template?.position_y ?? 0.75;
  const pillStyle = Boolean(template?.pill_style);
  const strokeWidth = template?.stroke_width ?? 0;
  const strokeColor = template?.stroke_color ?? "#000000";

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
    pillStyle,
  });

  useEffect(() => {
    if (!showKaraoke) return;
    const timer = window.setInterval(() => {
      setActiveWordIndex((prev) => (prev + 1) % words.length);
    }, WORD_CYCLE_MS);
    return () => window.clearInterval(timer);
  }, [showKaraoke, words.length]);

  return (
    <div className={className}>
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
      <div
        className="pointer-events-none absolute inset-x-0 z-10 flex justify-center px-3"
        style={{ bottom: `${(1 - positionY) * 100}%`, transform: "translateY(50%)" }}
      >
        <p
          className="max-w-full text-center leading-tight"
          style={{
            ...captionStyle,
            color: fontColor,
            ...(pillStyle
              ? {
                  backgroundColor: hexToRgba(pillColor, "rgba(26, 26, 26, 0.8)"),
                  borderRadius: "0.5rem",
                  padding: "0.35rem 0.65rem",
                }
              : {}),
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
                  marginRight: index < words.length - 1 ? "0.35em" : 0,
                }}
              >
                {word}
              </span>
            );
          })}
        </p>
      </div>
    </div>
  );
}
