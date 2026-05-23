import { describe, expect, it } from "vitest";

import { previewDisplayFontSize } from "./caption-fit";

const SAMPLE_WORDS = ["HOW", "YOUR", "CAPTIONS", "LOOK"];
const PREVIEW_HEIGHT = 480;
const OUTPUT_HEIGHT = 720;
const PREVIEW_WIDTH = 270;

describe("previewDisplayFontSize", () => {
  it("increases preview size when base font size increases", () => {
    const small = previewDisplayFontSize(
      24,
      PREVIEW_HEIGHT,
      OUTPUT_HEIGHT,
      PREVIEW_WIDTH,
      SAMPLE_WORDS,
    );
    const large = previewDisplayFontSize(
      48,
      PREVIEW_HEIGHT,
      OUTPUT_HEIGHT,
      PREVIEW_WIDTH,
      SAMPLE_WORDS,
    );

    expect(large).toBeGreaterThan(small);
  });

  it("maps 24px clip size to ~16px preview size when phrase fits", () => {
    const size = previewDisplayFontSize(
      24,
      PREVIEW_HEIGHT,
      OUTPUT_HEIGHT,
      PREVIEW_WIDTH,
      SAMPLE_WORDS,
    );

    expect(size).toBe(16);
  });

  it("maps 48px clip size to ~32px preview size when phrase fits", () => {
    const size = previewDisplayFontSize(
      48,
      PREVIEW_HEIGHT,
      OUTPUT_HEIGHT,
      PREVIEW_WIDTH,
      SAMPLE_WORDS,
    );

    expect(size).toBe(32);
  });
});
