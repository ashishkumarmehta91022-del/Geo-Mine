/** Shape of GET /api/health from the backend. */
export interface HealthStatus {
  status: string;
  service: string;
  database: string;
}
