
import {
  useEffect,
  useRef,
  useState,
} from "react";

import type { KeyboardEvent } from "react";

import {
  Link,
  NavLink,
  Outlet,
  useLocation,
} from "react-router";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/research/new": "New research",
  "/research/history": "Research history",
};

export default function AppLayout() {
  const [navigationOpen, setNavigationOpen] =
    useState(false);

  const location = useLocation();

  const mainRef = useRef<HTMLElement>(null);

  const menuButtonRef =
    useRef<HTMLButtonElement>(null);

  const pageTitle =
    pageTitles[location.pathname] ??
    "Page not found";

  useEffect(() => {
    document.title = `${pageTitle} | AgentOps AI`;

    mainRef.current?.focus();
  }, [location.pathname, pageTitle]);

  function closeNavigation(): void {
    setNavigationOpen(false);
  }

  function handleSidebarKeyDown(
    event: KeyboardEvent<HTMLElement>,
  ): void {
    if (
      event.key !== "Escape" ||
      !navigationOpen
    ) {
      return;
    }

    event.preventDefault();

    closeNavigation();

    menuButtonRef.current?.focus();
  }

  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
      >
        Skip to content
      </a>

      <aside
        className="sidebar"
        onKeyDown={handleSidebarKeyDown}
      >
        <div className="sidebar-heading">
          <Link
            className="brand"
            to="/"
            aria-label="AgentOps AI dashboard"
            onClick={closeNavigation}
          >
            <span
              className="brand-mark"
              aria-hidden="true"
            >
              A
            </span>

            <span>
              <span className="brand-name">
                AgentOps AI
              </span>

              <span className="brand-caption">
                Research workspace
              </span>
            </span>
          </Link>

          <button
            ref={menuButtonRef}
            className={
              "menu-toggle button button-secondary"
            }
            type="button"
            aria-controls="primary-navigation"
            aria-expanded={navigationOpen}
            onClick={() => {
              setNavigationOpen((open) => !open);
            }}
          >
            {navigationOpen
              ? "Close menu"
              : "Open menu"}
          </button>
        </div>

        <nav
          id="primary-navigation"
          className={
            `navigation${
              navigationOpen ? " is-open" : ""
            }`
          }
          aria-label="Primary navigation"
        >
          <NavLink
            className="nav-link"
            to="/"
            end
            onClick={closeNavigation}
          >
            Dashboard
          </NavLink>

          <NavLink
            className="nav-link"
            to="/research/new"
            onClick={closeNavigation}
          >
            New research
          </NavLink>

          <NavLink
            className="nav-link"
            to="/research/history"
            onClick={closeNavigation}
          >
            Research history
          </NavLink>
        </nav>

        <p className="sidebar-note">
          Evidence-grounded research.
          <br />
          Built for analyst review.
        </p>
      </aside>

      <div className="workspace">
        <header className="workspace-header">
          <p className="breadcrumb">
            Workspace / {pageTitle}
          </p>

          <span className="badge">
            Frontend preview
          </span>
        </header>

        <main
          id="main-content"
          className="main-content"
          ref={mainRef}
          tabIndex={-1}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
