// @vitest-environment node
import { expect, it } from "vitest";
import { ApiClient } from "./client";
import { getHealth } from "./health";

it.skipIf(process.env.CP_RUN_FRONTEND_INTEGRATION !== "1")(
  "real frontend client → Vite proxy → FastAPI → both databases",
  async () => {
    const health = await getHealth(
      undefined,
      new ApiClient("http://127.0.0.1:5173"),
    );
    expect(health.status).toBe("ready");
    expect(health.dependencies).toEqual({ mongodb: "up", neo4j: "up" });
    expect(health.requestId).toMatch(/^[A-Za-z0-9_-]{1,64}$/);
  },
);
