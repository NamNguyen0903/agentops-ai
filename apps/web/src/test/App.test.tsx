
import {
  render,
  screen,
  within,
} from "@testing-library/react";

import userEvent from "@testing-library/user-event";

import { MemoryRouter } from "react-router";

import {
  describe,
  expect,
  it,
} from "vitest";

import App from "../App";

function renderRoute(path: string = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("frontend routes", () => {
  it("renders the dashboard without network requests", () => {
    renderRoute();

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Dashboard",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", {
        name: "View your saved research",
      }),
    ).toBeInTheDocument();

    expect(fetch).not.toHaveBeenCalled();
  });

  it("navigates to New Research", async () => {
    const user = userEvent.setup();

    renderRoute();

    const navigation = screen.getByRole(
      "navigation",
      { name: "Primary navigation" },
    );

    const link = within(navigation).getByRole(
      "link",
      { name: "New research" },
    );

    await user.click(link);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "New research",
      }),
    ).toBeInTheDocument();

    expect(link).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("validates the research form", async () => {
    const user = userEvent.setup();

    renderRoute("/research/new");

    const question = screen.getByLabelText(
      /Research question \(required\)/,
    );

    const scope = screen.getByLabelText(
      /Geography/,
    );

    await user.click(question);
    await user.tab();

    expect(
      screen.getByRole("alert"),
    ).toHaveTextContent(
      "Enter a research question.",
    );

    expect(question).toHaveAttribute(
      "aria-invalid",
      "true",
    );

    await user.type(question, "   ");

    expect(
      screen.getByRole("alert"),
    ).toBeInTheDocument();

    await user.clear(question);

    await user.type(
      question,
      "Compare products",
    );

    await user.type(scope, "Europe");

    expect(question).toHaveValue(
      "Compare products",
    );

    expect(scope).toHaveValue("Europe");

    expect(question).toHaveAttribute(
      "aria-invalid",
      "false",
    );

    expect(
      screen.queryByRole("alert"),
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(
        "16 / 4,000 characters",
      ),
    ).toBeInTheDocument();

    expect(question).toHaveAttribute(
      "maxlength",
      "4000",
    );

    expect(scope).toHaveAttribute(
      "maxlength",
      "2000",
    );
  });

  it("does not submit a blank question", async () => {
    const user = userEvent.setup();

    renderRoute("/research/new");

    await user.click(
      screen.getByRole("button", { name: "Submit research" }),
    );

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter a research question.",
    );

    expect(fetch).not.toHaveBeenCalled();
  });

  it("shows 404 and navigates home", async () => {
    const user = userEvent.setup();

    renderRoute("/missing-page");

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Page not found",
      }),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("link", {
        name: "Back to dashboard",
      }),
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Dashboard",
      }),
    ).toBeInTheDocument();
  });
});

describe("navigation accessibility", () => {
  it("opens and closes the navigation disclosure", async () => {
    const user = userEvent.setup();

    renderRoute();

    const menuButton = screen.getByRole(
      "button",
      { name: "Open menu" },
    );

    const navigation = screen.getByRole(
      "navigation",
      { name: "Primary navigation" },
    );

    expect(menuButton).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    expect(navigation).not.toHaveClass("is-open");

    await user.click(menuButton);

    expect(menuButton).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    expect(menuButton).toHaveTextContent(
      "Close menu",
    );

    expect(navigation).toHaveClass("is-open");

    await user.click(menuButton);

    expect(menuButton).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    expect(navigation).not.toHaveClass("is-open");
  });

  it("closes the menu with Escape and restores focus", async () => {
    const user = userEvent.setup();

    renderRoute();

    const menuButton = screen.getByRole(
      "button",
      { name: "Open menu" },
    );

    await user.click(menuButton);

    expect(menuButton).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    const navigation = screen.getByRole(
      "navigation",
      { name: "Primary navigation" },
    );

    const historyLink = within(navigation).getByRole(
      "link",
      { name: "Research history" },
    );

    historyLink.focus();

    expect(historyLink).toHaveFocus();

    await user.keyboard("{Escape}");

    expect(menuButton).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    expect(menuButton).toHaveFocus();

    expect(navigation).not.toHaveClass("is-open");
  });

  it("closes the menu after navigation", async () => {
    const user = userEvent.setup();

    renderRoute();

    const menuButton = screen.getByRole(
      "button",
      { name: "Open menu" },
    );

    await user.click(menuButton);

    expect(menuButton).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    const navigation = screen.getByRole(
      "navigation",
      { name: "Primary navigation" },
    );

    await user.click(
      within(navigation).getByRole(
        "link",
        { name: "New research" },
      ),
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "New research",
      }),
    ).toBeInTheDocument();

    expect(menuButton).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    expect(navigation).not.toHaveClass("is-open");

    expect(
      within(navigation).getByRole(
        "link",
        { name: "New research" },
      ),
    ).toHaveAttribute("aria-current", "page");

    expect(fetch).not.toHaveBeenCalled();
  });
});
