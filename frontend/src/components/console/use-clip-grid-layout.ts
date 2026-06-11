import { useMemo, useState } from "react";

export const CLIP_MIN = 140;
export const CLIP_MAX = 220;
export const CLIP_MAX_AT_FULL_ZOOM = 480;
export const CLIP_GAP = 16;
export const DEFAULT_CLIP_ZOOM = 0.35;

/** Map zoom 0→min, DEFAULT→220px legacy cap, 1→full max. */
export function getMaxCardWidth(zoom: number): number {
  const clamped = Math.max(0, Math.min(1, zoom));
  if (clamped <= DEFAULT_CLIP_ZOOM) {
    return CLIP_MIN + (clamped / DEFAULT_CLIP_ZOOM) * (CLIP_MAX - CLIP_MIN);
  }
  const t = (clamped - DEFAULT_CLIP_ZOOM) / (1 - DEFAULT_CLIP_ZOOM);
  return CLIP_MAX + t * (CLIP_MAX_AT_FULL_ZOOM - CLIP_MAX);
}

export function getMaxColumns(containerWidth: number): number {
  if (containerWidth <= 0) return 1;
  return Math.max(1, Math.floor((containerWidth + CLIP_GAP) / (CLIP_MIN + CLIP_GAP)));
}

export function getCardWidth(
  containerWidth: number,
  columnsInRow: number,
  zoom: number = DEFAULT_CLIP_ZOOM,
): number {
  if (columnsInRow <= 0 || containerWidth <= 0) return CLIP_MIN;
  const raw = (containerWidth - (columnsInRow - 1) * CLIP_GAP) / columnsInRow;
  const maxWidth = getMaxCardWidth(zoom);
  return Math.min(maxWidth, Math.max(CLIP_MIN, raw));
}

export function chunkClipRows(clipCount: number, maxColumns: number): number[] {
  if (clipCount <= 0) return [];
  const rows: number[] = [];
  let remaining = clipCount;
  while (remaining > 0) {
    rows.push(Math.min(remaining, maxColumns));
    remaining -= maxColumns;
  }
  return rows;
}

export type ClipGridRow = {
  startIndex: number;
  count: number;
  cardWidth: number;
};

export function buildClipGridRows(
  clipCount: number,
  containerWidth: number,
  zoom: number = DEFAULT_CLIP_ZOOM,
): ClipGridRow[] {
  const maxColumns = getMaxColumns(containerWidth);
  const rowCounts = chunkClipRows(clipCount, maxColumns);
  let startIndex = 0;

  return rowCounts.map((count) => {
    const row: ClipGridRow = {
      startIndex,
      count,
      cardWidth: getCardWidth(containerWidth, count, zoom),
    };
    startIndex += count;
    return row;
  });
}

export function useClipGridLayout(clipCount: number, zoom: number = DEFAULT_CLIP_ZOOM) {
  const [containerWidth, setContainerWidth] = useState(0);

  const rows = useMemo(
    () => buildClipGridRows(clipCount, containerWidth, zoom),
    [clipCount, containerWidth, zoom],
  );

  return {
    rows,
    containerWidth,
    setContainerWidth,
  };
}
