import { ApiClient, ApiError, apiClient } from "./client";

export type Entity = {
  id: string;
  kind: string;
  name: string;
  description: string;
};
export type Citation = {
  citation: { evidence: string; locator: string };
  source: { title: string; publisher: string; uri: string };
};
export type SkillRelation = {
  entity: Entity;
  evidence: {
    assertion: { id: string; importance: string };
    provenance: Citation[];
    dataset_version: string;
  };
};
export type EntityPage = { items: Entity[]; limit: number; offset: number };
export type RelationsPage = {
  entity: Entity;
  items: SkillRelation[];
  limit: number;
  offset: number;
};

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new ApiError(
      "INVALID_RESPONSE",
      "The knowledge response is invalid.",
    );
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string")
    throw new ApiError(
      "INVALID_RESPONSE",
      "The knowledge response is invalid.",
    );
  return value;
}
function entity(value: unknown): Entity {
  const item = record(value);
  return {
    id: text(item.id),
    kind: text(item.kind),
    name: text(item.name),
    description: text(item.description),
  };
}
function citation(value: unknown): Citation {
  const item = record(value);
  const detail = record(item.citation);
  const source = record(item.source);
  return {
    citation: {
      evidence: text(detail.evidence),
      locator: text(detail.locator),
    },
    source: {
      title: text(source.title),
      publisher: text(source.publisher),
      uri: text(source.uri),
    },
  };
}

export async function getRoles(
  signal?: AbortSignal,
  client: ApiClient = apiClient,
): Promise<EntityPage> {
  const body = record(
    (await client.get("/api/v1/knowledge/roles", signal)).body,
  );
  if (
    !Array.isArray(body.items) ||
    typeof body.limit !== "number" ||
    typeof body.offset !== "number"
  )
    throw new ApiError(
      "INVALID_RESPONSE",
      "The knowledge response is invalid.",
    );
  return {
    items: body.items.map(entity),
    limit: body.limit,
    offset: body.offset,
  };
}

export async function getSkills(
  signal?: AbortSignal,
  client: ApiClient = apiClient,
): Promise<EntityPage> {
  const body = record(
    (await client.get("/api/v1/knowledge/skills?limit=100", signal)).body,
  );
  if (
    !Array.isArray(body.items) ||
    typeof body.limit !== "number" ||
    typeof body.offset !== "number"
  )
    throw new ApiError(
      "INVALID_RESPONSE",
      "The knowledge response is invalid.",
    );
  return {
    items: body.items.map(entity),
    limit: body.limit,
    offset: body.offset,
  };
}

export async function getRoleSkills(
  roleId: string,
  signal?: AbortSignal,
  client: ApiClient = apiClient,
): Promise<RelationsPage> {
  const body = record(
    (
      await client.get(
        `/api/v1/knowledge/roles/${encodeURIComponent(roleId)}/skills`,
        signal,
      )
    ).body,
  );
  if (
    !Array.isArray(body.items) ||
    typeof body.limit !== "number" ||
    typeof body.offset !== "number"
  )
    throw new ApiError(
      "INVALID_RESPONSE",
      "The knowledge response is invalid.",
    );
  return {
    entity: entity(body.entity),
    items: body.items.map((value) => {
      const item = record(value);
      const evidence = record(item.evidence);
      const assertion = record(evidence.assertion);
      if (!Array.isArray(evidence.provenance))
        throw new ApiError(
          "INVALID_RESPONSE",
          "The knowledge response is invalid.",
        );
      return {
        entity: entity(item.entity),
        evidence: {
          assertion: {
            id: text(assertion.id),
            importance: text(assertion.importance),
          },
          provenance: evidence.provenance.map(citation),
          dataset_version: text(evidence.dataset_version),
        },
      };
    }),
    limit: body.limit,
    offset: body.offset,
  };
}
