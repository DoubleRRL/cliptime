import { describe, expect, it } from "vitest";

import {
  buildClipGridRows,
  DEFAULT_CLIP_ZOOM,
  getCardWidth,
  getMaxCardWidth,
  getMaxColumns,
} from "@/components/console/use-clip-grid-layout";

describe("use-clip-grid-layout", () => {
  it("computes max columns from container width", () => {
    expect(getMaxColumns(1000)).toBe(6);
    expect(getMaxColumns(200)).toBe(1);
  });

  it("scales card width proportionally for partial rows at default zoom", () => {
    const width = getCardWidth(900, 2, DEFAULT_CLIP_ZOOM);
    expect(width).toBeGreaterThan(140);
    expect(width).toBeLessThanOrEqual(220);
  });

  it("builds per-row layouts for multi-row grids", () => {
    const rows = buildClipGridRows(8, 900);
    expect(rows).toHaveLength(2);
    expect(rows[0].count).toBe(5);
    expect(rows[1].count).toBe(3);
    expect(rows[1].cardWidth).toBeGreaterThanOrEqual(rows[0].cardWidth);
  });

  it("default zoom max width matches legacy 220px cap", () => {
    expect(getMaxCardWidth(DEFAULT_CLIP_ZOOM)).toBe(220);
  });

  it("full zoom allows cards wider than 220px on wide containers", () => {
    const width = getCardWidth(1200, 4, 1);
    expect(width).toBeGreaterThan(220);
  });
});
