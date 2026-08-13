import { LRUCache } from "lru-cache";

const productionApiBaseUrl = "https://api.arkwaifu.cc";
const chinaMirrorApiBaseUrl = "https://api.cn.arkwaifu.cc";

export function resolveApiBaseUrl(
  configuredApiBaseUrl: string | undefined,
  hostname?: string,
): string {
  const defaultApiBaseUrl =
    hostname === "cn.arkwaifu.cc" ? chinaMirrorApiBaseUrl : productionApiBaseUrl;
  return (configuredApiBaseUrl?.trim() || defaultApiBaseUrl).replace(/\/+$/, "");
}

const apiBaseUrl = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
  typeof window === "undefined" ? undefined : window.location.hostname,
);
const requestTimeoutMs = 15_000;

const requests = new LRUCache<string, Promise<unknown>>({
  max: 256,
  ttl: 5 * 60_000,
});

/** A request or response-validation failure from the archive service. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function pathSegment(value: string): string {
  return encodeURIComponent(value);
}

export async function fetchJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(requestTimeoutMs),
    });
  } catch {
    throw new ApiError("The archive service could not be reached.", 503);
  }

  if (!response.ok) {
    throw new ApiError(
      response.status === 404
        ? "That archive record does not exist in this locale."
        : "The archive service could not complete this request.",
      response.status,
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new ApiError("The archive service returned an unexpected response.", response.status);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("The archive service returned invalid JSON.", response.status);
  }
}

export function cachedRequest<T>(key: string, load: () => Promise<T>): Promise<T> {
  const existing = requests.get(key);
  if (existing) return existing as Promise<T>;

  const request = load();
  requests.set(key, request);
  return request;
}

/** Clears all fulfilled, pending, and rejected API requests from the client cache. */
export function clearApiCache(): void {
  requests.clear();
}
