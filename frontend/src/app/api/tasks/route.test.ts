import { GET } from "./route";
import { fetchBackend } from "@/server/backend-api";
import { getEffectiveSession } from "@/server/session";

vi.mock("@/server/session", () => ({
  getEffectiveSession: vi.fn(),
}));

vi.mock("@/server/backend-api", async () => {
  const actual = await vi.importActual<typeof import("@/server/backend-api")>(
    "@/server/backend-api",
  );
  return {
    ...actual,
    fetchBackend: vi.fn(),
  };
});

describe("/api/tasks", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("returns 401 when unauthenticated", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue(null);

    const response = await GET(
      new Request("http://localhost/api/tasks") as never,
    );

    expect(response.status).toBe(401);
  });

  it("forwards the backend response and trace headers", async () => {
    vi.mocked(getEffectiveSession).mockResolvedValue({
      user: { id: "user-1" },
    } as never);
    vi.mocked(fetchBackend).mockResolvedValue(
      new Response(JSON.stringify({ tasks: [] }), {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "no-store",
          "x-trace-id": "trace-1",
        },
      }),
    );

    const response = await GET(
      new Request("http://localhost/api/tasks?limit=100&offset=0") as never,
    );

    expect(fetchBackend).toHaveBeenCalledWith(
      "/tasks/?limit=100&offset=0",
      expect.objectContaining({
        method: "GET",
        userId: "user-1",
      }),
    );
    expect(response.headers.get("x-trace-id")).toBe("trace-1");
    await expect(response.json()).resolves.toEqual({ tasks: [] });
  });
});
