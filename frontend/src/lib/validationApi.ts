import { apiBaseUrl } from "@/lib/env";
import { ApiError, networkError } from "@/lib/api";
import type {
  ReviewQueueResponse,
  ValidationDocumentResponse,
  ValidationRunResponse,
} from "@/types/validation";

/** Validation operations client — components never call fetch() directly. */

async function parseError(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}.`;
  try {
    const body = (await response.json()) as { error?: { message?: string } };
    if (body.error?.message) message = body.error.message;
  } catch {
    // non-JSON error body — keep the generic message
  }
  return new ApiError(message, response.status);
}

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      headers: { Accept: "application/json" },
      signal,
      ...init,
    });
  } catch {
    throw networkError();
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as T;
}

export function runValidation(documentId: number, signal?: AbortSignal): Promise<ValidationRunResponse> {
  return request<ValidationRunResponse>(
    `/api/validation/run/${documentId}`,
    { method: "POST" },
    signal,
  );
}

export function fetchDocumentValidation(
  documentId: number,
  signal?: AbortSignal,
): Promise<ValidationDocumentResponse> {
  return request<ValidationDocumentResponse>(`/api/validation/${documentId}`, {}, signal);
}

export function fetchReviewQueue(
  page = 1,
  reviewStatus = "open",
  signal?: AbortSignal,
): Promise<ReviewQueueResponse> {
  return request<ReviewQueueResponse>(
    `/api/validation/review-queue?page=${page}&review_status=${reviewStatus}`,
    {},
    signal,
  );
}

export function updateReviewStatus(
  validationId: number,
  reviewStatus: string,
  reviewNotes?: string,
  signal?: AbortSignal,
): Promise<{ id: number; review_status: string; review_notes: string | null; reviewed_at: string | null }> {
  return request(
    `/api/validation/${validationId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: reviewStatus, review_notes: reviewNotes ?? null }),
    },
    signal,
  );
}
