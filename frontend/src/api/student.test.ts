import { afterEach, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./client";
import {
  authenticate,
  decideEvidence,
  generateRoadmap,
  getEvidence,
  getProfile,
  runGap,
  uploadResume,
} from "./student";

afterEach(() => vi.unstubAllGlobals());

function clientReturning(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    ),
  );
  return new ApiClient("https://api.test", 100);
}

it("registers and returns only the access token", async () => {
  const client = clientReturning(
    { access_token: "signed-token", token_type: "bearer" },
    201,
  );
  await expect(
    authenticate(
      "register",
      {
        email: "student@example.com",
        password: "long-password",
        display_name: "Student",
      },
      client,
    ),
  ).resolves.toBe("signed-token");
  const init = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
  expect(init.credentials).toBe("omit");
  expect(init.body).toContain("student@example.com");
});

it("sends bearer ownership credentials for private profile reads", async () => {
  const client = clientReturning({
    student_id: "student_1",
    display_name: "Student",
    target_role_id: null,
    version: 1,
  });
  await expect(getProfile("private-token", client)).resolves.toMatchObject({
    student_id: "student_1",
    target_role_id: null,
  });
  const init = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
  expect((init.headers as Record<string, string>).Authorization).toBe(
    "Bearer private-token",
  );
});

it("uploads a real FormData body without forcing a content type", async () => {
  const client = clientReturning({
    resume_id: "resume_1",
    original_filename: "resume.pdf",
    status: "COMPLETED",
    version: 1,
    active: true,
    duplicate: false,
  });
  const result = await uploadResume(
    "private-token",
    new File(["pdf"], "resume.pdf", { type: "application/pdf" }),
    client,
  );
  expect(result.active).toBe(true);
  const init = vi.mocked(fetch).mock.calls[0]?.[1] as RequestInit;
  expect(init.body).toBeInstanceOf(FormData);
  expect(
    (init.headers as Record<string, string>)["Content-Type"],
  ).toBeUndefined();
});

it("decodes evidence decisions and deterministic gap metadata", async () => {
  const evidenceBody = {
    evidence_id: "evidence_1",
    raw_text: "Python",
    section: "skills",
    evidence_text: "Python",
    skill_id: "skill_python",
    skill_name: "Python",
    normalization_status: "EXACT",
    verification_status: "CONFIRMED",
  };
  await expect(
    decideEvidence(
      "token",
      "evidence_1",
      "CONFIRM",
      undefined,
      clientReturning(evidenceBody),
    ),
  ).resolves.toMatchObject({ verification_status: "CONFIRMED" });

  const gap = await runGap(
    "token",
    clientReturning(
      {
        run_id: "run_1",
        target_role_id: "role_backend_developer",
        knowledge_dataset_version: "careerpilot-knowledge-v1",
        rule_version: "evidence-gap-v1",
        items: [
          {
            skill_id: "skill_python",
            skill_name: "Python",
            importance: "CORE",
            status: "SUPPORTED",
            reason_code: "CONFIRMED_DIRECT_EVIDENCE",
          },
        ],
      },
      201,
    ),
  );
  expect(gap.items[0]).toMatchObject({ status: "SUPPORTED" });
});

it("rejects malformed private responses", async () => {
  await expect(
    getEvidence("token", "resume_1", clientReturning({ items: [] })),
  ).rejects.toBeInstanceOf(ApiError);
});

it("requests the task-oriented roadmap endpoint without exposing a raw LLM API", async () => {
  const client = clientReturning(
    { roadmap_id: "roadmap_1", items: [], evidence: [] },
    201,
  );
  await expect(
    generateRoadmap("token", "gap_1", client),
  ).resolves.toMatchObject({
    roadmap_id: "roadmap_1",
  });
  const [url, init] = vi.mocked(fetch).mock.calls[0] as [string, RequestInit];
  expect(url).toContain("/api/v1/roadmaps");
  expect(String(init.body)).toContain("gap_1");
  expect(url).not.toMatch(/llm|groq/);
});
