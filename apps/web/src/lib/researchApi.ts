import {
  isRecord,
  isResearchAccepted,
  isResearchHistory,
  isResearchTask,
  isTaskId,
} from "./research";

import type {
  ResearchAccepted,
  ResearchHistory,
  ResearchInput,
  ResearchTask,
} from "./research";

const BASE = "/api/v1";
const TIMEOUT = 10000;

const messages: Record<number, string> = {
  401: "Authentication required. Sign in through the approved review environment.",
  403: "Request authorization failed. Refresh your session and try again.",
  404: "The requested research resource is unavailable.",
  409: "This submission key conflicts with an existing task. Check research history.",
  422: "Invalid research request. Review your question and scope.",
  429: "The research queue is full. Try again later.",
  503: "Research service is unavailable. Authentication or database access may be disabled.",
};

export class ResearchApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ResearchApiError";
  }
}

export function researchErrorMessage(error: unknown): string {
  return error instanceof ResearchApiError
    ? error.message
    : "Unable to complete the research request.";
}

async function request<T>(
  path: string,
  validate: (value: unknown) => value is T,
  signal?: AbortSignal,
  init: RequestInit = {},
  expectedStatus = 200,
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();

  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });

  const timeout = globalThis.setTimeout(abort, TIMEOUT);

  try {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");

    const response = await fetch(`${BASE}${path}`, {
      ...init,
      headers,
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      signal: controller.signal,
    });

    if (response.status !== expectedStatus) {
      throw new ResearchApiError(
        messages[response.status] || "Research request failed.",
        response.status,
      );
    }

    const payload: unknown = await response.json();

    if (!validate(payload)) {
      throw new ResearchApiError(
        "Unexpected research response. Check research history before submitting again.",
      );
    }

    return payload;
  } catch (error: unknown) {
    if (error instanceof ResearchApiError) throw error;

    throw new ResearchApiError(
      controller.signal.aborted
        ? "The research request was interrupted or timed out."
        : "Unable to connect to the research service.",
    );
  } finally {
    globalThis.clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

function isCsrf(value: unknown): value is { csrf_token: string } {
  return isRecord(value)
    && typeof value.csrf_token === "string"
    && value.csrf_token.length > 0
    && value.csrf_token.length <= 256;
}

export async function createResearch(
  input: ResearchInput,
  key: string,
  signal?: AbortSignal,
): Promise<ResearchAccepted> {
  if (!key.trim() || key.length > 128) {
    throw new ResearchApiError("Invalid submission key.");
  }

  const csrf = await request("/auth/csrf", isCsrf, signal);

  return request(
    "/research/tasks",
    isResearchAccepted,
    signal,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf.csrf_token,
        "Idempotency-Key": key,
      },
      body: JSON.stringify(input),
    },
    202,
  );
}

export function getResearchHistory(
  cursor: string | null = null,
  signal?: AbortSignal,
): Promise<ResearchHistory> {
  const query = new URLSearchParams({ limit: "20" });

  if (cursor !== null) query.set("cursor", cursor);

  return request(
    `/research/tasks?${query}`,
    isResearchHistory,
    signal,
  );
}

export function getResearchTask(
  id: string,
  signal?: AbortSignal,
): Promise<ResearchTask> {
  if (!isTaskId(id)) {
    return Promise.reject(
      new ResearchApiError("Invalid research task identifier.", 422),
    );
  }

  return request(
    `/research/tasks/${encodeURIComponent(id)}`,
    (value): value is ResearchTask =>
      isResearchTask(value) && value.id === id,
    signal,
  );
}
