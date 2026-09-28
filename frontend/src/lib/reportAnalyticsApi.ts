/**
 * Report analytics client (Step 12) — POST /api/reports/analyze for the
 * analytical visualization surface, POST /api/reports/generate for DOCX
 * download. Follows the existing fetch + ApiError pattern.
 */

import { apiBaseUrl } from "@/lib/env";
import { ApiError } from "@/lib/api";
import type { AnalyzeRequest, AnalyzeResponse } from "@/types/reportAnalytics";

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const error = (await response.json()) as { error?: { message?: string } };
      if (error.error?.message) message = error.error.message;
    } catch {
      // keep generic message
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function analyzeReports(
  request: AnalyzeRequest,
  signal?: AbortSignal,
): Promise<AnalyzeResponse> {
  return post<AnalyzeResponse>("/api/reports/analyze", request, signal);
}

export async function generateReportDocx(request: AnalyzeRequest, signal?: AbortSignal): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/reports/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...request, output_format: "docx" }),
      signal,
    });
  } catch {
    throw new ApiError("Cannot reach the API server. Is the backend running?");
  }
  if (!response.ok) {
    let message = `Report generation failed with status ${response.status}.`;
    try {
      const error = (await response.json()) as { error?: { message?: string } };
      if (error.error?.message) message = error.error.message;
    } catch {
      // keep generic message
    }
    throw new ApiError(message, response.status);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = /filename=\"?([^\";]+)\"?/.exec(disposition);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = match?.[1] ?? "report.docx";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
