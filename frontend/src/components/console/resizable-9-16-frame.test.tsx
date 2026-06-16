import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  clampPreviewWidth,
  CLIP_EDITOR_MAX_PREVIEW_WIDTH,
  computeResizeWidth,
  DEFAULT_PREVIEW_WIDTH,
  MAX_PREVIEW_WIDTH,
  MIN_PREVIEW_WIDTH,
  previewHeightForWidth,
  Resizable9By16Frame,
} from "./resizable-9-16-frame";

describe("clampPreviewWidth", () => {
  it("clamps to min and max bounds", () => {
    expect(clampPreviewWidth(100)).toBe(MIN_PREVIEW_WIDTH);
    expect(clampPreviewWidth(500)).toBe(MAX_PREVIEW_WIDTH);
    expect(clampPreviewWidth(300)).toBe(300);
  });

  it("respects container max when provided", () => {
    expect(clampPreviewWidth(400, 260)).toBe(260);
    expect(clampPreviewWidth(180, 260)).toBe(MIN_PREVIEW_WIDTH);
  });

  it("respects custom max above the settings default", () => {
    expect(clampPreviewWidth(700, 700, CLIP_EDITOR_MAX_PREVIEW_WIDTH)).toBe(
      CLIP_EDITOR_MAX_PREVIEW_WIDTH,
    );
  });
});

describe("computeResizeWidth", () => {
  it("expands and shrinks symmetrically from a drag start", () => {
    const startWidth = 400;
    const startPointerX = 500;

    expect(computeResizeWidth(startWidth, startPointerX, 550)).toBe(500);
    expect(computeResizeWidth(startWidth, startPointerX, 450)).toBe(300);
  });
});

describe("previewHeightForWidth", () => {
  it("keeps a 9:16 frame proportional", () => {
    expect(previewHeightForWidth(300)).toBe(533);
  });
});

describe("Resizable9By16Frame", () => {
  it("renders children at the provided width and height", () => {
    render(
      <Resizable9By16Frame width={280} onWidthChange={vi.fn()}>
        <span>Preview content</span>
      </Resizable9By16Frame>,
    );

    const frame = screen.getByTestId("caption-preview-frame");
    expect(frame).toHaveStyle({ width: "280px", height: "498px" });
    expect(screen.getByText("Preview content")).toBeInTheDocument();
  });

  it("updates width when resize handle is dragged", () => {
    const onWidthChange = vi.fn();

    render(
      <Resizable9By16Frame width={DEFAULT_PREVIEW_WIDTH} onWidthChange={onWidthChange}>
        <span>Preview content</span>
      </Resizable9By16Frame>,
    );

    const frame = screen.getByTestId("caption-preview-frame");
    const container = frame.parentElement?.parentElement;
    expect(container).toBeTruthy();
    if (!container) return;

    Object.defineProperty(container, "clientWidth", {
      configurable: true,
      value: 800,
    });

    fireEvent.pointerDown(screen.getByTestId("preview-resize-handle"), {
      clientX: 400,
      pointerId: 1,
    });
    fireEvent.pointerMove(window, { clientX: 430, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    expect(onWidthChange).toHaveBeenCalled();
    const lastCall = onWidthChange.mock.calls.at(-1)?.[0];
    expect(lastCall).toBe(360);
  });

  it("allows drag results above the settings default when maxWidth is higher", () => {
    const onWidthChange = vi.fn();

    render(
      <Resizable9By16Frame
        width={DEFAULT_PREVIEW_WIDTH}
        onWidthChange={onWidthChange}
        maxWidth={CLIP_EDITOR_MAX_PREVIEW_WIDTH}
      >
        <span>Preview content</span>
      </Resizable9By16Frame>,
    );

    const frame = screen.getByTestId("caption-preview-frame");
    const container = frame.parentElement?.parentElement;
    expect(container).toBeTruthy();
    if (!container) return;

    Object.defineProperty(container, "clientWidth", {
      configurable: true,
      value: 800,
    });

    fireEvent.pointerDown(screen.getByTestId("preview-resize-handle"), {
      clientX: 400,
      pointerId: 1,
    });
    fireEvent.pointerMove(window, { clientX: 500, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    expect(onWidthChange).toHaveBeenCalled();
    const lastCall = onWidthChange.mock.calls.at(-1)?.[0];
    expect(lastCall).toBeGreaterThan(MAX_PREVIEW_WIDTH);
    expect(lastCall).toBeLessThanOrEqual(CLIP_EDITOR_MAX_PREVIEW_WIDTH);
  });
});
