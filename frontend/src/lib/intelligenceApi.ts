/**
 * Document intelligence client (Step 13) — deterministic intelligence over
 * the knowledge index. Follows the existing fetch + ApiError pattern.
 */

import { apiBaseUrl } from "@/lib/env";
import { ApiError } from "@/lib/api";
import type {
  AiSummary,
  CorpusStats,
  DocumentSummary,
  IntelligenceResponse,
  Keyword,
  Topic,
  TopicDocumentMatch,
  WordCloudTerm,
} from "@/types/intelligence";

interface ErrorBody {
  error?: { message?: string };
}

async function request<T>(path: string, init?: RequestInit, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, { signal, ...init });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = (await response.json()) as ErrorBody;
      if (body.error?.message) message = body.error.message;
    } catch {
      // keep generic message
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

interface KeywordsPayload {
  document_id: number;
  keywords: Keyword[];
  corpus_stats: CorpusStats;
}

interface TopicsPayload {
  document_id: number;
  topics: Topic[];
  topic_document_matches: TopicDocumentMatch[];
  corpus_stats: CorpusStats;
}

interface WordCloudPayload {
  document_id: number;
  terms: WordCloudTerm[];
  corpus_stats: CorpusStats;
}

export function fetchDocumentIntelligence(documentId: number, signal?: AbortSignal): Promise<IntelligenceResponse> {
  return request<IntelligenceResponse>(`/api/intelligence/documents/${documentId}`, undefined, signal);
}

export function fetchDocumentKeywords(documentId: number, signal?: AbortSignal): Promise<KeywordsPayload> {
  return request<KeywordsPayload>(`/api/intelligence/documents/${documentId}/keywords`, undefined, signal);
}

export function fetchDocumentTopics(documentId: number, signal?: AbortSignal): Promise<TopicsPayload> {
  return request<TopicsPayload>(`/api/intelligence/documents/${documentId}/topics`, undefined, signal);
}

export function fetchDocumentWordCloud(documentId: number, signal?: AbortSignal): Promise<WordCloudPayload> {
  return request<WordCloudPayload>(`/api/intelligence/documents/${documentId}/word-cloud`, undefined, signal);
}

export async function fetchCorpusIntelligence(
  documentIds: number[] | null,
  signal?: AbortSignal,
): Promise<IntelligenceResponse> {
  return request<IntelligenceResponse>(
    "/api/intelligence/corpus/analyze",
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ document_ids: documentIds }),
    },
    signal,
  );
}

export async function summarizeDocument(
  documentId: number,
  includeAiSummary: boolean,
  signal?: AbortSignal,
): Promise<{ document_id: number; summary: DocumentSummary; ai_summary: AiSummary | null }> {
  return request(
    `/api/intelligence/documents/${documentId}/summarize`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ include_ai_summary: includeAiSummary }),
    },
    signal,
  );
}
