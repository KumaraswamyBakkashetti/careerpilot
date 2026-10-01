import { ApiClient, ApiError, apiClient } from "./client";

export type Profile = {
  student_id: string;
  display_name: string;
  target_role_id: string | null;
  version: number;
};
export type Resume = {
  resume_id: string;
  original_filename: string;
  status: string;
  version: number;
  active: boolean;
  duplicate: boolean;
};
export type Evidence = {
  evidence_id: string;
  raw_text: string;
  section: string;
  evidence_text: string;
  skill_id: string | null;
  skill_name: string | null;
  normalization_status: string;
  verification_status: string;
};
export type GapItem = {
  skill_id: string;
  skill_name: string;
  importance: string;
  status: string;
  reason_code: string;
};
export type GapRun = {
  run_id: string;
  target_role_id: string;
  knowledge_dataset_version: string;
  rule_version: string;
  items: GapItem[];
};

const object = (value: unknown): Record<string, unknown> => {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    throw new ApiError(
      "INVALID_RESPONSE",
      "The private student response is invalid.",
    );
  return value as Record<string, unknown>;
};
const text = (value: unknown) => {
  if (typeof value !== "string")
    throw new ApiError(
      "INVALID_RESPONSE",
      "The private student response is invalid.",
    );
  return value;
};
const nullableText = (value: unknown) => (value === null ? null : text(value));
const json = (value: unknown) => JSON.stringify(value);

export async function authenticate(
  mode: "register" | "token",
  body: Record<string, string>,
  client: ApiClient = apiClient,
): Promise<string> {
  const result = object(
    (
      await client.send(
        "POST",
        `/api/v1/auth/${mode}`,
        json(body),
        undefined,
        undefined,
        mode === "register" ? [201] : [200],
        "application/json",
      )
    ).body,
  );
  return text(result.access_token);
}

export async function getProfile(
  token: string,
  client: ApiClient = apiClient,
): Promise<Profile> {
  const body = object(
    (await client.send("GET", "/api/v1/student/profile", undefined, token))
      .body,
  );
  return {
    student_id: text(body.student_id),
    display_name: text(body.display_name),
    target_role_id: nullableText(body.target_role_id),
    version: Number(body.version),
  };
}

export async function updateProfile(
  token: string,
  values: Record<string, string>,
  client: ApiClient = apiClient,
): Promise<Profile> {
  const body = object(
    (
      await client.send(
        "PUT",
        "/api/v1/student/profile",
        json(values),
        token,
        undefined,
        [200],
        "application/json",
      )
    ).body,
  );
  return {
    student_id: text(body.student_id),
    display_name: text(body.display_name),
    target_role_id: nullableText(body.target_role_id),
    version: Number(body.version),
  };
}

const resume = (value: unknown): Resume => {
  const body = object(value);
  return {
    resume_id: text(body.resume_id),
    original_filename: text(body.original_filename),
    status: text(body.status),
    version: Number(body.version),
    active: Boolean(body.active),
    duplicate: Boolean(body.duplicate),
  };
};
export async function uploadResume(
  token: string,
  file: File,
  client: ApiClient = apiClient,
): Promise<Resume> {
  const form = new FormData();
  form.append("file", file);
  return resume(
    (await client.send("POST", "/api/v1/student/resumes", form, token)).body,
  );
}
export async function getResumes(
  token: string,
  client: ApiClient = apiClient,
): Promise<Resume[]> {
  const body = (
    await client.send("GET", "/api/v1/student/resumes", undefined, token)
  ).body;
  if (!Array.isArray(body))
    throw new ApiError(
      "INVALID_RESPONSE",
      "The private student response is invalid.",
    );
  return body.map(resume);
}
const evidence = (value: unknown): Evidence => {
  const body = object(value);
  return {
    evidence_id: text(body.evidence_id),
    raw_text: text(body.raw_text),
    section: text(body.section),
    evidence_text: text(body.evidence_text),
    skill_id: nullableText(body.skill_id),
    skill_name: nullableText(body.skill_name),
    normalization_status: text(body.normalization_status),
    verification_status: text(body.verification_status),
  };
};
export async function getEvidence(
  token: string,
  resumeId: string,
  client: ApiClient = apiClient,
): Promise<Evidence[]> {
  const body = (
    await client.send(
      "GET",
      `/api/v1/student/resumes/${encodeURIComponent(resumeId)}/evidence`,
      undefined,
      token,
    )
  ).body;
  if (!Array.isArray(body))
    throw new ApiError(
      "INVALID_RESPONSE",
      "The private student response is invalid.",
    );
  return body.map(evidence);
}
export async function decideEvidence(
  token: string,
  id: string,
  action: "CONFIRM" | "REJECT",
  corrected?: string,
  client: ApiClient = apiClient,
): Promise<Evidence> {
  return evidence(
    (
      await client.send(
        "PUT",
        `/api/v1/student/evidence/${encodeURIComponent(id)}`,
        json({
          action,
          ...(corrected ? { corrected_skill_id: corrected } : {}),
        }),
        token,
        undefined,
        [200],
        "application/json",
      )
    ).body,
  );
}
export async function runGap(
  token: string,
  client: ApiClient = apiClient,
): Promise<GapRun> {
  const body = object(
    (
      await client.send(
        "POST",
        "/api/v1/student/gap-analyses",
        undefined,
        token,
        undefined,
        [201],
      )
    ).body,
  );
  if (!Array.isArray(body.items))
    throw new ApiError(
      "INVALID_RESPONSE",
      "The private student response is invalid.",
    );
  return {
    run_id: text(body.run_id),
    target_role_id: text(body.target_role_id),
    knowledge_dataset_version: text(body.knowledge_dataset_version),
    rule_version: text(body.rule_version),
    items: body.items.map((value) => {
      const item = object(value);
      return {
        skill_id: text(item.skill_id),
        skill_name: text(item.skill_name),
        importance: text(item.importance),
        status: text(item.status),
        reason_code: text(item.reason_code),
      };
    }),
  };
}
