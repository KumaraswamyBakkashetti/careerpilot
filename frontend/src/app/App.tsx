import { useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getHealth, type FoundationHealth } from "../api/health";

type State =
  | { kind: "loading" }
  | { kind: "loaded"; health: FoundationHealth; checkedAt: string }
  | { kind: "error"; message: string; requestId?: string };

export function App() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal).then(
      (health) => {
        if (!controller.signal.aborted)
          setState({
            kind: "loaded",
            health,
            checkedAt: new Date().toLocaleTimeString(),
          });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            kind: "error",
            message:
              error instanceof ApiError
                ? error.message
                : "Unable to check system health.",
            requestId: error instanceof ApiError ? error.requestId : undefined,
          });
        }
      },
    );
    return () => controller.abort();
  }, [attempt]);

  const loaded = state.kind === "loaded";
  const backend = loaded
    ? "Available"
    : state.kind === "loading"
      ? "Checking"
      : "Unavailable";
  const databaseLabel = (name: "mongodb" | "neo4j") =>
    loaded
      ? state.health.dependencies[name] === "up"
        ? "Available"
        : "Unavailable"
      : state.kind === "loading"
        ? "Checking"
        : "Unknown";
  const rows = [
    { name: "FastAPI backend", detail: "Application process", status: backend },
    {
      name: "MongoDB",
      detail: "Student & application state",
      status: databaseLabel("mongodb"),
    },
    {
      name: "Neo4j",
      detail: "Canonical career knowledge",
      status: databaseLabel("neo4j"),
    },
  ];

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/">
          CareerPilot
          <span className="brand-dot" aria-hidden="true" />
        </a>
        <span className="phase-tag">PHASE 01</span>
      </header>
      <main>
        <p className="eyebrow">ENGINEERING FOUNDATION</p>
        <h1>
          A dependable start.
          <br />
          <span>Room to grow.</span>
        </h1>
        <p className="intro">
          A Multi-Agent Placement Intelligence System Using Knowledge
          Graph-Enhanced Agentic RAG
        </p>
        <section
          className="status-panel"
          aria-labelledby="status-title"
          aria-busy={state.kind === "loading"}
        >
          <div className="panel-header">
            <div>
              <p className="eyebrow">SYSTEM STATUS</p>
              <h2 id="status-title">Foundation connectivity</h2>
            </div>
            <button
              disabled={state.kind === "loading"}
              onClick={() => {
                setState({ kind: "loading" });
                setAttempt((value) => value + 1);
              }}
            >
              Refresh status <span aria-hidden="true">↗</span>
            </button>
          </div>
          <div className="health-message" role="status" aria-live="polite">
            {state.kind === "loading"
              ? "Checking the backend and its dependencies…"
              : state.kind === "error"
                ? state.message
                : state.health.status === "ready"
                  ? "All foundation services are available."
                  : "The backend is alive. Required databases are unavailable; the system is not ready."}
          </div>
          <ul className="service-list">
            {rows.map((row) => (
              <li key={row.name}>
                <div>
                  <h3>{row.name}</h3>
                  <p>{row.detail}</p>
                </div>
                <span className={`service-state ${row.status.toLowerCase()}`}>
                  <span aria-hidden="true" className="state-dot" />
                  {row.status}
                </span>
              </li>
            ))}
          </ul>
          <div className="panel-footer">
            <span>
              {loaded
                ? `Checked at ${state.checkedAt}`
                : "Live checks · No simulated connectivity"}
            </span>
            {(loaded
              ? state.health.requestId
              : state.kind === "error"
                ? state.requestId
                : null) && (
              <code>
                Request:{" "}
                {loaded
                  ? state.health.requestId
                  : state.kind === "error"
                    ? state.requestId
                    : ""}
              </code>
            )}
          </div>
        </section>
        <aside className="scope-note">
          <span aria-hidden="true">01 /</span>
          <p>
            Phase 1 establishes the engineering platform. Resume intelligence,
            knowledge ingestion, retrieval, and agent workflows belong to later
            phases.
          </p>
        </aside>
      </main>
      <footer>
        CareerPilot <span>Modular monolith · React + FastAPI</span>
      </footer>
    </div>
  );
}
