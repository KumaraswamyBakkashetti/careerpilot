import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { getRoles, getSkills, type Entity } from "../api/knowledge";
import {
  authenticate,
  calculateReadiness,
  completeInterview,
  decideEvidence,
  generateRoadmap,
  generateCompanyPreparation,
  getCompanies,
  getCompanyRoles,
  getEvidence,
  getProfile,
  getResumes,
  runGap,
  retrieveGapEvidence,
  startInterview,
  submitInterviewAnswer,
  updateProfile,
  uploadResume,
  type Evidence,
  type GapRun,
  type RetrievalBundle,
  type Profile,
  type Roadmap,
  type CompanyPreparation,
  type Interview,
  type Readiness,
  type Resume,
} from "../api/student";

const errorMessage = (error: unknown) =>
  error instanceof ApiError
    ? error.code === "RATE_LIMITED"
      ? "Roadmap generation is rate limited. Please try again later."
      : error.code === "ROADMAP_EVIDENCE_INSUFFICIENT"
        ? "CareerPilot needs more validated evidence before generating a roadmap."
        : error.code === "PROVIDER_UNAVAILABLE" ||
            error.code === "MODEL_UNAVAILABLE"
          ? "Roadmap generation is temporarily unavailable; your evidence is safe."
          : error.code === "DEPENDENCY_UNAVAILABLE"
            ? "Private student services are temporarily unavailable."
            : "The request could not be completed. Check the supplied information."
    : "The request could not be completed.";

