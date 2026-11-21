
import { useState } from "react";
import type { FormEvent } from "react";

const QUESTION_LIMIT = 4000;
const SCOPE_LIMIT = 2000;

export default function NewResearchPage() {
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState("");
  const [questionTouched, setQuestionTouched] =
    useState(false);

  const questionError =
    questionTouched && question.trim().length === 0
      ? "Enter a research question."
      : null;

  function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ): void {
    event.preventDefault();
    setQuestionTouched(true);

    // Research task submission is not implemented yet.
    // Do not call an unavailable backend endpoint.
  }

  return (
    <div className="page-stack">
      <section className="page-heading">
        <p className="eyebrow">Research setup</p>

        <h1>New research</h1>

        <p className="lead">
          Start with the question that matters.
        </p>

        <p className="muted">
          Prepare a focused question and add context
          to guide future research.
        </p>
      </section>

      <aside
        className="notice"
        aria-labelledby="availability-heading"
      >
        <h2 id="availability-heading">
          Submission is not available yet
        </h2>

        <p id="submission-unavailable">
          Research submission is disabled until
          the backend task API is implemented.
          Nothing entered here is sent or saved.
          Leaving this page clears the form.
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
            Research question{" "}
            <span className="required-label">
              (required)
            </span>
          </label>

          <p
            className="field-help"
            id="question-help"
          >
            Ask about competitors, products, or
            market trends. Include the comparison
            or decision you want to explore.
          </p>

          <textarea
            id="research-question"
            name="question"
            rows={6}
            required
            maxLength={QUESTION_LIMIT}
            value={question}
            onChange={(event) => {
              setQuestion(event.target.value);
            }}
            onBlur={() => {
              setQuestionTouched(true);
            }}
            aria-invalid={Boolean(questionError)}
            aria-describedby={[
              "question-help",
              "question-count",
              questionError
                ? "question-error"
                : "",
            ]
              .filter(Boolean)
              .join(" ")}
            placeholder="What differentiates these products for mid-sized teams?"
          />

          <p
            className="character-count"
            id="question-count"
          >
            {question.length.toLocaleString("en-US")}{" "}
            / 4,000 characters
          </p>

          {questionError && (
            <p
              className="field-error"
              id="question-error"
              role="alert"
            >
              {questionError}
            </p>
          )}
        </div>

        <div className="field">
          <label htmlFor="research-scope">
            Research scope{" "}
            <span className="optional-label">
              (optional)
            </span>
          </label>

          <p
            className="field-help"
            id="scope-help"
          >
            Add competitors, geography, product
            category, or a time period.
          </p>

          <textarea
            id="research-scope"
            name="scope"
            rows={4}
            maxLength={SCOPE_LIMIT}
            value={scope}
            onChange={(event) => {
              setScope(event.target.value);
            }}
            aria-describedby="scope-help scope-count"
            placeholder="For example: European market, public sources, last 12 months."
          />

          <p
            className="character-count"
            id="scope-count"
          >
            {scope.length.toLocaleString("en-US")}{" "}
            / 2,000 characters
          </p>
        </div>

        <div className="form-footer">
          <p className="muted">
            Draft fields only. No research task
            will be created.
          </p>

          <button
            className="button button-primary"
            type="submit"
            disabled
            aria-describedby="submission-unavailable"
          >
            Submit research — unavailable
          </button>
        </div>
      </form>
    </div>
  );
}
