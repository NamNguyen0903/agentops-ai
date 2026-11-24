import { describe, expect, it, vi } from "vitest";

import {
  createResearch,
  getResearchHistory,
  getResearchTask,
} from "./researchApi";

import { isTerminal } from "./research";
import type { ResearchInput } from "./research";

const id = "11111111-1111-4111-8111-111111111111";

const input: ResearchInput = {
  question: "Compare products",
  scope: {
    geography: "Europe",
    category: null,
    time_scope: null,
    competitors: ["Company A", "Company B"],
  },
};

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), { status });
}

describe("research API client", () => {
  it("obtains CSRF and submits an idempotent request", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({ csrf_token: "synthetic-proof" }))
      .mockResolvedValueOnce(json({
        task_id: id,
        status: "queued",
        status_url: `/api/v1/research/tasks/${id}`,
      }, 202));

    vi.stubGlobal("fetch", fetchMock);

    const result = await createResearch(input, "test-key");

    expect(result.task_id).toBe(id);

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/auth/csrf");

    const [url, options] = fetchMock.mock.calls[1];
    const headers = new Headers(options?.headers);

    expect(url).toBe("/api/v1/research/tasks");
    expect(options?.method).toBe("POST");
    expect(options?.credentials).toBe("same-origin");
    expect(options?.redirect).toBe("error");
    expect(options?.cache).toBe("no-store");

    expect(headers.get("X-CSRF-Token")).toBe("synthetic-proof");
    expect(headers.get("Idempotency-Key")).toBe("test-key");
    expect(JSON.parse(String(options?.body))).toEqual(input);
  });

  it("does not submit when CSRF acquisition fails", async () => {
    const fetchMock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({}, 401));

    vi.stubGlobal("fetch", fetchMock);

    await expect(createResearch(input, "key")).rejects.toMatchObject({
      status: 401,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each([401, 403, 404, 409, 422, 429, 503, 500])(
    "handles HTTP %s without leaking raw error text",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi.fn<typeof fetch>().mockResolvedValue(
          json({ detail: "private-internal-error" }, status),
        ),
      );

      try {
        await getResearchHistory();
        throw new Error("Expected rejection");
      } catch (error: unknown) {
        expect(error).toMatchObject({ status });
        expect(String(error)).not.toContain("private-internal-error");
      }
    },
  );

  it("validates malformed history responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        json({ items: [{ status: "invented" }], next_cursor: null }),
      ),
    );

    await expect(getResearchHistory()).rejects.toThrow(
      "Unexpected research response",
    );
  });

  it("encodes pagination cursors", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      json({ items: [], next_cursor: null }),
    );

    vi.stubGlobal("fetch", fetchMock);

    await getResearchHistory("cursor+/=");

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/v1/research/tasks?limit=20&cursor=cursor%2B%2F%3D",
    );
  });

  it("rejects invalid task identifiers before sending requests", async () => {
    await expect(getResearchTask("../auth/me")).rejects.toMatchObject({
      status: 422,
    });

    expect(fetch).not.toHaveBeenCalled();
  });

  it("rejects an external polling URL in a submission response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>()
        .mockResolvedValueOnce(json({ csrf_token: "proof" }))
        .mockResolvedValueOnce(json({
          task_id: id,
          status: "queued",
          status_url: "https://invalid.example/task",
        }, 202)),
    );

    await expect(createResearch(input, "key")).rejects.toThrow(
      "Unexpected research response",
    );
  });

  it("reports active and terminal states correctly", () => {
    expect(isTerminal("queued")).toBe(false);
    expect(isTerminal("running")).toBe(false);
    expect(isTerminal("completed")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
    expect(isTerminal("timed_out")).toBe(true);
    expect(isTerminal("insufficient_evidence")).toBe(true);
  });
});
