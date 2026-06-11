import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModelSelector } from "./model-selector";

const mockRecommendations = {
  system: {
    platform: "darwin",
    machine: "arm64",
    cpu_count: 8,
    total_ram_gb: 16,
    apple_silicon: true,
    spec_source: "ollama",
  },
  best_pick: "ollama:gemma4:e4b",
  recommendations: [
    {
      tag: "gemma4:e4b",
      model: "ollama:gemma4:e4b",
      display_name: "Gemma 4 E4B",
      params_b: 4,
      download_gb: 9.6,
      min_ram_gb: 16,
      speed: "medium",
      quality: "good",
      description: "Top pick for 16 GB laptops.",
      fit: "ok",
      installed: false,
    },
    {
      tag: "gemma4:e2b",
      model: "ollama:gemma4:e2b",
      display_name: "Gemma 4 E2B",
      params_b: 2,
      download_gb: 7.2,
      min_ram_gb: 8,
      speed: "fast",
      quality: "good",
      description: "Edge model.",
      fit: "great",
      installed: true,
    },
  ],
};

const mockInstalled = {
  ollama_available: true,
  installed: [
    {
      name: "gemma4:e2b",
      model: "ollama:gemma4:e2b",
      size_gb: 7.2,
    },
    {
      name: "qwen2.5:7b",
      model: "ollama:qwen2.5:7b",
      size_gb: 4.7,
    },
  ],
  cloud_models: [],
  default_model: "ollama:qwen2.5:7b",
};

describe("ModelSelector", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.includes("/recommendations")) {
          return Promise.resolve({
            ok: true,
            json: async () => mockRecommendations,
          });
        }
        if (url.includes("/installed")) {
          return Promise.resolve({
            ok: true,
            json: async () => mockInstalled,
          });
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );
  });

  it("shows recommended models in the dropdown above other installed", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<ModelSelector value={null} onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i }));

    expect(await screen.findByText("Recommended for your system")).toBeInTheDocument();
    expect(screen.getByText("Gemma 4 E4B")).toBeInTheDocument();
    expect(screen.getByText("Gemma 4 E2B")).toBeInTheDocument();
    expect(screen.getByText("Top pick")).toBeInTheDocument();
    expect(screen.getByText("Other installed")).toBeInTheDocument();
    expect(screen.getAllByText("qwen2.5:7b").length).toBeGreaterThan(0);

    const popover = screen.getByRole("dialog");
    const text = popover.textContent ?? "";
    expect(text.indexOf("Recommended for your system")).toBeLessThan(text.indexOf("Other installed"));
  });

  it("selects a recommended model when its row is clicked", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();

    render(<ModelSelector value={null} onChange={onChange} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Recommended · Gemma 4 E4B/i }));
    await user.click(screen.getByText("Gemma 4 E2B"));

    expect(onChange).toHaveBeenCalledWith("ollama:gemma4:e2b");
  });
});
