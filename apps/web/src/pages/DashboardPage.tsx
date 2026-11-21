import { Link } from "react-router";

export default function DashboardPage() {
  return (
    <div className="page-stack">
      <section className="page-heading">
        <p className="eyebrow">Your research workspace</p>
        <h1>Dashboard</h1>
        <p className="lead">
          Turn market questions into research you can inspect.
        </p>
        <p className="muted">
          AgentOps AI is being built to organize competitor and market research
          around traceable evidence. This frontend preview lets you explore the
          workspace and prepare a question.
        </p>
      </section>

      <section className="card hero-card" aria-labelledby="start-heading">
        <div>
          <p className="eyebrow">Start with a clear question</p>
          <h2 id="start-heading">Define what you want to learn</h2>
          <p>
            Identify the competitors, products, geography, or time period that
            matter to your research.
          </p>
          <Link className="button button-primary" to="/research/new">
            New research
          </Link>
        </div>
        <div className="hero-note">
          <strong>Research execution is not connected yet.</strong>
          <p>
            Preparing a question does not submit a task or generate a report.
          </p>
        </div>
      </section>

      <section className="card" aria-labelledby="history-heading">
        <div className="section-heading">
          <h2 id="history-heading">Research activity</h2>
          <Link to="/research/history">View history</Link>
        </div>
        <div className="empty-state">
          <span className="empty-symbol" aria-hidden="true">
            ↗
          </span>
          <h3>No research history yet</h3>
          <p>
            No records are loaded in this preview. Saved research will appear
            after backend history integration is implemented.
          </p>
        </div>
      </section>

      <section aria-labelledby="workflow-heading">
        <h2 id="workflow-heading">The planned research workflow</h2>
        <ol className="workflow-grid">
          <li className="card">
            <h3>Frame the question</h3>
            <p>Set a focused objective and optional research scope.</p>
          </li>
          <li className="card">
            <h3>Gather evidence</h3>
            <p>
              Planned backend tools will collect sources through approved
              providers.
            </p>
          </li>
          <li className="card">
            <h3>Review findings</h3>
            <p>
              Planned reports will distinguish evidence, interpretation, and
              uncertainty.
            </p>
          </li>
        </ol>
      </section>
    </div>
  );
}