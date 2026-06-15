import { describe, expect, it } from "vitest";

import {
  baseToBurnedIn,
  burnedInToBase,
  getScaledFontSize,
  previewDisplayFontSize,
  resolveRenderFontSize,
  RENDER_HEIGHT,
} from "./caption-fit";

const SAMPLE_WORDS = ["HOW", "YOUR", "CAPTIONS", "LOOK"];
const PREVIEW_HEIGHT = 427;

describe("resolveRenderFontSize", () => {
  it("applies 1080p width scaling by default", () => {
    expect(resolveRenderFontSize(48)).toBe(72);
    expect(getScaledFontSize(48, 1080)).toBe(72);
  });
});

describe("baseToBurnedIn and burnedInToBase", () => {
  it("maps base 32 to 48px export size", () => {
    expect(baseToBurnedIn(32)).toBe(48);
  });

  it("maps 48px export back to base 32", () => {
    expect(burnedInToBase(48)).toBe(32);
  });

  it("round-trips common Riverside default", () => {
    const base = 32;
    expect(burnedInToBase(baseToBurnedIn(base))).toBe(base);
  });
});

describe("previewDisplayFontSize", () => {
  it("increases preview size when base font size increases", () => {
    const small = previewDisplayFontSize(24, PREVIEW_HEIGHT, RENDER_HEIGHT, 240, SAMPLE_WORDS);
    const large = previewDisplayFontSize(48, PREVIEW_HEIGHT, RENDER_HEIGHT, 240, SAMPLE_WORDS);

    expect(large).toBeGreaterThan(small);
  });

  it("maps base 48 to ~16px preview at 427px preview height", () => {
    const size = previewDisplayFontSize(
      48,
      PREVIEW_HEIGHT,
      RENDER_HEIGHT,
      240,
      SAMPLE_WORDS,
    );

    expect(size).toBeCloseTo(16, 0);
  });

  it("maps base 24 to ~8px preview at 427px preview height", () => {
    const size = previewDisplayFontSize(
      24,
      PREVIEW_HEIGHT,
      RENDER_HEIGHT,
      240,
      SAMPLE_WORDS,
    );

    expect(size).toBeCloseTo(8, 0);
  });
});
