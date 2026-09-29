import { apiBaseUrl } from "@/lib/env";
import type { HealthStatus } from "@/types/health";

/**
 * Minimal typed API client.
 *
 * Later steps will add more endpoints here (documents, queries, reports…),
 * each following the same fetch + error pattern.
 */

export class ApiError extends Error {
  readonly statusCode?: number;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
  }
}

/**
 * Diagnostic error for network-level failures — fetch itself rejected
 * (DNS failure, connection refused, or CORS block). No server response is
 * involved, so surface the exact target tried plus the two settings that
 * fix a split deployment (e.g. frontend on Vercel, API on Railway):
 *   - VITE_API_BASE_URL on the frontend: absolute API origin, set at build time
 *   - CORS_ORIGINS on the backend: comma-separated list including this app's origin
 */
export function networkError(): ApiError {
  const base = apiBaseUrl();
  const target =
    base === ""
      ? `${window.location.origin}/api (same origin — no VITE_API_BASE_URL set)`
      : `${base}/api`;
  return new ApiError(
    "Cannot reach the API server. Is the backend running? " +
      `Tried ${target}. ` +
      "For a split deploy: set the frontend's VITE_API_BASE_URL to the API origin " +
      "(e.g. https://<app>.up.railway.app) and the backend's CORS_ORIGINS to this " +
      "app's origin (e.g. https://<app>.vercel.app), then rebuild both.",
  );
}

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw networkError();
  }
  if (!response.ok) {
    throw new ApiError(`API request failed with status ${response.status}.`, response.status);
  }
  return (await response.json()) as T;
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health", signal);
}
