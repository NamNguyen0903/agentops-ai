import {
  act,
  render,
  screen,
  waitFor,
} from "@testing-library/react";

import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import App from "../App";
import type { ResearchTask, TaskStatus } from "../lib/research";

const id = "11111111-1111-4111-8111-111111111111";
const date = "2026-11-24T06:00:00Z";

function task(status: TaskStatus = "queued"): ResearchTask {
  return {
    id,
    question: "Compare products",
    scope: {
      geography: "Europe",
      category: null,
      competitors: [],
      time_scope: null,
    },
    status,
    current_stage: null,
    created_at: date,
    updated_at: date,
    started_at: null,
    completed_at: null,
    error_category: null,
  };
}

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), { status });
}

function accepted(): Response {
  return json({
    task_id: id,
    status: "queued",
    status_url: `/api/v1/research/tasks/${id}`,
  }, 202);
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

describe("research workflow", () => {
  it("submits a question and navigates to saved task detail", async () => {
    const user = userEvent.setup();

    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({ csrf_token: "proof" }))
      .mockResolvedValueOnce(accepted())
      .mockResolvedValueOnce(json(task()));

    vi.stubGlobal("fetch", fetchMock);

    renderRoute("/research/new");

    await user.type(
      screen.getByRole("textbox", {
        name: "Research question (required)",
      }),
      "Compare products",
    );

    await user.type(screen.getByLabelText("Geography"), "Europe");

    await user.click(
      screen.getByRole("button", { name: "Submit research" }),
    );

    expect(await screen.findByText("Queued")).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { level: 1, name: "Research task" }),
    ).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(3);

    expect(fetchMock.mock.calls[2][0]).toBe(
      `/api/v1/research/tasks/${id}`,
    );
  });

  it("reuses the submission key after a failed request", async () => {
    const user = userEvent.setup();

    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({ csrf_token: "proof-one" }))
      .mockRejectedValueOnce(new Error("Synthetic connection failure"))
      .mockResolvedValueOnce(json({ csrf_token: "proof-two" }))
      .mockResolvedValueOnce(accepted())
      .mockResolvedValueOnce(json(task()));

    vi.stubGlobal("fetch", fetchMock);

    renderRoute("/research/new");

    await user.type(
      screen.getByRole("textbox", {
        name: "Research question (required)",
      }),
      "Compare products",
    );

    await user.click(
      screen.getByRole("button", { name: "Submit research" }),
    );

    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Retry submission" }),
    );

    expect(await screen.findByText("Queued")).toBeInTheDocument();

    const original = new Headers(fetchMock.mock.calls[1][1]?.headers);
    const retry = new Headers(fetchMock.mock.calls[3][1]?.headers);

    expect(original.get("Idempotency-Key")).toBeTruthy();
    expect(original.get("Idempotency-Key")).toBe(
      retry.get("Idempotency-Key"),
    );

    expect(retry.get("X-CSRF-Token")).toBe("proof-two");
  });

  it("shows an empty history only after a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        json({ items: [], next_cursor: null }),
      ),
    );

    renderRoute("/research/history");

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading research history",
    );

    expect(
      await screen.findByRole("heading", {
        name: "No research history yet",
      }),
    ).toBeInTheDocument();
  });

  it("loads a paginated history and supports navigation", async () => {
    const user = userEvent.setup();

    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({
        items: [task()],
        next_cursor: "next-cursor",
      }))
      .mockResolvedValueOnce(json({
        items: [],
        next_cursor: null,
      }))
      .mockResolvedValueOnce(json({
        items: [task()],
        next_cursor: "next-cursor",
      }));

    vi.stubGlobal("fetch", fetchMock);

    renderRoute("/research/history");

    expect(
      await screen.findByRole("link", { name: "Compare products" }),
    ).toHaveAttribute("href", `/research/tasks/${id}`);

    await user.click(
      screen.getByRole("button", { name: "Next page" }),
    );

    expect(await screen.findByText("Page 2")).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchMock.mock.calls[1][0]).toContain("cursor=next-cursor");
    });

    await user.click(
      screen.getByRole("button", { name: "Previous page" }),
    );

    expect(await screen.findByText("Page 1")).toBeInTheDocument();

    expect(
      await screen.findByRole("link", { name: "Compare products" }),
    ).toBeInTheDocument();
  });

  it("shows unavailable history rather than fabricated records", async () => {
    const user = userEvent.setup();

    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>()
        .mockResolvedValueOnce(json({}, 503))
        .mockResolvedValueOnce(json({
          items: [],
          next_cursor: null,
        })),
    );

    renderRoute("/research/history");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Research service is unavailable",
    );

    expect(
      screen.queryByText("No research history yet"),
    ).not.toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Retry history" }),
    );

    expect(
      await screen.findByText("No research history yet"),
    ).toBeInTheDocument();
  });

  it("polls actual task status and stops after a terminal state", async () => {
    vi.useFakeTimers();

    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json(task("queued")))
      .mockResolvedValueOnce(json(task("running")))
      .mockResolvedValueOnce(json(task("completed")));

    vi.stubGlobal("fetch", fetchMock);

    renderRoute(`/research/tasks/${id}`);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText("Queued")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(screen.getByText("Running")).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(
      screen.getByText("Automatic status polling has stopped."),
    ).toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("cancels polling when leaving task detail", async () => {
    vi.useFakeTimers();

    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json(task()));

    vi.stubGlobal("fetch", fetchMock);

    const view = renderRoute(`/research/tasks/${id}`);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByText("Queued")).toBeInTheDocument();

    view.unmount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects invalid route identifiers without a request", () => {
    renderRoute("/research/tasks/invalid");

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Invalid research task identifier",
    );

    expect(fetch).not.toHaveBeenCalled();
  });
});
