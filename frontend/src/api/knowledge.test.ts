import { afterEach, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./client";
import { getRoleSkills, getRoles } from "./knowledge";

afterEach(() => vi.unstubAllGlobals());
const response = (body: unknown) => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(body), { status: 200 })),
    ),
  );
  return new ApiClient("", 100);
};

it("decodes role lists", async () => {
  const client = response({
    items: [
      {
        id: "role_backend",
        kind: "Role",
        name: "Backend",
        description: "Description",
      },
    ],
    limit: 50,
    offset: 0,
  });
  expect((await getRoles(undefined, client)).items[0]?.name).toBe("Backend");
});

it("decodes role skills and provenance", async () => {
  const client = response({
    entity: {
      id: "role_backend",
      kind: "Role",
      name: "Backend",
      description: "Description",
    },
    items: [
      {
        entity: {
          id: "skill_python",
          kind: "Skill",
          name: "Python",
          description: "Description",
        },
        evidence: {
          assertion: { id: "assertion_123", importance: "CORE" },
          provenance: [
            {
              citation: { evidence: "Evidence text", locator: "line" },
              source: {
                title: "Curated",
                publisher: "CareerPilot",
                uri: "urn:test",
              },
            },
          ],
          dataset_version: "careerpilot-knowledge-v1",
        },
      },
    ],
    limit: 50,
    offset: 0,
  });
  const page = await getRoleSkills("role_backend", undefined, client);
  expect(page.items[0]?.evidence.provenance[0]?.source.title).toBe("Curated");
});

it("rejects malformed knowledge responses", async () => {
  await expect(
    getRoles(undefined, response({ items: "not-an-array" })),
  ).rejects.toBeInstanceOf(ApiError);
});
