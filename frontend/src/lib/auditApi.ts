import { apiBaseUrl } from "@/lib/env";
import { ApiError } from "@/lib/api";
import type { AuditLogListResponse } from "@/types/audit";

/** Audit trail client — read-only. */

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      headers: { Accept: "application/json" },
      signal,
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      if (body.error?.message) message = body.error.message;
    } catch {
      // non-JSON error body — keep the generic message
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export function fetchAuditLogs(
  page = 1,
  pageSize = 20,
  action?: string,
  signal?: AbortSignal,
): Promise<AuditLogListResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (action) params.set("action", action);
  return request<AuditLogListResponse>(`/api/audit?${params.toString()}`, signal);
}
