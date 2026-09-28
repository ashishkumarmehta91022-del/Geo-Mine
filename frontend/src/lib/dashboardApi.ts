/**
 * Dashboard client (Step 14) — GET /api/dashboard/summary (read-only
 * operational aggregation). Follows the existing fetch + ApiError pattern.
 */

import { apiBaseUrl } from "@/lib/env";
import { ApiError } from "@/lib/api";
import type { DashboardSummary } from "@/types/dashboard";

export async function fetchDashboardSummary(signal?: AbortSignal): Promise<DashboardSummary> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/dashboard/summary`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) {
    let message = `Dashboard request failed with status ${response.status}.`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      if (body.error?.message) message = body.error.message;
    } catch {
      // keep generic message
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as DashboardSummary;
}
