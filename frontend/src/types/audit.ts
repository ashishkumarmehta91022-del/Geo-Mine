/** Audit log API types (mirror backend/app/api/routes/audit.py). */

export interface AuditLogItem {
  id: number;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  page: number;
  page_size: number;
  total: number;
}
