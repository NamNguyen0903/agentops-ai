import { Link } from "react-router";

export default function NotFoundPage() {
  return (
    <section className="card empty-state">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p>The page may have moved, or the address may be incorrect.</p>
      <Link className="button button-primary" to="/">
        Back to dashboard
      </Link>
    </section>
  );
}
