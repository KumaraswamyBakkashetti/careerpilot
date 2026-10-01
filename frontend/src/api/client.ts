export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status?: number,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type ApiResult = {
  status: number;
  body: unknown;
  requestId: string | null;
};

export class ApiClient {
  constructor(
    private readonly baseUrl = import.meta.env.VITE_API_BASE_URL || "",
    private readonly timeoutMs = 8000,
  ) {}

  async get(
    path: string,
    signal?: AbortSignal,
    acceptedStatuses: readonly number[] = [200],
  ): Promise<ApiResult> {
    const controller = new AbortController();
    const abort = () => controller.abort();
    signal?.addEventListener("abort", abort, { once: true });
    if (signal?.aborted) controller.abort();
    let timedOut = false;
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, this.timeoutMs);
    const requestId = crypto.randomUUID();
    try {
      const response = await fetch(
        `${this.baseUrl.replace(/\/$/, "")}${path}`,
        {
          signal: controller.signal,
          headers: { Accept: "application/json", "X-Request-ID": requestId },
          credentials: "omit",
        },
      );
      let body: unknown;
      try {
        body = await response.json();
      } catch (error) {
        if (controller.signal.aborted) throw error;
        throw new ApiError(
          "INVALID_RESPONSE",
          "The backend returned an invalid response.",
          response.status,
          requestId,
        );
      }
      const returnedId = response.headers.get("X-Request-ID") || requestId;
      if (!acceptedStatuses.includes(response.status)) {
        const error =
          typeof body === "object" && body !== null && "error" in body
            ? body.error
            : null;
        const code =
          typeof error === "object" &&
          error !== null &&
          "code" in error &&
          typeof error.code === "string" &&
          /^[A-Z_]{1,64}$/.test(error.code)
            ? error.code
            : "HTTP_ERROR";
        throw new ApiError(
          code,
          "The backend could not complete the request.",
          response.status,
          returnedId,
        );
      }
      return { status: response.status, body, requestId: returnedId };
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (timedOut)
        throw new ApiError(
          "TIMEOUT",
          "The backend request timed out.",
          undefined,
          requestId,
        );
      if (controller.signal.aborted)
        throw new ApiError(
          "CANCELLED",
          "The request was cancelled.",
          undefined,
          requestId,
        );
      throw new ApiError(
        "NETWORK_ERROR",
        "The backend could not be reached.",
        undefined,
        requestId,
      );
    } finally {
      clearTimeout(timeout);
      signal?.removeEventListener("abort", abort);
    }
  }
}

export const apiClient = new ApiClient();
