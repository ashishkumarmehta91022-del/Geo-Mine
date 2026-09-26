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

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) {
    throw new ApiError(`API request failed with status ${response.status}.`, response.status);
  }
  return (await response.json()) as T;
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health", signal);
}
