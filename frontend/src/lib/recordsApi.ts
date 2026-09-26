import { apiBaseUrl } from "@/lib/env";
import { ApiError } from "@/lib/api";
import type { RecordListResponse } from "@/types/records";

/** Structured-record (Data Explorer) client — exact-match filters only. */

export async function listRecords(
  params: {
    entity?: string;
    metric?: string;
    reporting_period?: string;
    extraction_method?: string;
    document_id?: number;
    validation_status?: string;
    page?: number;
    page_size?: number;
  } = {},
  signal?: AbortSignal,
): Promise<RecordListResponse> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/records?${search.toString()}`, {
      signal,
      headers: { Accept: "application/json" },
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
      // keep generic message
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as RecordListResponse;
}
