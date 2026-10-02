import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StudentWorkspace } from "./StudentWorkspace";

afterEach(() => vi.unstubAllGlobals());

const profile = (target: string | null) => ({
  student_id: "student_0123456789abcdef0123456789abcdef",
  display_name: "Synthetic Student",
  target_role_id: target,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  version: target ? 2 : 1,
});
const resume = {
  resume_id: "resume_0123456789abcdef0123456789abcdef",
  original_filename: "synthetic.pdf",
  media_type: "application/pdf",
  size: 100,
  content_hash: "a".repeat(64),
  status: "AWAITING_CONFIRMATION",
  version: 1,
  active: true,
  duplicate: false,
  parser_version: "resume-parser-v1",
  uploaded_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
};
const evidence = {
  evidence_id: "evidence_0123456789abcdef0123456789abcdef",
  student_id: "student_0123456789abcdef0123456789abcdef",
  resume_id: resume.resume_id,
  raw_text: "Python",
  section: "PROJECTS",
  evidence_text: "Built REST APIs with Python",
  skill_id: "skill_python",
  skill_name: "Python",
  normalization_status: "EXACT",
  extraction_method: "DETERMINISTIC_ALIAS_V1",
  verification_status: "EXTRACTED",
  observed_at: "2026-10-01T00:00:00Z",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
};

