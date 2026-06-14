import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StorageDetailsSection } from "./storage-details-section";

const mockSummary = {
  total_bytes: 400,
  breakdown: {
    clips: 100,
    uploads: 100,
    downloads: 0,
    caches: 0,
    orphans: 200,
  },
  counts: {
    tasks: 1,
    clips: 1,
    orphan_files: 2,
  },
  temp_dir: "/app/uploads",
  host_path: "/Users/test/supoclip/uploads",
  orphan_paths: ["/app/uploads/clips/stale-a.mp4", "/app/uploads/clips/stale-b.mp4"],
  orphan_files: [
    {
      path: "/app/uploads/clips/stale-a.mp4",
      relative_path: "clips/stale-a.mp4",
      name: "stale-a.mp4",
      size_bytes: 100,
    },
    {
      path: "/app/uploads/clips/stale-b.mp4",
      relative_path: "clips/stale-b.mp4",
      name: "stale-b.mp4",
      size_bytes: 100,
    },
  ],
};

describe("StorageDetailsSection", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (url.includes("/api/storage") && init?.method !== "POST") {
          return Promise.resolve({
            ok: true,
            json: async () => mockSummary,
          });
        }
        if (url.includes("/api/storage/cleanup-orphans")) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              ...mockSummary,
              counts: { ...mockSummary.counts, orphan_files: 0 },
              breakdown: { ...mockSummary.breakdown, orphans: 0 },
              orphan_paths: [],
              orphan_files: [],
              removed_files: 2,
              reclaimed_bytes: 200,
            }),
          });
        }
        return Promise.reject(new Error(`Unexpected fetch: ${url}`));
      }),
    );
  });

  it("renders orphan file list and disables delete-all when empty after cleanup", async () => {
    render(<StorageDetailsSection />);

    expect(await screen.findByText("stale-a.mp4")).toBeInTheDocument();
    expect(screen.getByText("stale-b.mp4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete all orphans/i })).toBeEnabled();
  });

  it("shows empty orphan state when count is zero", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: async () => ({
            ...mockSummary,
            counts: { ...mockSummary.counts, orphan_files: 0 },
            breakdown: { ...mockSummary.breakdown, orphans: 0 },
            orphan_paths: [],
            orphan_files: [],
          }),
        }),
      ),
    );

    render(<StorageDetailsSection />);

    expect(await screen.findByText("No orphan files")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete all orphans/i })).toBeDisabled();
  });

  it("shows the host uploads folder path for Finder access", async () => {
    render(<StorageDetailsSection />);

    expect(await screen.findByText("/Users/test/supoclip/uploads")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy uploads folder path/i })).toBeInTheDocument();
  });
});
