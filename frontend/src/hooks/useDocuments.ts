import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { listDocuments } from "@/lib/documentApi";
import type { DocumentListResponse } from "@/types/document";

interface DocumentsState {
  documents: DocumentListResponse | null;
  isLoading: boolean;
  isError: boolean;
  error: string | null;
  page: number;
  setPage: (page: number) => void;
  refetch: () => void;
}

/** Fetches the paginated document list with loading / error / refetch controls. */
export function useDocuments(pageSize = 20): DocumentsState {
  const [documents, setDocuments] = useState<DocumentListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [attempt, setAttempt] = useState(0);

  const refetch = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setIsError(false);
    setError(null);

    listDocuments(page, pageSize, controller.signal)
      .then((data) => {
        setDocuments(data);
        setIsLoading(false);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setIsError(true);
        setError(cause instanceof ApiError ? cause.message : "Unexpected error while loading documents.");
        setIsLoading(false);
      });

    return () => controller.abort();
  }, [page, pageSize, attempt]);

  return { documents, isLoading, isError, error, page, setPage, refetch };
}