export function StudentWorkspace() {
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<"register" | "token">("register");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [roles, setRoles] = useState<Entity[]>([]);
  const [skills, setSkills] = useState<Entity[]>([]);
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [gap, setGap] = useState<GapRun | null>(null);
  const [retrieval, setRetrieval] = useState<RetrievalBundle | null>(null);
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [companies, setCompanies] = useState<
    Array<{ id: string; name: string; synthetic: boolean }>
  >([]);
  const [companyRoles, setCompanyRoles] = useState<
    Array<{ id: string; name: string }>
  >([]);
  const [companyId, setCompanyId] = useState("");
  const [companyRoleId, setCompanyRoleId] = useState("");
  const [preparation, setPreparation] = useState<CompanyPreparation | null>(
    null,
  );
  const [interview, setInterview] = useState<Interview | null>(null);
  const [answer, setAnswer] = useState("");
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    Promise.all([
      getProfile(token),
      getRoles(controller.signal),
      getSkills(controller.signal),
      getResumes(token),
    ]).then(
      ([student, rolePage, skillPage, resumeList]) => {
        if (controller.signal.aborted) return;
        setProfile(student);
        setRoles(rolePage.items);
        setSkills(skillPage.items);
        setResumes(resumeList);
        const active = resumeList.find((item) => item.active);
        if (active)
          getEvidence(token, active.resume_id).then(setEvidence, () =>
            setError("Evidence could not be loaded."),
          );
      },
      (failure: unknown) =>
        !controller.signal.aborted && setError(errorMessage(failure)),
    );
    getCompanies(token).then(
      (values) => !controller.signal.aborted && setCompanies(values),
      () => !controller.signal.aborted && setCompanies([]),
    );
    return () => controller.abort();
  }, [token]);

  const submitAuth = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    const body: Record<string, string> = {
      email: String(data.get("email")),
      password: String(data.get("password")),
    };
    if (mode === "register")
      body.display_name = String(data.get("display_name"));
    try {
      setToken(await authenticate(mode, body));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  if (!token)
    return (
      <section className="student-panel" aria-labelledby="student-title">
        <p className="eyebrow">PRIVATE STUDENT EVIDENCE</p>
        <h2 id="student-title">Your evidence workspace</h2>
        <p>
          Resume evidence stays private and remains unconfirmed until you review
          it.
        </p>
        <form onSubmit={submitAuth} className="student-form">
          {mode === "register" && (
            <label>
              Display name
              <input name="display_name" required maxLength={80} />
            </label>
          )}
          <label>
            Email
            <input name="email" type="email" required />
          </label>
          <label>
            Password
            <input name="password" type="password" minLength={12} required />
          </label>
          <button disabled={busy}>
            {mode === "register" ? "Create private workspace" : "Sign in"}
          </button>
        </form>
        <button
          className="text-button"
          onClick={() => setMode(mode === "register" ? "token" : "register")}
        >
          {mode === "register"
            ? "Already registered? Sign in"
            : "Create an account"}
        </button>
        {error && <p role="alert">{error}</p>}
      </section>
    );

  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get("resume");
    if (!(file instanceof File) || file.size === 0) return;
    setBusy(true);
    setError("");
    try {
      const value = await uploadResume(token, file);
      const list = await getResumes(token);
      setResumes(list);
      setEvidence(await getEvidence(token, value.resume_id));
      setGap(null);
      setRoadmap(null);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const decide = async (
    item: Evidence,
    action: "CONFIRM" | "REJECT",
    corrected?: string,
  ) => {
    setBusy(true);
    try {
      const value = await decideEvidence(
        token,
        item.evidence_id,
        action,
        corrected,
      );
      setEvidence((current) =>
        current.map((entry) =>
          entry.evidence_id === value.evidence_id ? value : entry,
        ),
      );
      setGap(null);
      setRoadmap(null);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const selectRole = async (roleId: string) => {
    try {
      setProfile(await updateProfile(token, { target_role_id: roleId }));
      setGap(null);
      setRoadmap(null);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  };
  const analyze = async () => {
    setBusy(true);
    try {
      setGap(await runGap(token));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const retrieve = async (skillId: string) => {
    if (!gap) return;
    setBusy(true);
    setError("");
    try {
      setRetrieval(await retrieveGapEvidence(token, gap.run_id, skillId));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const createRoadmap = async () => {
    if (!gap) return;
    setBusy(true);
    setError("");
    try {
      setRoadmap(await generateRoadmap(token, gap.run_id));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const selectCompany = async (id: string) => {
    setCompanyId(id);
    setCompanyRoleId("");
    setPreparation(null);
    setInterview(null);
    try {
      setCompanyRoles(id ? await getCompanyRoles(token, id) : []);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  };
  const prepareForCompany = async () => {
    if (!gap || !companyRoleId) return;
    setBusy(true);
    setError("");
    try {
      setPreparation(
        await generateCompanyPreparation(token, companyRoleId, gap.run_id),
      );
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const beginInterview = async () => {
    if (!companyRoleId) return;
    setBusy(true);
    setError("");
    try {
      setInterview(await startInterview(token, companyRoleId));
      setAnswer("");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const currentQuestion = interview?.questions.find(
    (question) =>
      !interview.responses.some(
        (response) => response.question_id === question.question_id,
      ),
  );
  const submitAnswer = async () => {
    if (!interview || !currentQuestion || !answer.trim()) return;
    setBusy(true);
    setError("");
    try {
      setInterview(
        await submitInterviewAnswer(
          token,
          interview.session_id,
          currentQuestion.question_id,
          answer.trim(),
        ),
      );
      setAnswer("");
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const finishInterview = async () => {
    if (!interview) return;
    setBusy(true);
    try {
      setInterview(await completeInterview(token, interview.session_id));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const assessReadiness = async () => {
    if (!gap) return;
    setBusy(true);
    try {
      setReadiness(await calculateReadiness(token, gap.run_id));
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="student-panel" aria-labelledby="student-title">
      <div className="student-heading">
        <div>
          <p className="eyebrow">PRIVATE STUDENT EVIDENCE</p>
          <h2 id="student-title">
            {profile?.display_name ?? "Your workspace"}
          </h2>
        </div>
        <button onClick={() => setToken("")}>Sign out</button>
      </div>
      <p className="privacy-note">
        CareerPilot records evidence, not proficiency. Extracted mentions
        require your confirmation.
      </p>
      <form onSubmit={upload} className="upload-row">
        <label>
          PDF or DOCX resume
          <input
            name="resume"
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            required
          />
        </label>
        <button disabled={busy}>Upload and process</button>
      </form>
      {resumes.length > 0 && (
        <p className="version-note">
          Active resume version:{" "}
          {resumes.find((item) => item.active)?.version ?? "none"} ·{" "}
          {resumes.length} preserved version(s)
        </p>
      )}
      {evidence.length > 0 && (
        <div className="review">
          <h3>Review detected evidence</h3>
          <ul>
            {evidence.map((item) => (
              <li key={item.evidence_id}>
                <div>
                  <strong>{item.skill_name ?? item.raw_text}</strong>
                  <small>
                    {item.section} · {item.normalization_status} ·{" "}
                    {item.verification_status}
                  </small>
                  <p>{item.evidence_text}</p>
                </div>
                <div className="review-actions">
                  <button
                    disabled={busy}
                    onClick={() => decide(item, "CONFIRM")}
                  >
                    Confirm
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => decide(item, "REJECT")}
                  >
                    Reject
                  </button>
                  {!item.skill_id && (
                    <select
                      aria-label={`Correct ${item.raw_text}`}
                      defaultValue=""
                      onChange={(event) =>
                        event.target.value &&
                        decide(item, "CONFIRM", event.target.value)
                      }
                    >
                      <option value="">Correct to canonical skill…</option>
                      {skills.map((skill) => (
                        <option key={skill.id} value={skill.id}>
                          {skill.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="target-row">
        <label>
          Canonical target role
          <select
            value={profile?.target_role_id ?? ""}
            onChange={(event) => selectRole(event.target.value)}
          >
            <option value="">Select a role…</option>
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.name}
              </option>
            ))}
          </select>
        </label>
        <button disabled={busy || !profile?.target_role_id} onClick={analyze}>
          Run evidence gap analysis
        </button>
      </div>
      {gap && (
        <div className="gap-results">
          <h3>Evidence against this role</h3>
          <p>
            {gap.rule_version} · {gap.knowledge_dataset_version}
          </p>
          <ul>
            {gap.items.map((item) => (
              <li key={item.skill_id}>
                <strong>{item.skill_name}</strong>
                <span>{item.importance}</span>
                <b className={item.status.toLowerCase()}>
                  {item.status.replace("_", " ")}
                </b>
                <small>
                  {item.status === "UNVERIFIED"
                    ? "CareerPilot does not currently have direct evidence for this skill."
                    : item.status === "SUPPORTED"
                      ? "Supported by confirmed direct evidence."
                      : "Direct evidence exists but is not confirmed."}
                </small>
                <button disabled={busy} onClick={() => retrieve(item.skill_id)}>
                  Retrieve evidence
                </button>
              </li>
            ))}
          </ul>
          <button disabled={busy} onClick={createRoadmap}>
            Generate grounded learning roadmap
          </button>
        </div>
      )}
      {roadmap && (
        <div className="roadmap-results" aria-live="polite">
          <p className="eyebrow">PERSONALIZED LEARNING ROADMAP</p>
          <h3>Validated evidence, generated recommendations</h3>
          <p className="roadmap-meta">
            Version {roadmap.version} · {roadmap.prompt_version} · evidence
            bundle {roadmap.evidence_bundle_version}
          </p>
          {roadmap.coverage_status === "PARTIAL" && (
            <p className="roadmap-coverage" role="status">
              Partial coverage: no recommendation was generated for{" "}
              {roadmap.omitted_skill_ids.join(", ")} because the current corpus
              did not supply enough validated learning evidence.
            </p>
          )}
          <ol>
            {roadmap.items.map((item) => {
              const evidence = roadmap.evidence.filter(
                (entry) =>
                  entry.skill_id === item.skill_id &&
                  item.evidence_ids.includes(entry.evidence_id),
              );
              const requirement = evidence.find(
                (entry) => entry.evidence_type === "ROLE_REQUIREMENT",
              );
              const studentStatus = evidence.find(
                (entry) => entry.evidence_type === "STUDENT_STATUS",
              );
              const resources = evidence.filter(
                (entry) => entry.evidence_type === "RESOURCE",
              );
              return (
                <li key={item.item_id}>
                  <div className="roadmap-item-heading">
                    <h4>
                      {item.sequence}. {item.skill_name}
                    </h4>
                    <span
                      className={`roadmap-priority ${item.priority.toLowerCase()}`}
                    >
                      {item.priority}
                    </span>
                  </div>
                  <dl>
                    <div>
                      <dt>Requirement · graph fact</dt>
                      <dd>{requirement?.label}</dd>
                    </div>
                    <div>
                      <dt>Student status · evidence analysis</dt>
                      <dd>{studentStatus?.label}</dd>
                    </div>
                    <div>
                      <dt>CareerPilot recommendation · generated synthesis</dt>
                      <dd>{item.recommendation}</dd>
                    </div>
                  </dl>
                  <h5>Suggested activities</h5>
                  <ul>
                    {item.suggested_activities.map((activity) => (
                      <li key={activity}>{activity}</li>
                    ))}
                  </ul>
                  <h5>Supporting resources · retrieval evidence</h5>
                  {resources.map((resource) => (
                    <p className="roadmap-resource" key={resource.evidence_id}>
                      <strong>
                        {resource.resource_name ?? resource.resource_id}
                      </strong>
                      <span>{resource.text}</span>
                      <small>Source: {resource.source_id}</small>
                    </p>
                  ))}
                </li>
              );
            })}
          </ol>
          <small>
            Generated synthesis is separate from graph facts, student evidence,
            and retrieved resources. Hidden model reasoning is never displayed.
          </small>
        </div>
      )}
      {gap && (
        <section
          className="specialist-workflows"
          aria-labelledby="specialist-title"
        >
          <p className="eyebrow">SPECIALIST WORKFLOWS</p>
          <h3 id="specialist-title">Prepare, practice, then reassess</h3>
          <div className="company-picker">
            <label>
              Canonical company
              <select
                value={companyId}
                onChange={(event) => selectCompany(event.target.value)}
              >
                <option value="">Select a company…</option>
                {companies.map((company) => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                    {company.synthetic ? " · synthetic" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Company role
              <select
                value={companyRoleId}
                onChange={(event) => setCompanyRoleId(event.target.value)}
              >
                <option value="">Select a company role…</option>
                {companyRoles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
            </label>
            <button
              disabled={busy || !companyRoleId}
              onClick={prepareForCompany}
            >
              Prepare for company
            </button>
            <button disabled={busy || !companyRoleId} onClick={beginInterview}>
              Start text mock interview
            </button>
          </div>
        </section>
      )}
      {preparation && (
        <section className="company-preparation" aria-live="polite">
          <p className="eyebrow">COMPANY PREPARATION</p>
          <h3>{preparation.company_role_name}</h3>
          <p className="scope-warning" role="status">
            {preparation.limitation}
          </p>
          <h4>Validated graph facts</h4>
          <ul>
            {preparation.facts.map((fact) => (
              <li key={fact.assertion_id}>
                {fact.label}
                <small>Source: {fact.source_ids.join(", ")}</small>
              </li>
            ))}
          </ul>
          <h4>CareerPilot generated synthesis</h4>
          <ol>
            {preparation.items.map((item) => (
              <li key={item.skill_id}>
                <strong>
                  {item.skill_name} · {item.importance}
                </strong>
                <span className="status-chip">
                  {item.student_status.replace("_", " ")}
                </span>
                <p>{item.recommendation}</p>
                <ul>
                  {item.activities.map((activity) => (
                    <li key={activity}>{activity}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </section>
      )}
      {interview && (
        <section className="mock-interview" aria-live="polite">
          <p className="eyebrow">TEXT MOCK INTERVIEW</p>
          <h3>{interview.company_role_name}</h3>
          <p>
            {interview.interview_type.replace("_", " ")} ·{" "}
            {interview.difficulty} · {interview.responses.length}/
            {interview.questions.length} answered
          </p>
          {currentQuestion ? (
            <div className="interview-question">
              <small>
                Question {currentQuestion.sequence} ·{" "}
                {currentQuestion.topic_name}
              </small>
              <h4>{currentQuestion.text}</h4>
              <label>
                Your answer
                <textarea
                  rows={7}
                  maxLength={8000}
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                />
              </label>
              <button disabled={busy || !answer.trim()} onClick={submitAnswer}>
                Submit answer for structured feedback
              </button>
            </div>
          ) : interview.status === "ACTIVE" ? (
            <button disabled={busy} onClick={finishInterview}>
              Complete interview
            </button>
          ) : (
            <p className="success-note">
              Interview completed. Practice evidence remains unconfirmed
              evidence, not mastery.
            </p>
          )}
          {interview.evaluations
            .filter((item) => item.status === "COMPLETED")
            .map((evaluation) => {
              const question = interview.questions.find(
                (item) => item.question_id === evaluation.question_id,
              );
              const response = interview.responses.find(
                (item) => item.question_id === evaluation.question_id,
              );
              return (
                <article
                  className="interview-feedback"
                  key={evaluation.evaluation_id}
                >
                  <h4>{question?.text}</h4>
                  <blockquote>{response?.answer}</blockquote>
                  <dl>
                    {evaluation.dimensions.map((dimension) => (
                      <div key={dimension.dimension}>
                        <dt>
                          {dimension.dimension.replaceAll("_", " ")} ·{" "}
                          {dimension.rating}
                        </dt>
                        <dd>{dimension.feedback}</dd>
                      </div>
                    ))}
                  </dl>
                  <small>
                    {evaluation.practice_evidence_ids.length
                      ? "Practice evidence recorded with session, question, and evaluation provenance."
                      : "No practice evidence was created from this response."}
                  </small>
                </article>
              );
            })}
        </section>
      )}
      {gap && (
        <section className="readiness-panel">
          <p className="eyebrow">PREPARATION READINESS</p>
          <h3>Evidence-backed, not a placement prediction</h3>
          <button disabled={busy} onClick={assessReadiness}>
            Calculate readiness snapshot
          </button>
          {readiness && (
            <div className="readiness-result" aria-live="polite">
              <div className="readiness-score">
                <strong>{readiness.score}</strong>
                <span>/ 100 · {readiness.category}</span>
              </div>
              <p>{readiness.limitation}</p>
              <dl>
                {readiness.components.map((component) => (
                  <div key={component.component}>
                    <dt>
                      {component.component.replaceAll("_", " ")}{" "}
                      <b>{component.score}</b>
                    </dt>
                    <dd>
                      {component.explanation} Weight: {component.weight}%.
                    </dd>
                  </div>
                ))}
              </dl>
              <small>
                {readiness.rule_version} · immutable snapshot version{" "}
                {readiness.version}
              </small>
            </div>
          )}
        </section>
      )}
      {retrieval && (
        <div className="retrieval-results" aria-live="polite">
          <h3>Retrieval inspection</h3>
          <p>
            {retrieval.retrieval_strategy} · {retrieval.sufficiency.status} ·
            trace {retrieval.trace_id}
          </p>
          <section>
            <h4>Why this skill matters — graph evidence</h4>
            {retrieval.graph_evidence.length ? (
              <ul>
                {retrieval.graph_evidence.map((item) => (
                  <li key={item.assertion_id}>
                    {item.relationship_type} → {item.entity_name} (
                    {item.importance})
                    <small>Source: {item.source_ids.join(", ")}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No validated graph relationship available.</p>
            )}
          </section>
          <section>
            <h4>Learning evidence — resource passages</h4>
            {retrieval.vector_evidence.length ? (
              <ul>
                {retrieval.vector_evidence.map((item) => (
                  <li key={item.chunk_id}>
                    <strong>
                      {String(item.metadata.resource_name ?? item.resource_id)}
                    </strong>
                    <p>{item.text}</p>
                    <small>
                      Source: {item.source_id} · cosine{" "}
                      {item.similarity_score.toFixed(3)}
                    </small>
                  </li>
                ))}
              </ul>
            ) : (
              <p>No validated resource available.</p>
            )}
          </section>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
