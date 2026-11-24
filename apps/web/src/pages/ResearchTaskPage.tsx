import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import {
  getResearchTask,
  researchErrorMessage,
} from "../lib/researchApi";

import {
  isTerminal,
  isTaskId,
  STATUS_LABELS,
} from "../lib/research";

import type { ResearchTask } from "../lib/research";

export const POLL_INTERVAL_MS = 5000;

type TaskState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; task: ResearchTask };

function TaskDetail({ id }: { id: string }) {
  const [state, setState] = useState<TaskState>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function refresh() {
      try {
        const task = await getResearchTask(id, controller.signal);

        if (controller.signal.aborted) return;

        setState({ kind: "ready", task });

        if (!isTerminal(task.status)) {
          timer = globalThis.setTimeout(
            () => void refresh(),
            POLL_INTERVAL_MS,
          );
        }
      } catch (error: unknown) {
        if (!controller.signal.aborted) {
          setState({
            kind: "error",
            message: researchErrorMessage(error),
          });
        }
      }
    }

    void refresh();

    return () => {
      controller.abort();
      globalThis.clearTimeout(timer);
    };
  }, [id, attempt]);

  function retry() {
    setState({ kind: "loading" });
    setAttempt((value) => value + 1);
  }

  if (state.kind === "loading") {
    return <p role="status" className="card">Loading research task...</p>;
  }

  if (state.kind === "error") {
    return (
      <section className="card page-stack">
        <p role="alert">{state.message}</p>
        <button
          className="button button-secondary"
          type="button"
          onClick={retry}
        >
          Retry task status
        </button>
      </section>
    );
  }

  const { task } = state;

  return (
    <>
      <section className="card page-stack" aria-labelledby="task-question">
        <div className="section-heading">
          <h2 id="task-question">Research question</h2>
          <span className="badge" role="status">
            {STATUS_LABELS[task.status]}
          </span>
        </div>

        <p className="research-question">{task.question}</p>

        <dl className="task-metadata">
          <dt>Task ID</dt>
          <dd>{task.id}</dd>

          <dt>Current stage</dt>
          <dd>{task.current_stage ?? "Not started"}</dd>

          <dt>Created</dt>
          <dd>{new Date(task.created_at).toLocaleString()}</dd>

          <dt>Last updated</dt>
          <dd>{new Date(task.updated_at).toLocaleString()}</dd>

          <dt>Started</dt>
          <dd>
            {task.started_at
              ? new Date(task.started_at).toLocaleString()
              : "Not started"}
          </dd>

          <dt>Completed</dt>
          <dd>
            {task.completed_at
              ? new Date(task.completed_at).toLocaleString()
              : "Not completed"}
          </dd>

          {task.error_category && (
            <>
              <dt>Error category</dt>
              <dd>{task.error_category}</dd>
            </>
          )}
        </dl>
      </section>

      <section className="card">
        <h2>Research scope</h2>
        <dl className="task-metadata">
          <dt>Geography</dt>
          <dd>{task.scope.geography ?? "Not specified"}</dd>
          <dt>Category</dt>
          <dd>{task.scope.category ?? "Not specified"}</dd>
          <dt>Time scope</dt>
          <dd>{task.scope.time_scope ?? "Not specified"}</dd>
          <dt>Competitors</dt>
          <dd>{task.scope.competitors.join(", ") || "Not specified"}</dd>
        </dl>
      </section>

      <aside className="notice">
        <h2>Execution availability</h2>
        <p>
          S03 does not include a research worker or report generation.
          The status shown above comes from the backend.
        </p>

        <p>
          {isTerminal(task.status)
            ? "Automatic status polling has stopped."
            : "Checking saved task status every 5 seconds."}
        </p>
      </aside>
    </>
  );
}

export default function ResearchTaskPage() {
  const { taskId } = useParams();

  return (
    <div className="page-stack">
      <section className="page-heading">
        <p className="eyebrow">Research workspace</p>
        <h1>Research task</h1>
        <Link to="/research/history">Back to research history</Link>
      </section>

      {isTaskId(taskId)
        ? <TaskDetail key={taskId} id={taskId} />
        : <p role="alert">Invalid research task identifier.</p>}
    </div>
  );
}
