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
export type RetrievalBundle = {
  trace_id: string;
  retrieval_strategy: string;
  graph_evidence: Array<{
    assertion_id: string;
    entity_name: string;
    relationship_type: string;
    importance: string;
    source_ids: string[];
  }>;
  vector_evidence: Array<{
    chunk_id: string;
    resource_id: string;
    source_id: string;
    text: string;
    similarity_score: number;
    metadata: Record<string, string | string[]>;
  }>;
  sufficiency: { status: string; reasons: string[] };
};
export type RoadmapEvidence = {
  evidence_id: string;
  evidence_type: "ROLE_REQUIREMENT" | "STUDENT_STATUS" | "RESOURCE";
  skill_id: string;
  label: string;
  source_id: string;
  resource_id: string | null;
  resource_name: string | null;
  text: string | null;
};
export type Roadmap = {
  roadmap_id: string;
  version: number;
  generated_at: string;
  prompt_version: string;
  model_provider: string;
  model_id: string;
  retrieval_trace_ids: string[];
  evidence_bundle_version: string;
  coverage_status: "SUFFICIENT" | "PARTIAL";
  omitted_skill_ids: string[];
  items: Array<{
    item_id: string;
    skill_id: string;
    skill_name: string;
    priority: "HIGH" | "MEDIUM" | "LOW";
    reason_code: string;
    recommendation: string;
    evidence_ids: string[];
    resource_ids: string[];
    sequence: number;
    suggested_activities: string[];
    status: string;
  }>;
  evidence: RoadmapEvidence[];
};
export type CompanyPreparation = {
  preparation_id: string;
  company_name: string;
  company_role_id: string;
  company_role_name: string;
  synthetic: boolean;
  limitation: string;
  prompt_version: string;
  facts: Array<{
    fact_type: string;
    entity_id: string;
    label: string;
    assertion_id: string;
    source_ids: string[];
  }>;
  items: Array<{
    skill_id: string;
    skill_name: string;
    importance: string;
    student_status: string;
    recommendation: string;
    activities: string[];
    resource_ids: string[];
  }>;
};
export type Interview = {
  session_id: string;
  company_role_id: string;
  company_role_name: string;
  interview_type: string;
  difficulty: string;
  status: "ACTIVE" | "COMPLETED";
  questions: Array<{
    question_id: string;
    sequence: number;
    text: string;
    topic_name: string;
    skill_ids: string[];
  }>;
  responses: Array<{
    response_id: string;
    question_id: string;
    answer: string;
  }>;
  evaluations: Array<{
    evaluation_id: string;
    question_id: string;
    status: string;
    dimensions: Array<{
      dimension: string;
      rating: string;
      feedback: string;
    }>;
    strengths: string[];
    improvements: string[];
    practice_evidence_ids: string[];
  }>;
};
export type Readiness = {
  snapshot_id: string;
  score: number;
  category: string;
  rule_version: string;
  version: number;
  components: Array<{
    component: string;
    score: number;
    weight: number;
    explanation: string;
  }>;
  priority_skill_ids: string[];
  limitation: string;
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

export async function retrieveGapEvidence(
  token: string,
  gapId: string,
  skillId: string,
  client: ApiClient = apiClient,
): Promise<RetrievalBundle> {
  return object(
    (
      await client.send(
        "POST",
        `/api/v1/retrieval/gaps/${encodeURIComponent(gapId)}/evidence`,
        json({ skill_id: skillId }),
        token,
        undefined,
        [200],
        "application/json",
      )
    ).body,
  ) as RetrievalBundle;
}

export async function generateRoadmap(
  token: string,
  gapId: string,
  client: ApiClient = apiClient,
): Promise<Roadmap> {
  return object(
    (
      await client.send(
        "POST",
        "/api/v1/roadmaps",
        json({ gap_run_id: gapId }),
        token,
        undefined,
        [201],
        "application/json",
      )
    ).body,
  ) as Roadmap;
}

export async function getCompanies(
  token: string,
  client: ApiClient = apiClient,
): Promise<Array<{ id: string; name: string; synthetic: boolean }>> {
  const body = object(
    (await client.send("GET", "/api/v1/companies", undefined, token)).body,
  );
  if (!Array.isArray(body.items))
    throw new ApiError("INVALID_RESPONSE", "Invalid company response.");
  return body.items.map((value) => {
    const item = object(value);
    return {
      id: text(item.id),
      name: text(item.name),
      synthetic: Boolean(item.synthetic),
    };
  });
}

export async function getCompanyRoles(
  token: string,
  companyId: string,
  client: ApiClient = apiClient,
): Promise<Array<{ id: string; name: string }>> {
  const body = object(
    (
      await client.send(
        "GET",
        `/api/v1/companies/${encodeURIComponent(companyId)}/roles`,
        undefined,
        token,
      )
    ).body,
  );
  if (!Array.isArray(body.items))
    throw new ApiError("INVALID_RESPONSE", "Invalid company-role response.");
  return body.items.map((value) => {
    const relation = object(value);
    const item = object(relation.entity);
    return { id: text(item.id), name: text(item.name) };
  });
}

export async function generateCompanyPreparation(
  token: string,
  companyRoleId: string,
  gapRunId: string,
  client: ApiClient = apiClient,
): Promise<CompanyPreparation> {
  return object(
    (
      await client.send(
        "POST",
        "/api/v1/company-preparations",
        json({ company_role_id: companyRoleId, gap_run_id: gapRunId }),
        token,
        undefined,
        [201],
        "application/json",
      )
    ).body,
  ) as CompanyPreparation;
}

export async function startInterview(
  token: string,
  companyRoleId: string,
  client: ApiClient = apiClient,
): Promise<Interview> {
  return object(
    (
      await client.send(
        "POST",
        "/api/v1/interviews",
        json({
          company_role_id: companyRoleId,
          interview_type: "ROLE_SPECIFIC",
          difficulty: "INTERMEDIATE",
          question_count: 2,
        }),
        token,
        undefined,
        [201],
        "application/json",
      )
    ).body,
  ) as Interview;
}

export async function submitInterviewAnswer(
  token: string,
  sessionId: string,
  questionId: string,
  answer: string,
  client: ApiClient = apiClient,
): Promise<Interview> {
  return object(
    (
      await client.send(
        "POST",
        `/api/v1/interviews/${encodeURIComponent(sessionId)}/responses`,
        json({ question_id: questionId, answer }),
        token,
        undefined,
        [200],
        "application/json",
      )
    ).body,
  ) as Interview;
}

export async function completeInterview(
  token: string,
  sessionId: string,
  client: ApiClient = apiClient,
): Promise<Interview> {
  return object(
    (
      await client.send(
        "POST",
        `/api/v1/interviews/${encodeURIComponent(sessionId)}/complete`,
        undefined,
        token,
      )
    ).body,
  ) as Interview;
}

export async function calculateReadiness(
  token: string,
  gapRunId: string,
  client: ApiClient = apiClient,
): Promise<Readiness> {
  return object(
    (
      await client.send(
        "POST",
        "/api/v1/readiness",
        json({ gap_run_id: gapRunId }),
        token,
        undefined,
        [201],
        "application/json",
      )
    ).body,
  ) as Readiness;
}
