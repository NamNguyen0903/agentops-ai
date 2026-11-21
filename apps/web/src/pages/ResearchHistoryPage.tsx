
import { Link } from "react-router";

export default function ResearchHistoryPage() {
  return (
    <div className="page-stack">
      <section className="page-heading">
        <p className="eyebrow">
          Your research library
        </p>

        <h1>Research history</h1>

        <p className="lead">
          A place to return to your findings.
        </p>

        <p className="muted">
          Backend history integration is planned.
          This page does not fetch or display
          saved research yet.
        </p>
      </section>

      <section
        className="card empty-state"
        aria-labelledby="empty-history"
      >
        <span
          className="empty-symbol"
          aria-hidden="true"
        >
          ≡
        </span>

        <h2 id="empty-history">
          No research history yet
        </h2>

        <p>
          No research records are loaded in this
          frontend preview. You can explore the
          question form while backend integration
          is being built.
        </p>

        <Link
          className="button button-primary"
          to="/research/new"
        >
          New research
        </Link>
      </section>
    </div>
  );
}
