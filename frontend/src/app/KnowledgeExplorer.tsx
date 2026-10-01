import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import {
  getRoles,
  getRoleSkills,
  type Entity,
  type RelationsPage,
} from "../api/knowledge";

type RolesState =
  | { kind: "loading" }
  | { kind: "loaded"; roles: Entity[] }
  | { kind: "error"; message: string };
type SkillsState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; value: RelationsPage }
  | { kind: "missing" }
  | { kind: "error"; message: string };

const message = (error: unknown) => {
  if (error instanceof ApiError && error.status === 404)
    return "The selected role no longer exists.";
  if (error instanceof ApiError && error.code === "DEPENDENCY_UNAVAILABLE")
    return "Career knowledge is unavailable while Neo4j is offline.";
  return "Career knowledge could not be loaded.";
};

export function KnowledgeExplorer() {
  const [roles, setRoles] = useState<RolesState>({ kind: "loading" });
  const [selected, setSelected] = useState("");
  const [skills, setSkills] = useState<SkillsState>({ kind: "idle" });

  useEffect(() => {
    const controller = new AbortController();
    getRoles(controller.signal).then(
      (page) => {
        if (!controller.signal.aborted) {
          setRoles({ kind: "loaded", roles: page.items });
          setSelected(page.items[0]?.id ?? "");
          if (page.items.length) setSkills({ kind: "loading" });
        }
      },
      (error: unknown) => {
        if (!controller.signal.aborted)
          setRoles({ kind: "error", message: message(error) });
      },
    );
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!selected) {
      return;
    }
    const controller = new AbortController();
    getRoleSkills(selected, controller.signal).then(
      (value) =>
        !controller.signal.aborted && setSkills({ kind: "loaded", value }),
      (error: unknown) => {
        if (!controller.signal.aborted)
          setSkills(
            error instanceof ApiError && error.status === 404
              ? { kind: "missing" }
              : { kind: "error", message: message(error) },
          );
      },
    );
    return () => controller.abort();
  }, [selected]);

  return (
    <section className="knowledge-panel" aria-labelledby="knowledge-title">
      <p className="eyebrow">CANONICAL CAREER KNOWLEDGE</p>
      <h2 id="knowledge-title">Explore a learning profile</h2>
      <p className="knowledge-intro">
        Select a curated role profile to see its Neo4j-backed skills and the
        source trail for each mapping.
      </p>
      {roles.kind === "loading" && <p role="status">Loading career roles…</p>}
      {roles.kind === "error" && <p role="alert">{roles.message}</p>}
      {roles.kind === "loaded" && roles.roles.length === 0 && (
        <p className="empty">No curated role profiles are available.</p>
      )}
      {roles.kind === "loaded" && roles.roles.length > 0 && (
        <label>
          Role profile
          <select
            value={selected}
            onChange={(event) => {
              setSkills({ kind: "loading" });
              setSelected(event.target.value);
            }}
          >
            {roles.roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {skills.kind === "loading" && (
        <p role="status">Loading required skills…</p>
      )}
      {skills.kind === "missing" && (
        <p role="alert">The selected role no longer exists.</p>
      )}
      {skills.kind === "error" && <p role="alert">{skills.message}</p>}
      {skills.kind === "loaded" && skills.value.items.length === 0 && (
        <p className="empty">
          This profile has no curated skill relationships.
        </p>
      )}
      {skills.kind === "loaded" && skills.value.items.length > 0 && (
        <ul className="skill-list">
          {skills.value.items.map((item) => (
            <li key={item.evidence.assertion.id}>
              <div>
                <h3>{item.entity.name}</h3>
                <p>{item.entity.description}</p>
              </div>
              <div className="evidence">
                <span
                  className={`importance ${item.evidence.assertion.importance.toLowerCase()}`}
                >
                  {item.evidence.assertion.importance}
                </span>
                {item.evidence.provenance.map(({ source }) =>
                  source.uri.startsWith("https://") ? (
                    <a
                      key={source.uri}
                      href={source.uri}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Source: {source.title}
                    </a>
                  ) : (
                    <span key={source.uri}>Source: {source.title}</span>
                  ),
                )}
                <small>{item.evidence.dataset_version}</small>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
