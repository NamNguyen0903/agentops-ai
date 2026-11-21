export interface HealthResponse {
  status: "ok";
  service: "agentops-api";
}

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL as
  | string
  | undefined;

const API_BASE_URL = (configuredBaseUrl?.trim() || "/api/v1").replace(
  /\/+$/,
  "",
);

export class ApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function isHealthResponse(value: unknown): value is HealthResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    "status" in value &&
    value.status === "ok" &&
    "service" in value &&
    value.service === "agentops-api"
  );
}

export async function getHealth(
  timeoutMs: number = 5000,
): Promise<HealthResponse> {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new ApiError("Health request timeout must be a positive number.");
  }

  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal: controller.signal,
      cache: "no-store",
    });

    if (!response.ok) {
      throw new ApiError(
        `Health request failed with HTTP ${response.status}.`,
        response.status,
      );
    }

    const payload: unknown = await response.json();

    if (!isHealthResponse(payload)) {
      throw new ApiError("The backend returned an unexpected health response.");
    }

    return payload;
  } catch (error: unknown) {
    if (controller.signal.aborted) {
      throw new ApiError("The health request timed out.");
    }

    if (error instanceof ApiError) {
      throw error;
    }

    throw new ApiError("Unable to read the backend health response.");
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}