it("runs the visible auth, evidence review, role and gap workflow", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      let body: unknown;
      let status = 200;
      if (url.endsWith("/auth/register")) {
        body = {
          access_token: "signed-token",
          token_type: "bearer",
          expires_in: 3600,
        };
        status = 201;
      } else if (url.endsWith("/student/profile") && method === "GET") {
        body = profile(null);
      } else if (url.endsWith("/student/profile") && method === "PUT") {
        body = profile("role_backend_developer");
      } else if (url.includes("/knowledge/roles")) {
        body = {
          items: [
            {
              id: "role_backend_developer",
              kind: "Role",
              name: "Backend Developer",
              description: "Backend role",
            },
          ],
          limit: 50,
          offset: 0,
        };
      } else if (url.includes("/knowledge/skills")) {
        body = {
          items: [
            {
              id: "skill_python",
              kind: "Skill",
              name: "Python",
              description: "Python language",
            },
          ],
          limit: 100,
          offset: 0,
        };
      } else if (url.endsWith("/student/resumes") && method === "POST") {
        body = resume;
      } else if (url.endsWith("/student/resumes")) {
        body = [resume];
      } else if (url.includes("/evidence/") && method === "PUT") {
        body = { ...evidence, verification_status: "CONFIRMED" };
      } else if (url.endsWith("/evidence") && !url.includes("/retrieval/")) {
        body = [evidence];
      } else if (url.endsWith("/gap-analyses")) {
        status = 201;
        body = {
          run_id: "gap_0123456789abcdef0123456789abcdef",
          target_role_id: "role_backend_developer",
          knowledge_dataset_version: "careerpilot-knowledge-v1",
          rule_version: "gap-rules-v1",
          items: [
            {
              skill_id: "skill_python",
              skill_name: "Python",
              importance: "CORE",
              status: "PARTIALLY_SUPPORTED",
              reason_code: "UNCONFIRMED_DIRECT_EVIDENCE",
            },
          ],
        };
      } else if (url.includes("/retrieval/gaps/")) {
        body = {
          task: "GAP_RESOURCES",
          retrieval_strategy: "GRAPH_THEN_VECTOR",
          graph_evidence: [
            {
              assertion_id: "assertion_0123456789abcdef0123456789abcdef",
              entity_name: "Python data structures tutorial",
              relationship_type: "TEACHES_SKILL",
              importance: "UNSPECIFIED",
              source_ids: ["source_python"],
            },
          ],
          vector_evidence: [
            {
              chunk_id: "chunk_0123456789abcdef0123456789abcdef",
              resource_id: "resource_python",
              source_id: "source_python",
              text: "Python lists and dictionaries support collection operations.",
              similarity_score: 0.91,
              metadata: { resource_name: "Python data structures tutorial" },
            },
          ],
          sufficiency: {
            status: "SUFFICIENT",
            reasons: ["REQUIRED_EVIDENCE_PRESENT"],
          },
          trace_id: "trace_0123456789abcdef0123456789abcdef",
        };
      } else if (url.endsWith("/roadmaps")) {
        status = 201;
        body = {
          roadmap_id: "roadmap_0123456789abcdef0123456789abcdef",
          version: 1,
          generated_at: "2026-10-02T00:00:00Z",
          prompt_version: "roadmap-prompt-v1",
          model_provider: "groq",
          model_id: "openai/gpt-oss-120b",
          retrieval_trace_ids: ["trace_0123456789abcdef0123456789abcdef"],
          evidence_bundle_version: "evidence-bundle-test",
          coverage_status: "SUFFICIENT",
          omitted_skill_ids: [],
          items: [
            {
              item_id: "roadmap_item_0123456789abcdef0123456789abcdef",
              skill_id: "skill_python",
              skill_name: "Python",
              priority: "MEDIUM",
              reason_code: "PARTIALLY_SUPPORTED_CORE_REQUIREMENT",
              recommendation:
                "Strengthen Python through the supplied documentation.",
              evidence_ids: [
                "assertion_python",
                "status_python",
                "chunk_python",
              ],
              resource_ids: ["resource_python"],
              sequence: 1,
              suggested_activities: [
                "Complete the validated collection examples.",
              ],
              status: "NOT_STARTED",
            },
          ],
          evidence: [
            {
              evidence_id: "assertion_python",
              evidence_type: "ROLE_REQUIREMENT",
              skill_id: "skill_python",
              label: "Python is CORE for the target role.",
              source_id: "source_curated",
              resource_id: null,
              resource_name: null,
              text: null,
            },
            {
              evidence_id: "status_python",
              evidence_type: "STUDENT_STATUS",
              skill_id: "skill_python",
              label:
                "CareerPilot has direct evidence that is not fully confirmed.",
              source_id: "gap_test",
              resource_id: null,
              resource_name: null,
              text: null,
            },
            {
              evidence_id: "chunk_python",
              evidence_type: "RESOURCE",
              skill_id: "skill_python",
              label: "Validated learning resource passage.",
              source_id: "source_python",
              resource_id: "resource_python",
              resource_name: "Python documentation",
              text: "Python collection examples.",
            },
          ],
        };
      } else {
        throw new Error(`Unexpected request: ${method} ${url}`);
      }
      return new Response(JSON.stringify(body), { status });
    }),
  );

  render(<StudentWorkspace />);
  fireEvent.change(screen.getByLabelText("Display name"), {
    target: { value: "Synthetic Student" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "synthetic@example.test" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "synthetic-test-password" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Create private workspace" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Synthetic Student" }),
  ).toBeInTheDocument();

  expect(
    await screen.findByText("Built REST APIs with Python"),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("PDF or DOCX resume")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  await waitFor(() =>
    expect(screen.getByText(/CONFIRMED/)).toBeInTheDocument(),
  );

  fireEvent.change(screen.getByLabelText("Canonical target role"), {
    target: { value: "role_backend_developer" },
  });
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Run evidence gap analysis" }),
    ).toBeEnabled(),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Run evidence gap analysis" }),
  );
  expect(await screen.findByText("PARTIALLY SUPPORTED")).toBeInTheDocument();
  expect(
    screen.getByText("Direct evidence exists but is not confirmed."),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Retrieve evidence" }));
  expect(await screen.findByText("Retrieval inspection")).toBeInTheDocument();
  expect(screen.getByText(/Why this skill matters/)).toBeInTheDocument();
  expect(screen.getByText(/Python lists and dictionaries/)).toBeInTheDocument();
  expect(screen.getAllByText(/source_python/)).toHaveLength(2);
  fireEvent.click(
    screen.getByRole("button", { name: "Generate grounded learning roadmap" }),
  );
  expect(
    await screen.findByText("Validated evidence, generated recommendations"),
  ).toBeInTheDocument();
  expect(screen.getByText("Requirement · graph fact")).toBeInTheDocument();
  expect(screen.getByText(/generated synthesis/)).toBeInTheDocument();
  expect(screen.getByText("Python documentation")).toBeInTheDocument();
});
