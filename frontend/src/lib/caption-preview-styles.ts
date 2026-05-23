import type { CSSProperties } from "react";

export interface PreviewCaptionStyleInput {
  fontFamily: string;
  displayFontSize: number;
  strokeWidth?: number;
  strokeColor?: string | null;
  shadow?: boolean;
}

/** ASS-like preview styling: thin scaled outline OR crisp shadow, never both stacked. */
export function buildPreviewCaptionStyles({
  fontFamily,
  displayFontSize,
  strokeWidth = 0,
  strokeColor = "#000000",
  shadow = false,
}: PreviewCaptionStyleInput): CSSProperties {
  const maxOutlinePx = Math.max(0.5, displayFontSize * 0.06);
  const scaledStroke =
    strokeWidth > 0
      ? Math.min(maxOutlinePx, Math.max(0.5, strokeWidth * (displayFontSize / 48)))
      : 0;

  const styles: CSSProperties = {
    fontFamily: `'${fontFamily}', system-ui, -apple-system, sans-serif`,
    fontSize: `${displayFontSize}px`,
    fontWeight: 400,
    lineHeight: 1.35,
    textAlign: "center",
    margin: 0,
  };

  if (scaledStroke > 0 && strokeColor) {
    styles.WebkitTextStroke = `${scaledStroke}px ${strokeColor}`;
    styles.paintOrder = "stroke fill";
  } else if (shadow) {
    styles.textShadow = "1px 1px 0 rgba(0, 0, 0, 0.6)";
  }

  return styles;
}
