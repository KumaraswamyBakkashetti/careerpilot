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
      } else if (url.endsWith("/evidence")) {
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
              status: "SUPPORTED",
              reason_code: "CONFIRMED_DIRECT_EVIDENCE",
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
  expect(await screen.findByText("SUPPORTED")).toBeInTheDocument();
  expect(
    screen.getByText("Supported by confirmed direct evidence."),
  ).toBeInTheDocument();
});
