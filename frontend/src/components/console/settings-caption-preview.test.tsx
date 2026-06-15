import { render, screen } from "@testing-library/react";
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

describe("SettingsCaptionPreview", () => {
  it("shows burned-in export px in the label", () => {
    render(
      <SettingsCaptionPreview
        fontFamily="TikTokSans-Regular"
        burnedInPx={48}
        fontColor="#FFFFFF"
        highlightColor="#8B5CF6"
        textBackgroundColor="#1A1A1ACC"
        template={riversideTemplate}
      />,
    );

    expect(screen.getByText("48px in your exported clip")).toBeInTheDocument();
  });

  it("renders 1:1 sample at exact export font size", () => {
    render(
      <SettingsCaptionPreview
        fontFamily="TikTokSans-Regular"
        burnedInPx={48}
        fontColor="#FFFFFF"
        highlightColor="#8B5CF6"
        textBackgroundColor="#1A1A1ACC"
        template={riversideTemplate}
      />,
    );

    const sample = screen.getByTestId("export-size-sample");
    expect(sample.style.fontSize).toBe("48px");
  });

  it("updates sample font size when burnedInPx changes", () => {
    const { rerender } = render(
      <SettingsCaptionPreview
        fontFamily="TikTokSans-Regular"
        burnedInPx={36}
        fontColor="#FFFFFF"
        highlightColor="#8B5CF6"
        textBackgroundColor="#1A1A1ACC"
        template={riversideTemplate}
      />,
    );

    expect(screen.getByTestId("export-size-sample").style.fontSize).toBe("36px");

    rerender(
      <SettingsCaptionPreview
        fontFamily="TikTokSans-Regular"
        burnedInPx={60}
        fontColor="#FFFFFF"
        highlightColor="#8B5CF6"
        textBackgroundColor="#1A1A1ACC"
        template={riversideTemplate}
      />,
    );

    expect(screen.getByText("60px in your exported clip")).toBeInTheDocument();
    expect(screen.getByTestId("export-size-sample").style.fontSize).toBe("60px");
  });
});
