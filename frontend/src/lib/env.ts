/**
 * Public (browser-safe) environment variables.
 *
 * Only variables prefixed with VITE_ are bundled into the client, so no
 * secrets may ever be placed here. Example: frontend/.env.local
 *   VITE_API_BASE_URL=http://localhost:8000
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";

/**
 * Base URL for API calls. Empty string means "same origin", which lets the
 * Vite dev proxy (see vite.config.ts) forward /api requests to the backend.
 */
export const apiBaseUrl = (): string => API_BASE_URL;
