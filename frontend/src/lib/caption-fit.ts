/** Mirror backend get_scaled_font_size + karaoke shrink-to-fit. */

export const RENDER_WIDTH = 1080;
export const RENDER_HEIGHT = 1920;

const MIN_FONT_SIZE = 24;
const MAX_FONT_SIZE = 72;
const REFERENCE_WIDTH = 720;

export function getScaledFontSize(baseFontSize: number, videoWidth: number): number {
  const scaled = Math.round(baseFontSize * (videoWidth / REFERENCE_WIDTH));
  return Math.max(MIN_FONT_SIZE, Math.min(MAX_FONT_SIZE, scaled));
}

export function resolveRenderFontSize(
  baseFontSize: number,
  options: { useWidthScaling: boolean } = { useWidthScaling: true },
): number {
  if (options.useWidthScaling) {
    return getScaledFontSize(baseFontSize, RENDER_WIDTH);
  }
  return baseFontSize;
}

export function getSubtitleMaxWidth(videoWidth: number): number {
  const horizontalPadding = Math.max(40, Math.floor(videoWidth * 0.06));
  return Math.max(200, videoWidth - horizontalPadding * 2);
}

/** Rough width estimate: char count * 0.55 * fontSize + spacing between words. */
export function estimatePhraseWidth(words: string[], fontSize: number): number {
  const spaceWidth = fontSize * 0.28;
  const charWidth = fontSize * 0.55;
  const textWidth = words.reduce((sum, word) => sum + word.length * charWidth, 0);
  const gaps = Math.max(0, words.length - 1) * spaceWidth;
  return textWidth + gaps;
}

export function fitPhraseFontSize(
  words: string[],
  baseFontSize: number,
  maxWidth: number,
  minSize = MIN_FONT_SIZE,
): number {
  let size = getScaledFontSize(baseFontSize, REFERENCE_WIDTH);
  while (size > minSize && estimatePhraseWidth(words, size) > maxWidth) {
    size = Math.max(minSize, Math.floor(size * 0.9));
  }
  return size;
}

/** Map effective render font size to CSS pixels in a 9:16 preview frame. */
export function previewDisplayFontSize(
  baseFontSize: number,
  previewHeight: number,
  outputHeight: number = RENDER_HEIGHT,
  _previewWidth?: number,
  _words?: string[],
): number {
  const renderSize = resolveRenderFontSize(baseFontSize);
  return Math.max(8, renderSize * (previewHeight / outputHeight));
}
