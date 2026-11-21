
import {
  describe,
  expect,
  it,
  vi,
} from "vitest";

import {
  ApiError,
  getHealth,
} from "./api";

describe("health API client", () => {
  it("returns a validated health payload", async () => {
    const payload = {
      status: "ok",
      service: "agentops-api",
    };

    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        }),
      );

    vi.stubGlobal("fetch", fetchMock);

    await expect(getHealth()).resolves.toEqual(
      payload,
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/health$/),
      expect.objectContaining({
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("rejects unsuccessful HTTP responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(null, {
          status: 503,
        }),
      ),
    );

    await expect(getHealth()).rejects.toMatchObject({
      name: "ApiError",
      message:
        "Health request failed with HTTP 503.",
      status: 503,
    });
  });

  it("rejects unexpected health payloads", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({
            status: "unknown",
          }),
          { status: 200 },
        ),
      ),
    );

    await expect(getHealth()).rejects.toThrow(
      "The backend returned an unexpected health response.",
    );
  });

  it("reports a timeout without a live server", async () => {
    vi.useFakeTimers();

    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockImplementation(
        (_input, init) =>
          new Promise<Response>(
            (_resolve, reject) => {
              init?.signal?.addEventListener(
                "abort",
                () =>
                  reject(
                    new DOMException(
                      "Aborted",
                      "AbortError",
                    ),
                  ),
                { once: true },
              );
            },
          ),
      ),
    );

    const assertion = expect(
      getHealth(25),
    ).rejects.toThrow(
      "The health request timed out.",
    );

    await vi.advanceTimersByTimeAsync(25);

    await assertion;
  });

  it.each([
    0,
    -1,
    Number.NaN,
    Number.POSITIVE_INFINITY,
  ])(
    "rejects invalid timeout value %s",
    async (timeoutMs) => {
      await expect(
        getHealth(timeoutMs),
      ).rejects.toBeInstanceOf(ApiError);

      expect(fetch).not.toHaveBeenCalled();
    },
  );
});
