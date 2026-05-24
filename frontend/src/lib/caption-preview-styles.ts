import type { CSSProperties } from "react";

export interface PreviewCaptionStyleInput {
  fontFamily: string;
  displayFontSize: number;
  strokeWidth?: number;
  strokeColor?: string | null;
  shadow?: boolean;
  pillStyle?: boolean;
}

/** Preview styling for captions — pill (Riverside) or stroke/shadow legacy. */
export function buildPreviewCaptionStyles({
  fontFamily,
  displayFontSize,
  strokeWidth = 0,
  strokeColor = "#000000",
  shadow = false,
  pillStyle = false,
}: PreviewCaptionStyleInput): CSSProperties {
  const styles: CSSProperties = {
    fontFamily: `'${fontFamily}', system-ui, -apple-system, sans-serif`,
    fontSize: `${displayFontSize}px`,
    fontWeight: 600,
    lineHeight: 1.35,
    textAlign: "center",
    margin: 0,
  };

  if (pillStyle) {
    return styles;
  }

  const maxOutlinePx = Math.max(0.5, displayFontSize * 0.06);
  const scaledStroke =
    strokeWidth > 0
      ? Math.min(maxOutlinePx, Math.max(0.5, strokeWidth * (displayFontSize / 48)))
      : 0;

  if (scaledStroke > 0 && strokeColor) {
    styles.WebkitTextStroke = `${scaledStroke}px ${strokeColor}`;
    styles.paintOrder = "stroke fill";
  } else if (shadow) {
    styles.textShadow = "1px 1px 0 rgba(0, 0, 0, 0.6)";
  }

  return styles;
}

export function hexToRgba(hex: string, fallback: string): string {
  const c = hex.replace("#", "");
  if (c.length === 6) {
    const r = parseInt(c.slice(0, 2), 16);
    const g = parseInt(c.slice(2, 4), 16);
    const b = parseInt(c.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, 0.85)`;
  }
  if (c.length === 8) {
    const r = parseInt(c.slice(0, 2), 16);
    const g = parseInt(c.slice(2, 4), 16);
    const b = parseInt(c.slice(4, 6), 16);
    const a = parseInt(c.slice(6, 8), 16) / 255;
    return `rgba(${r}, ${g}, ${b}, ${a})`;
  }
  return fallback;
}
