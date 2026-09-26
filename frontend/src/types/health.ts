/** Shape of GET /api/health from the backend. */
export interface DatabaseHealth {
  connected: boolean;
  /** "connected" | "unavailable" | "timeout" */
  detail: string;
}

export interface HealthStatus {
  status: string;
  service: string;
  database: DatabaseHealth;
}
