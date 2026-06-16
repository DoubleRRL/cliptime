import { GET, PATCH } from "./route";
import { getPrismaClient } from "@/server/prisma";
import { getEffectiveSession } from "@/server/session";

vi.mock("@/server/session", () => ({
  getEffectiveSession: vi.fn(),
}));

vi.mock("@/server/prisma", () => ({
  getPrismaClient: vi.fn(),
}));

describe("/api/preferences", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns 401 when no session exists", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue(null);

    const response = await GET(new Request("http://localhost/api/preferences") as never);

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Unauthorized" });
  });

  it("returns user preferences for an authenticated user", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue({
      user: { id: "user-1" },
    } as never);
    vi.mocked(getPrismaClient).mockReturnValue({
      user: {
        findUnique: vi.fn().mockResolvedValue({
          default_font_family: "Inter",
          default_font_size: 28,
          default_font_color: "#123456",
          default_position_y: 0.72,
          default_llm_model: "ollama:llama3.1:8b",
        }),
      },
    } as never);

    const response = await GET(new Request("http://localhost/api/preferences") as never);

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      fontFamily: "Inter",
      fontSize: 28,
      fontColor: "#123456",
      highlightColor: "#8B5CF6",
      pillColor: "#1A1A1ACC",
      captionTemplate: "riverside",
      positionY: 0.72,
      llmModel: "ollama:llama3.1:8b",
    });
  });

  it("validates PATCH payloads", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue({
      user: { id: "user-1" },
    } as never);

    const response = await PATCH(
      new Request("http://localhost/api/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fontColor: "red" }),
      }) as never,
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error: "Invalid fontColor (must be hex format like #FFFFFF)",
    });
  });

  it("validates llmModel", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue({
      user: { id: "user-1" },
    } as never);

    const response = await PATCH(
      new Request("http://localhost/api/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ llmModel: 42 }),
      }) as never,
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error: "Invalid llmModel",
    });
  });

  it("validates positionY", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue({
      user: { id: "user-1" },
    } as never);

    const response = await PATCH(
      new Request("http://localhost/api/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ positionY: 0.4 }),
      }) as never,
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error: "Invalid positionY (must be between 0.55 and 0.85)",
    });
  });

  it("updates stored preferences", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue({
      user: { id: "user-1" },
    } as never);
    const update = vi.fn().mockResolvedValue({
      default_font_family: "TikTokSans-Regular",
      default_font_size: 24,
      default_font_color: "#FFFFFF",
      default_llm_model: null,
    });
    vi.mocked(getPrismaClient).mockReturnValue({
      user: { update },
    } as never);

    const response = await PATCH(
      new Request("http://localhost/api/preferences", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fontFamily: "TikTokSans-Regular",
          fontSize: 24,
          fontColor: "#FFFFFF",
        }),
      }) as never,
    );

    expect(update).toHaveBeenCalled();
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toMatchObject({
      fontFamily: "TikTokSans-Regular",
      fontSize: 24,
      fontColor: "#FFFFFF",
    });
  });
});
