import { useEffect, useState } from "react";
import { Link } from "react-router";

import { getResearchHistory, researchErrorMessage } from "../lib/researchApi";
import { STATUS_LABELS } from "../lib/research";
import type { ResearchHistory } from "../lib/research";

type HistoryState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: ResearchHistory };

function HistoryResults({
  cursor,
  onNext,
}: {
  cursor: string | null;
  onNext: (cursor: string) => void;
}) {
  const [state, setState] = useState<HistoryState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    void getResearchHistory(cursor, controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) {
          setState({ kind: "ready", data });
        }
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({
            kind: "error",
            message: researchErrorMessage(error),
          });
        }
      });

    return () => controller.abort();
  }, [cursor, attempt]);

  function refresh() {
    setState({ kind: "loading" });
    setAttempt((value) => value + 1);
  }

  if (state.kind === "loading") {
    return <p className="card" role="status">Loading research history...</p>;
  }

  if (state.kind === "error") {
    return (
      <section className="card page-stack">
        <p role="alert">{state.message}</p>
        <button
          className="button button-secondary"
          type="button"
          onClick={refresh}
        >
          Retry history
        </button>
      </section>
    );
  }

  const { items, next_cursor } = state.data;

  return (
    <section className="card page-stack" aria-label="Saved research">
      <div className="section-heading">
        <h2>Saved research tasks</h2>
        <button
          className="button button-secondary"
          type="button"
          onClick={refresh}
        >
          Refresh history
        </button>
      </div>

      {items.length === 0 ? (
        <div className="empty-state">
          <h3>No research history yet</h3>
          <p>No saved research tasks were returned for this page.</p>
          <Link className="button button-primary" to="/research/new">
            New research
          </Link>
        </div>
      ) : (
        <ul className="research-list">
          {items.map((task) => (
            <li key={task.id} className="research-list-item">
              <div>
                <Link to={`/research/tasks/${task.id}`}>
                  {task.question}
                </Link>
                <p className="muted">
                  Created: {new Date(task.created_at).toLocaleString()}
                </p>
              </div>
              <span className="badge">
                {STATUS_LABELS[task.status]}
              </span>
            </li>
          ))}
        </ul>
      )}

      {next_cursor !== null && (
        <button
          className="button button-secondary"
          type="button"
          onClick={() => onNext(next_cursor)}
        >
          Next page
        </button>
      )}
    </section>
  );
}

export default function ResearchHistoryPage() {
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const cursor = cursors[cursors.length - 1] ?? null;

  return (
    <div className="page-stack">
      <section className="page-heading">
        <p className="eyebrow">Your research library</p>
        <h1>Research history</h1>
        <p className="lead">Review your saved research tasks.</p>
      </section>

      <div className="section-heading">
        <Link className="button button-primary" to="/research/new">
          New research
        </Link>
        <span>Page {cursors.length}</span>

        {cursors.length > 1 && (
          <button
            className="button button-secondary"
            type="button"
            onClick={() => setCursors((items) => items.slice(0, -1))}
          >
            Previous page
          </button>
        )}
      </div>

      <HistoryResults
        key={cursor ?? "first"}
        cursor={cursor}
        onNext={(next) => setCursors((items) => [...items, next])}
      />
    </div>
  );
}
