import { apiBaseUrl } from "@/lib/env";
import { ApiError } from "@/lib/api";
import type {
  DocumentContent,
  DocumentListResponse,
  DocumentRecord,
  ProcessingStatus,
} from "@/types/document";

/**
 * Document operations client. All backend calls for the Documents page go
 * through here — components never call fetch() directly.
 */

interface BackendErrorBody {
  error?: { code?: string; message?: string };
}

async function parseError(response: Response): Promise<ApiError> {
  let message = `Request failed with status ${response.status}.`;
  try {
    const body = (await response.json()) as BackendErrorBody;
    if (body.error?.message) message = body.error.message;
  } catch {
    // non-JSON error body — keep the generic message
  }
  return new ApiError(message, response.status);
}

export async function uploadDocument(
  file: File,
  signal?: AbortSignal,
): Promise<DocumentRecord> {
  const form = new FormData();
  form.append("upload", file);

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/documents/upload`, {
      method: "POST",
      body: form,
      signal,
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as DocumentRecord;
}

export async function listDocuments(
  page = 1,
  pageSize = 20,
  signal?: AbortSignal,
): Promise<DocumentListResponse> {
  let response: Response;
  try {
    response = await fetch(
      `${apiBaseUrl()}/api/documents?page=${page}&page_size=${pageSize}`,
      { signal, headers: { Accept: "application/json" } },
    );
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as DocumentListResponse;
}

export async function deleteDocument(
  id: number,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/documents/${id}`, {
      method: "DELETE",
      signal,
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) throw await parseError(response);
}

export function downloadDocumentUrl(id: number): string {
  return `${apiBaseUrl()}/api/documents/${id}/download`;
}

export async function processDocument(
  id: number,
  signal?: AbortSignal,
): Promise<ProcessingStatus> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/documents/${id}/process`, {
      method: "POST",
      signal,
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as ProcessingStatus;
}

export async function fetchProcessingStatus(
  id: number,
  signal?: AbortSignal,
): Promise<ProcessingStatus> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/documents/${id}/processing-status`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as ProcessingStatus;
}

export async function fetchDocumentContent(
  id: number,
  signal?: AbortSignal,
): Promise<DocumentContent> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/documents/${id}/content`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) throw await parseError(response);
  return (await response.json()) as DocumentContent;
}
