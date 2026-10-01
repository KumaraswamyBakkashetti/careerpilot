import { useEffect, useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { getRoles, getSkills, type Entity } from "../api/knowledge";
import {
  authenticate,
  decideEvidence,
  getEvidence,
  getProfile,
  getResumes,
  runGap,
  updateProfile,
  uploadResume,
  type Evidence,
  type GapRun,
  type Profile,
  type Resume,
} from "../api/student";

const errorMessage = (error: unknown) =>
  error instanceof ApiError
    ? error.code === "DEPENDENCY_UNAVAILABLE"
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
              </li>
            ))}
          </ul>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
