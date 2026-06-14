"use client";

import { useEffect, useMemo, useState } from "react";
import { previewDisplayFontSize, RENDER_HEIGHT } from "@/lib/caption-fit";
import { buildPreviewCaptionStyles, hexToRgba, isTransparentBackground } from "@/lib/caption-preview-styles";
import { RIVERSIDE_CAPTION_DEFAULTS } from "@/lib/caption-defaults";

export type CaptionStyleTemplate = {
  id: string;
  name?: string;
  description?: string;
  animation?: string;
  font_size?: number;
  font_color?: string;
  highlight_color?: string;
  background_color?: string;
  pill_style?: boolean;
  background?: boolean;
  stroke_color?: string | null;
  stroke_width?: number;
  position_y?: number;
  text_transform?: string;
  shadow?: boolean;
  emphasis_callouts?: boolean;
};

type CaptionStylePreviewProps = {
  fontFamily: string;
  fontSize: number;
  fontColor: string;
  highlightColor: string;
  textBackgroundColor: string;
  /** @deprecated Use textBackgroundColor */
  pillColor?: string;
  template: CaptionStyleTemplate | null;
  positionY?: number;
  sampleWords?: string[];
  emphasisCallouts?: boolean;
  emphasisWords?: string[];
  className?: string;
};

const PREVIEW_WIDTH = 240;
const PREVIEW_HEIGHT = 427;
const DEFAULT_WORDS = ["YOUR", "CAPTION", "HERE"];
const WORD_CYCLE_MS = 650;

function buildWords(template: CaptionStyleTemplate | null, sampleWords?: string[]): string[] {
  const base = sampleWords?.length ? sampleWords : DEFAULT_WORDS;
  if (template?.text_transform === "uppercase") {
    return base.map((word) => word.toUpperCase());
  }
  return base.map((word) => word.charAt(0) + word.slice(1).toLowerCase());
}

function normalizeWordToken(text: string): string {
  return text.toLowerCase().replace(/[.,!?;:"']/g, "");
}

function shouldShowActiveHighlightPill(
  word: string,
  isActive: boolean,
  emphasisCallouts: boolean,
  emphasisSet: Set<string>,
): boolean {
  if (!isActive) return false;
  if (!emphasisCallouts) return true;
  if (emphasisSet.size === 0) return true;
  return emphasisSet.has(normalizeWordToken(word));
}

export function CaptionStylePreview({
  fontFamily,
  fontSize,
  fontColor,
  highlightColor,
  textBackgroundColor,
  pillColor,
  template,
  positionY,
  sampleWords,
  emphasisCallouts = true,
  emphasisWords,
  className,
}: CaptionStylePreviewProps) {
  const [activeWordIndex, setActiveWordIndex] = useState(0);
  const words = useMemo(() => buildWords(template, sampleWords), [template, sampleWords]);
  const showKaraoke = template?.animation === "karaoke";
  const resolvedPositionY = positionY ?? template?.position_y ?? RIVERSIDE_CAPTION_DEFAULTS.positionY;
  const pillStyle = Boolean(template?.pill_style);
  const boxStyle = Boolean(template?.background) && !pillStyle;
  const strokeWidth = template?.stroke_width ?? 0;
  const strokeColor = template?.stroke_color ?? "#000000";
  const resolvedBackground = textBackgroundColor || pillColor || "#1A1A1ACC";
  const transparentBackground = isTransparentBackground(resolvedBackground);

  const emphasisSet = useMemo(() => {
    const source =
      emphasisWords ??
      (emphasisCallouts && words.length > 0 ? [words[Math.floor(words.length / 2)]] : []);
    return new Set(source.map((word) => normalizeWordToken(word)));
  }, [emphasisCallouts, emphasisWords, words]);

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
    pillStyle: pillStyle || boxStyle,
  });

  const lineBackgroundStyles =
    !transparentBackground && pillStyle
      ? {
          backgroundColor: hexToRgba(resolvedBackground, "rgba(26, 26, 26, 0.8)"),
          borderRadius: `${Math.max(8, displayFontSize * 0.45)}px`,
          padding: `${displayFontSize * 0.28}px ${displayFontSize * 0.5}px`,
        }
      : !transparentBackground && boxStyle
        ? {
            backgroundColor: hexToRgba(resolvedBackground, "rgba(0, 0, 0, 0.5)"),
            borderRadius: "0.25rem",
            padding: "0.3rem 0.5rem",
          }
        : {};

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
        style={{ bottom: `${(1 - resolvedPositionY) * 100}%`, transform: "translateY(50%)" }}
      >
        <div
          className="inline-flex max-w-full flex-wrap justify-center text-center leading-tight"
          style={{
            ...captionStyle,
            color: fontColor,
            gap: pillStyle ? "0.15em" : "0.25em",
            ...lineBackgroundStyles,
          }}
        >
          {words.map((word, index) => {
            const isActive = showKaraoke && index === activeWordIndex;
            const showPill = shouldShowActiveHighlightPill(
              word,
              isActive,
              emphasisCallouts,
              emphasisSet,
            );
            return (
              <span
                key={`${word}-${index}`}
                className={isActive ? "caption-active-word" : undefined}
                style={{
                  color: fontColor,
                  whiteSpace: "nowrap",
                  borderRadius: showPill ? `${Math.max(4, displayFontSize * 0.18)}px` : undefined,
                  padding: showPill ? "0.05em 0.2em" : undefined,
                  backgroundColor: showPill ? highlightColor : "transparent",
                  marginRight: index < words.length - 1 ? "0.15em" : 0,
                }}
              >
                {word}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
