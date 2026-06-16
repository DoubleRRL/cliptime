import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { NewSessionDialog } from "./new-session-dialog";

describe("NewSessionDialog", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows loading summary until preferences load", async () => {
    let resolvePrefs: (value: Response) => void = () => {};
    const prefsPromise = new Promise<Response>((resolve) => {
      resolvePrefs = resolve;
    });

    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/preferences")) {
        return prefsPromise;
      }
      return Promise.resolve(
        new Response(JSON.stringify({ templates: [] }), { status: 200 }),
      );
    });

    render(<NewSessionDialog open onOpenChange={() => {}} onCreated={() => {}} />);

    expect(screen.getByTestId("new-session-caption-summary")).toHaveTextContent(
      "Loading defaults…",
    );
    expect(screen.getByRole("button", { name: /start clipping/i })).toBeDisabled();

    resolvePrefs(
      new Response(
        JSON.stringify({
          fontFamily: "TikTokSans-Regular",
          fontSize: 32,
          fontColor: "#FFFFFF",
          captionTemplate: "riverside",
          positionY: 0.77,
        }),
        { status: 200 },
      ),
    );

    await waitFor(() => {
      expect(screen.getByTestId("new-session-caption-summary")).not.toHaveTextContent(
        "Loading defaults…",
      );
    });
  });

  it("shows saved defaults in summary after preferences load", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/preferences")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              fontFamily: "TikTokSans-Regular",
              fontSize: 32,
              fontColor: "#FFFFFF",
              highlightColor: "#FE2C55",
              pillColor: null,
              captionTemplate: "tiktok",
              positionY: 0.75,
              llmModel: null,
            }),
            { status: 200 },
          ),
        );
      }
      if (url.includes("/api/caption-templates")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              templates: [
                {
                  id: "tiktok",
                  name: "TikTok",
                  animation: "karaoke",
                  background: false,
                  highlight_color: "#FE2C55",
                },
              ],
            }),
            { status: 200 },
          ),
        );
      }
      return Promise.resolve(new Response("{}", { status: 404 }));
    });

    render(<NewSessionDialog open onOpenChange={() => {}} onCreated={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("new-session-caption-summary")).toHaveTextContent(
        "Captions: TikTok · 48px · 75% vertical",
      );
    });
  });

  it("shows error when preferences fail to load", async () => {
    vi.spyOn(global, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/preferences")) {
        return Promise.resolve(new Response("{}", { status: 500 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ templates: [] }), { status: 200 }));
    });

    render(<NewSessionDialog open onOpenChange={() => {}} onCreated={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId("new-session-caption-summary")).toHaveTextContent(
        "Couldn't load saved defaults",
      );
    });
    expect(screen.getByRole("button", { name: /start clipping/i })).toBeDisabled();
  });
});
