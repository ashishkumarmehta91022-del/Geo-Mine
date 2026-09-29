import { apiBaseUrl } from "@/lib/env";
import { ApiError, networkError } from "@/lib/api";
import type { KnowledgeStats, RetrievalMode, SearchResponse } from "@/types/search";

/** Search client for the knowledge index (Step 8 lexical, Step 9 modes). */

export async function searchKnowledge(
  params: {
    q?: string;
    mode?: RetrievalMode;
    document_id?: number;
    page?: number;
    entity?: string;
    metric?: string;
    reporting_period?: string;
    extraction_method?: string;
    validation_status?: string;
    limit?: number;
    offset?: number;
  } = {},
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/search?${search.toString()}`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw networkError();
  }
  if (!response.ok) {
    let message = `Search failed with status ${response.status}.`;
    try {
      const body = (await response.json()) as { error?: { message?: string } };
      if (body.error?.message) message = body.error.message;
    } catch {
      // keep generic message
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as SearchResponse;
}

export async function fetchKnowledgeStats(signal?: AbortSignal): Promise<KnowledgeStats> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/search/stats`, {
      signal,
      headers: { Accept: "application/json" },
    });
  } catch {
    throw networkError();
  }
  if (!response.ok) throw new ApiError(`Stats failed with status ${response.status}.`, response.status);
  return (await response.json()) as KnowledgeStats;
}
