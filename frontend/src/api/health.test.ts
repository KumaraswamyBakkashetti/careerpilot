import { afterEach, expect, it, vi } from "vitest";
import { getHealth } from "./health";

afterEach(() => vi.unstubAllGlobals());

function responses(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(new Response('{"status":"alive"}'))
      .mockResolvedValueOnce(new Response(JSON.stringify(body), { status })),
  );
}

it("parses ready health", async () => {
  responses(200, {
    status: "ready",
    dependencies: { mongodb: "up", neo4j: "up" },
  });
  expect((await getHealth()).status).toBe("ready");
});
it("parses real 503 readiness as reachable backend", async () => {
  responses(503, {
    status: "not_ready",
    dependencies: { mongodb: "up", neo4j: "down" },
    error: { code: "DEPENDENCY_UNAVAILABLE" },
  });
  expect((await getHealth()).dependencies).toEqual({
    mongodb: "up",
    neo4j: "down",
  });
});
it.each([
  { status: "ready", dependencies: { mongodb: "up" } },
  { status: "ready", dependencies: { mongodb: "up", neo4j: "down" } },
  { status: "unknown", dependencies: { mongodb: "up", neo4j: "up" } },
])("rejects incompatible or contradictory contracts", async (body) => {
  responses(200, body);
  await expect(getHealth()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});
it("does not treat a failing liveness endpoint as available", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("{}", { status: 500 })),
  );
  await expect(getHealth()).rejects.toMatchObject({ code: "HTTP_ERROR" });
});
