import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SettingsCaptionPreview } from "./settings-caption-preview";

const riversideTemplate = {
  id: "riverside",
  name: "Riverside",
  animation: "karaoke",
  pill_style: true,
  position_y: 0.77,
  highlight_color: "#8B5CF6",
  background_color: "#1A1A1ACC",
};

const tiktokTemplate = {
  id: "tiktok",
  name: "TikTok",
  animation: "karaoke",
  background: false,
  highlight_color: "#FE2C55",
  stroke_width: 2,
  shadow: true,
};

describe("SettingsCaptionPreview", () => {
  it("shows export px badge on the 9:16 frame", () => {
    render(
      <SettingsCaptionPreview
        fontFamily="TikTokSans-Regular"
        burnedInPx={48}
        fontColor="#FFFFFF"
        highlightColor="#8B5CF6"
        textBackgroundColor="#1A1A1ACC"
        template={riversideTemplate}
        positionY={0.77}
      />,
    );

    expect(screen.getByTestId("export-px-badge")).toHaveTextContent("48px");
    expect(screen.queryByTestId("export-size-sample")).not.toBeInTheDocument();
  });

  it("renders resizable preview frame with background image", () => {
    render(
      <SettingsCaptionPreview
        fontFamily="TikTokSans-Regular"
        burnedInPx={48}
        fontColor="#FFFFFF"
        highlightColor="#FE2C55"
        textBackgroundColor="transparent"
        template={tiktokTemplate}
        positionY={0.75}
      />,
    );

    const frame = screen.getByTestId("caption-preview-frame");
    expect(frame).toBeInTheDocument();
    expect(screen.getByAltText("")).toHaveAttribute(
      "src",
      "/images/caption-settings-preview.jpg",
    );
  });

  it("updates frame width when resize handle is dragged", () => {
    render(
      <SettingsCaptionPreview
        fontFamily="TikTokSans-Regular"
        burnedInPx={36}
        fontColor="#FFFFFF"
        highlightColor="#FE2C55"
        textBackgroundColor="transparent"
        template={tiktokTemplate}
        positionY={0.75}
      />,
    );

    const frame = screen.getByTestId("caption-preview-frame");
    const initialWidth = frame.style.width;

    fireEvent.pointerDown(screen.getByTestId("preview-resize-handle"), {
      clientX: 500,
      pointerId: 1,
    });
    fireEvent.pointerMove(window, { clientX: 560, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    expect(frame.style.width).not.toBe(initialWidth);
  });
});
