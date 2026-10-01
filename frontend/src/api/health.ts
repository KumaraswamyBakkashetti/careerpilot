import { ApiClient, ApiError, apiClient } from "./client";

export type DependencyState = "up" | "down";
export type FoundationHealth = {
  status: "ready" | "not_ready";
  dependencies: { mongodb: DependencyState; neo4j: DependencyState };
  requestId: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isState(value: unknown): value is DependencyState {
  return value === "up" || value === "down";
}

export async function getHealth(
  signal?: AbortSignal,
  client: ApiClient = apiClient,
): Promise<FoundationHealth> {
  const live = await client.get("/health/live", signal);
  if (
    live.status !== 200 ||
    !isRecord(live.body) ||
    live.body.status !== "alive"
  ) {
    throw new ApiError(
      "BACKEND_UNAVAILABLE",
      "The backend is not responding normally.",
      live.status,
      live.requestId ?? undefined,
    );
  }
  const ready = await client.get("/health/ready", signal, [200, 503]);
  const body = ready.body;
  if (
    !isRecord(body) ||
    !isRecord(body.dependencies) ||
    !isState(body.dependencies.mongodb) ||
    !isState(body.dependencies.neo4j) ||
    (body.status !== "ready" && body.status !== "not_ready") ||
    (body.status === "ready" ? ready.status !== 200 : ready.status !== 503) ||
    (body.dependencies.mongodb === "up" && body.dependencies.neo4j === "up") !==
      (body.status === "ready")
  ) {
    throw new ApiError(
      "INVALID_RESPONSE",
      "The backend health contract could not be read.",
      ready.status,
      ready.requestId ?? undefined,
    );
  }
  return {
    status: body.status,
    dependencies: {
      mongodb: body.dependencies.mongodb,
      neo4j: body.dependencies.neo4j,
    },
    requestId: ready.requestId,
  };
}
