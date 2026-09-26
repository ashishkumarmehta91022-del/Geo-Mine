import { useCallback, useEffect, useState } from "react";
import { ApiError, fetchHealth } from "@/lib/api";
import type { HealthStatus } from "@/types/health";

interface HealthState {
  health: HealthStatus | null;
  isLoading: boolean;
  isError: boolean;
  error: string | null;
  refetch: () => void;
}

/** Fetches GET /api/health and exposes loading / error / refetch controls. */
export function useHealth(): HealthState {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const refetch = useCallback(() => setAttempt((current) => current + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setIsError(false);
    setError(null);

    fetchHealth(controller.signal)
      .then((data) => {
        setHealth(data);
        setIsLoading(false);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setIsError(true);
        setError(
          cause instanceof ApiError
            ? cause.message
            : "Unexpected error while contacting the API.",
        );
        setIsLoading(false);
      });

    return () => controller.abort();
  }, [attempt]);

  return { health, isLoading, isError, error, refetch };
}
