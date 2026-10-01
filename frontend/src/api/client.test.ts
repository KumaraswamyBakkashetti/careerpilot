import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("API client", () => {
  it("uses centralized URL, request IDs and no credentials", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response('{"status":"alive"}', {
        headers: { "X-Request-ID": "returned-id" },
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    const result = await new ApiClient("https://api.test/").get("/health/live");
    expect(result).toEqual({
      status: 200,
      body: { status: "alive" },
      requestId: "returned-id",
    });
    expect(fetcher.mock.calls[0]?.[0]).toBe("https://api.test/health/live");
    expect(fetcher.mock.calls[0]?.[1].credentials).toBe("omit");
    expect(fetcher.mock.calls[0]?.[1].headers["X-Request-ID"]).toMatch(
      /^[a-z0-9-]+$/,
    );
  });
  it("preserves structured non-200 bodies for health contract handling", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response('{"status":"not_ready"}', { status: 503 }),
        ),
    );
    expect(
      (await new ApiClient().get("/health/ready", undefined, [200, 503]))
        .status,
    ).toBe(503);
  });
  it("normalizes network failures without raw error content", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("sensitive raw detail")),
    );
    await expect(new ApiClient().get("/health/live")).rejects.toMatchObject({
      code: "NETWORK_ERROR",
      message: "The backend could not be reached.",
    });
  });
  it("rejects malformed JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>bad proxy</html>")),
    );
    await expect(new ApiClient().get("/health/live")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  });
  it("normalizes HTTP errors with code and request ID", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            '{"error":{"code":"NOT_FOUND","message":"private content"}}',
            { status: 404, headers: { "X-Request-ID": "error-trace" } },
          ),
        ),
    );
    await expect(new ApiClient().get("/missing")).rejects.toMatchObject({
      code: "NOT_FOUND",
      status: 404,
      requestId: "error-trace",
      message: "The backend could not complete the request.",
    });
  });
  it("cancels timed out requests", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      ),
    );
    const result = expect(
      new ApiClient("", 100).get("/health/live"),
    ).rejects.toMatchObject({ code: "TIMEOUT" });
    await vi.advanceTimersByTimeAsync(101);
    await result;
  });
  it("supports caller cancellation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () =>
              reject(new DOMException("Aborted", "AbortError")),
            );
          }),
      ),
    );
    const controller = new AbortController();
    const result = expect(
      new ApiClient().get("/health/live", controller.signal),
    ).rejects.toMatchObject({ code: "CANCELLED" });
    controller.abort();
    await result;
  });
});
