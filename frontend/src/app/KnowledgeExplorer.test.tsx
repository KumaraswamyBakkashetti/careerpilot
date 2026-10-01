import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { KnowledgeExplorer } from "./KnowledgeExplorer";

afterEach(() => vi.unstubAllGlobals());

const entity = (id: string, kind: string, name: string) => ({
  id,
  kind,
  name,
  description: `${name} description`,
});
function graphFetch(empty = false) {
  return vi.fn((url: string) =>
    Promise.resolve(
      new Response(
        JSON.stringify(
          url.endsWith("/roles")
            ? {
                items: empty
                  ? []
                  : [
                      entity("role_backend", "Role", "Backend Developer"),
                      entity("role_qa", "Role", "QA Engineer"),
                    ],
                limit: 50,
                offset: 0,
              }
            : {
                entity: entity(
                  url.includes("role_qa") ? "role_qa" : "role_backend",
                  "Role",
                  "Role",
                ),
                items: [
                  {
                    entity: entity("skill_python", "Skill", "Python"),
                    evidence: {
                      assertion: { id: "assertion_123", importance: "CORE" },
                      provenance: [
                        {
                          citation: {
                            evidence: "Curated mapping",
                            locator: "row",
                          },
                          source: {
                            title: "CareerPilot profiles",
                            publisher: "CareerPilot",
                            uri: "https://example.test/source",
                          },
                        },
                      ],
                      dataset_version: "careerpilot-knowledge-v1",
                    },
                  },
                ],
                limit: 50,
                offset: 0,
              },
        ),
        { status: 200 },
      ),
    ),
  );
}

it("loads roles, selects a role, and renders skill provenance", async () => {
  const fetcher = graphFetch();
  vi.stubGlobal("fetch", fetcher);
  render(<KnowledgeExplorer />);
  expect(screen.getByText("Loading career roles…")).toBeInTheDocument();
  expect(await screen.findByText("Python")).toBeInTheDocument();
  expect(screen.getByText("CORE")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: /CareerPilot profiles/ }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Role profile"), {
    target: { value: "role_qa" },
  });
  expect(await screen.findByText("Python")).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledWith(
    expect.stringContaining("role_qa"),
    expect.anything(),
  );
});

it("distinguishes an empty graph from an outage", async () => {
  vi.stubGlobal("fetch", graphFetch(true));
  const view = render(<KnowledgeExplorer />);
  expect(
    await screen.findByText("No curated role profiles are available."),
  ).toBeInTheDocument();
  view.unmount();
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            error: {
              code: "DEPENDENCY_UNAVAILABLE",
              message: "hidden",
              request_id: "r",
            },
          }),
          { status: 503 },
        ),
      ),
    ),
  );
  render(<KnowledgeExplorer />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Neo4j is offline",
  );
});
