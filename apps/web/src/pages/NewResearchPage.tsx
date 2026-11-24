import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { createResearch, researchErrorMessage } from "../lib/researchApi";
import type { ResearchInput } from "../lib/research";

const QUESTION_LIMIT = 4000;
const SCOPE_LIMIT = 2000;

export default function NewResearchPage() {
  const navigate = useNavigate();

  const [question, setQuestion] = useState("");
  const [geography, setGeography] = useState("");
  const [category, setCategory] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [timeScope, setTimeScope] = useState("");
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inFlight = useRef<AbortController | null>(null);
  const previous = useRef<{
    payload: string;
    key: string;
  } | null>(null);

  useEffect(() => {
    return () => inFlight.current?.abort();
  }, []);

  const input: ResearchInput = {
    question,
    scope: {
      geography: geography || null,
      category: category || null,
      time_scope: timeScope || null,
      competitors: competitors
        .split("\n")
        .filter((value) => value.trim().length > 0),
    },
  };

  const scopeJson = `{${Object.entries(input.scope)
    .map(([name, value]) => {
      const serialized = Array.isArray(value)
        ? `[${value.map((item) => JSON.stringify(item)).join(", ")}]`
        : JSON.stringify(value);
      return `${JSON.stringify(name)}: ${serialized}`;
    })
    .join(", ")}}`;

  const scopeLength = Array.from(scopeJson).length;

  const invalidQuestion =
    !question.trim()
    || question.length > QUESTION_LIMIT
    || question.includes("\0");

  const invalidScope =
    scopeLength > SCOPE_LIMIT
    || [geography, category, competitors, timeScope]
      .some((value) => value.includes("\0"));

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTouched(true);

    if (invalidQuestion || invalidScope || inFlight.current) return;

    const payload = JSON.stringify(input);

    if (previous.current?.payload !== payload) {
      previous.current = {
        payload,
        key: globalThis.crypto.randomUUID(),
      };
    }

    const controller = new AbortController();
    inFlight.current = controller;
    setBusy(true);
    setError(null);

    try {
      const result = await createResearch(
        input,
        previous.current.key,
        controller.signal,
      );

      if (!controller.signal.aborted) {
        navigate(`/research/tasks/${result.task_id}`);
      }
    } catch (failure: unknown) {
      if (!controller.signal.aborted) {
        setError(researchErrorMessage(failure));
      }
    } finally {
      inFlight.current = null;

      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <p className="eyebrow">Research setup</p>
        <h1>New research</h1>
        <p className="lead">Start with the question that matters.</p>
        <p className="muted">
          Submit a question to the research queue.
        </p>
      </section>

      <aside className="notice">
        <h2>Research execution is not connected yet.</h2>
        <p>
          Accepted tasks are saved in PostgreSQL and remain queued
          until the research worker is implemented.
          No AI report will be generated in this sprint.
        </p>
      </aside>

      <form
        className="card research-form"
        aria-label="Research question"
        onSubmit={handleSubmit}
        noValidate
      >
        <div className="field">
          <label htmlFor="research-question">
            Research question (required)
          </label>

          <textarea
            id="research-question"
            rows={6}
            required
            maxLength={QUESTION_LIMIT}
            value={question}
            disabled={busy}
            onChange={(event) => setQuestion(event.target.value)}
            onBlur={() => setTouched(true)}
            aria-invalid={touched && invalidQuestion}
            aria-describedby="question-count question-error"
          />

          <p className="character-count" id="question-count">
            {question.length.toLocaleString("en-US")} / 4,000 characters
          </p>

          <div id="question-error">
            {touched && invalidQuestion && (
              <p className="field-error" role="alert">
                Enter a research question.
              </p>
            )}
          </div>
        </div>

        <fieldset className="scope-fields" disabled={busy}>
          <legend>Research scope (optional)</legend>

          <div className="field">
            <label htmlFor="geography">Geography</label>
            <input
              id="geography"
              maxLength={SCOPE_LIMIT}
              value={geography}
              onChange={(event) => setGeography(event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="category">Category</label>
            <input
              id="category"
              maxLength={SCOPE_LIMIT}
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="time-scope">Time scope</label>
            <input
              id="time-scope"
              maxLength={SCOPE_LIMIT}
              value={timeScope}
              onChange={(event) => setTimeScope(event.target.value)}
            />
          </div>

          <div className="field">
            <label htmlFor="competitors">
              Competitors (one per line)
            </label>
            <textarea
              id="competitors"
              rows={3}
              maxLength={SCOPE_LIMIT}
              value={competitors}
              onChange={(event) => setCompetitors(event.target.value)}
            />
          </div>
        </fieldset>

        <p className="muted">
          Scope limit: 2,000 serialized characters, including field names.
        </p>

        {invalidScope && (
          <p role="alert" className="field-error">
            Research scope exceeds the allowed limit or contains invalid input.
          </p>
        )}

        {error && (
          <div className="notice" role="alert">
            <p>{error}</p>
            <p>
              If submission was interrupted, retry with unchanged input
              or check <Link to="/research/history">research history</Link>.
              Changing the input may create a new task.
            </p>
          </div>
        )}

        <div className="form-footer">
          <p className="muted" role="status">
            {busy
              ? "Submitting research..."
              : "Submission requires an authenticated review session."}
          </p>

          <button
            className="button button-primary"
            type="submit"
            disabled={busy || invalidScope}
          >
            {busy
              ? "Submitting..."
              : error
                ? "Retry submission"
                : "Submit research"}
          </button>
        </div>
      </form>
    </div>
  );
}
