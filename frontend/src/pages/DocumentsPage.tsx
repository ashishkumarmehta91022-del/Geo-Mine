import { useCallback, useEffect, useRef, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { Panel } from "@/components/ui/Cards";
import { Badge, StatusBadge, type BadgeTone } from "@/components/ui/Badge";
import { Icon } from "@/components/ui/Icon";
import {
  deleteDocument,
  downloadDocumentUrl,
  fetchDocumentContent,
  fetchProcessingStatus,
  processDocument,
  uploadDocument,
} from "@/lib/documentApi";
import { fetchDashboardSummary } from "@/lib/dashboardApi";
import type { RecentDocumentItem } from "@/types/dashboard";
import { useDocuments } from "@/hooks/useDocuments";
import {
  MAX_UPLOAD_SIZE_MB,
  SUPPORTED_FILE_TYPES,
  type DocumentContent,
  type DocumentRecord,
} from "@/types/document";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function typeBadge(type: string): string {
  switch (type) {
    case "pdf":
      return "bg-red-50 text-red-700 border-red-200";
    case "docx":
      return "bg-brand-50 text-brand-700 border-brand-200";
    case "xlsx":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "image":
      return "bg-violet-50 text-violet-700 border-violet-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}

function validationTone(status: string | null | undefined): BadgeTone {
  switch (status) {
    case "pass":
    case "valid":
      return "ok";
    case "warning":
      return "warn";
    case "failed":
    case "error":
      return "bad";
    case "review_required":
      return "review";
    default:
      return "neutral";
  }
}

const SUPPORTED_LABELS = ["PDF", "DOCX", "XLSX", "XLS", "PNG", "JPG"];

/** Indeterminate pipeline strip shown while the real pipeline runs. */
function ProcessingPipeline() {
  const stages = ["Document", "Extraction", "Structuring", "Validation", "Indexing"];
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1" aria-label="Processing pipeline running">
      {stages.map((stage, i) => (
        <span key={stage} className="flex items-center gap-1">
          <span className="inline-flex items-center gap-1.5 rounded border border-brand-200 bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-700">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" aria-hidden="true" />
            {stage}
          </span>
          {i < stages.length - 1 && <span className="text-gray-300" aria-hidden="true">→</span>}
        </span>
      ))}
    </div>
  );
}

/** Documents page: enterprise upload workspace, processing and provenance viewer. */
export default function DocumentsPage() {
  const { documents, isLoading, isError, error, setPage, refetch } = useDocuments();
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [processingIds, setProcessingIds] = useState<Set<number>>(new Set());
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({});
  const [viewerDoc, setViewerDoc] = useState<DocumentRecord | null>(null);
  const [viewerContent, setViewerContent] = useState<DocumentContent | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [viewerError, setViewerError] = useState<string | null>(null);
  const [docStats, setDocStats] = useState<Map<number, RecentDocumentItem>>(new Map());
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Real per-document record counts + validation status (dashboard summary).
  const loadDocStats = useCallback(async () => {
    try {
      const summary = await fetchDashboardSummary();
      setDocStats(new Map(summary.recent_documents.map((d) => [d.document_id, d])));
    } catch {
      setDocStats(new Map()); // stats are enrichment only; list still loads
    }
  }, []);

  useEffect(() => {
    loadDocStats();
  }, [loadDocStats, documents]);

  const handleUpload = useCallback(
    async (files: FileList | null) => {
      const file = files?.[0];
      if (!file) return;
      setUploadError(null);
      setUploadSuccess(null);
      setIsUploading(true);
      try {
        const created = await uploadDocument(file);
        setUploadSuccess(`"${created.filename}" uploaded successfully.`);
        refetch();
      } catch (cause: unknown) {
        setUploadError(cause instanceof Error ? cause.message : "Upload failed unexpectedly.");
      } finally {
        setIsUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [refetch],
  );

  const handleProcess = useCallback(
    async (doc: DocumentRecord) => {
      setUploadError(null);
      setUploadSuccess(null);
      setRowErrors((current) => ({ ...current, [doc.id]: "" }));
      setProcessingIds((current) => new Set(current).add(doc.id));
      try {
        const status = await processDocument(doc.id);
        if (status.status === "failed") {
          setRowErrors((current) => ({ ...current, [doc.id]: status.error_message ?? "Processing failed." }));
        } else {
          // Confirm the persisted state through the processing-status API.
          const detailed = await fetchProcessingStatus(doc.id);
          setUploadSuccess(
            `"${doc.filename}" processed — extraction ${detailed.extraction_status ?? "complete"}, ` +
              `${detailed.statistics.total_units} unit${detailed.statistics.total_units === 1 ? "" : "s"} extracted.`,
          );
        }
        refetch();
      } catch (cause: unknown) {
        setRowErrors((current) => ({
          ...current,
          [doc.id]: cause instanceof Error ? cause.message : "Processing failed.",
        }));
      } finally {
        setProcessingIds((current) => {
          const next = new Set(current);
          next.delete(doc.id);
          return next;
        });
      }
    },
    [refetch],
  );

  const handleDelete = useCallback(
    async (doc: DocumentRecord) => {
      setUploadError(null);
      setUploadSuccess(null);
      setDeletingId(doc.id);
      try {
        await deleteDocument(doc.id);
        setUploadSuccess(`"${doc.filename}" deleted.`);
        refetch();
      } catch (cause: unknown) {
        setUploadError(cause instanceof Error ? cause.message : "Delete failed.");
      } finally {
        setDeletingId(null);
      }
    },
    [refetch],
  );

  const openViewer = useCallback(async (doc: DocumentRecord) => {
    setViewerDoc(doc);
    setViewerContent(null);
    setViewerError(null);
    setViewerLoading(true);
    try {
      setViewerContent(await fetchDocumentContent(doc.id));
    } catch (cause: unknown) {
      setViewerError(cause instanceof Error ? cause.message : "Could not load extracted content.");
    } finally {
      setViewerLoading(false);
    }
  }, []);

  const closeViewer = useCallback(() => {
    setViewerDoc(null);
    setViewerContent(null);
    setViewerError(null);
  }, []);

  return (
    <>
      <PageHeader
        title="Document Intelligence"
        description="Upload, process and trace geological, mining and production documents."
      />

      {/* Upload panel */}
      <section aria-label="Upload a document" className="mb-8">
        <Panel title="Upload Documents" subtitle={`Supported: ${SUPPORTED_LABELS.join(" · ")} — max ${MAX_UPLOAD_SIZE_MB} MB per file`}>
          <div
            className={`flex flex-col items-center justify-center rounded-md border-2 border-dashed px-6 py-8 text-center transition-colors ${
              isDragging ? "border-brand-500 bg-brand-50" : "border-gray-300"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setIsDragging(false);
              handleUpload(e.dataTransfer.files);
            }}
          >
            {isUploading ? (
              <>
                <span
                  className="mb-3 h-8 w-8 animate-spin rounded-full border-[3px] border-brand-600 border-t-transparent"
                  role="status"
                  aria-label="Uploading"
                />
                <p className="text-sm font-medium text-gray-700">Uploading…</p>
              </>
            ) : (
              <>
                <span className="mb-2 flex h-11 w-11 items-center justify-center rounded-full bg-brand-50 text-brand-600">
                  <Icon name="upload" className="h-5 w-5" />
                </span>
                <p className="text-sm font-medium text-gray-700">
                  Drag &amp; drop a file here, or
                </p>
                <button type="button" className="btn-primary mt-3" onClick={() => fileInputRef.current?.click()}>
                  Browse Files
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept={SUPPORTED_FILE_TYPES}
                  onChange={(e) => handleUpload(e.target.files)}
                />
                <div className="mt-3 flex flex-wrap justify-center gap-1.5" aria-label="Supported formats">
                  {SUPPORTED_LABELS.map((label) => (
                    <span key={label} className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                      {label}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>

          {uploadSuccess && (
            <div
              role="status"
              className="mt-3 flex items-start justify-between gap-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800"
            >
              <span className="flex items-start gap-2">
                <Icon name="ok" className="mt-0.5 h-4 w-4 shrink-0" />
                {uploadSuccess}
              </span>
              <button type="button" className="text-emerald-700 underline" onClick={() => setUploadSuccess(null)}>
                dismiss
              </button>
            </div>
          )}
          {uploadError && (
            <div
              role="alert"
              className="mt-3 flex items-start justify-between gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700"
            >
              <span className="flex items-start gap-2">
                <Icon name="warn" className="mt-0.5 h-4 w-4 shrink-0" />
                {uploadError}
              </span>
              <button type="button" className="text-red-600 underline" onClick={() => setUploadError(null)}>
                dismiss
              </button>
            </div>
          )}
        </Panel>
      </section>

      {/* Document table */}
      <section aria-label="Uploaded documents">
        <h3 className="section-title mb-3">Documents</h3>

        {isLoading && <StateBlock variant="loading" title="Loading documents…" />}

        {!isLoading && isError && (
          <StateBlock
            variant="error"
            title="Cannot load documents"
            description={error ?? undefined}
            action={
              <button type="button" className="btn-primary" onClick={() => refetch()}>
                Retry
              </button>
            }
          />
        )}

        {!isLoading && !isError && documents && documents.items.length === 0 && (
          <StateBlock
            variant="empty"
            title="No documents yet"
            description="Upload a geological, mining or production document to begin."
            action={
              <button type="button" className="btn-primary" onClick={() => fileInputRef.current?.click()}>
                <Icon name="upload" className="h-4 w-4" /> Upload Document
              </button>
            }
          />
        )}

        {!isLoading && !isError && documents && documents.items.length > 0 && (
          <>
            <div className="card overflow-x-auto">
              <table className="table-base min-w-[820px]">
                <thead>
                  <tr>
                    <th scope="col">Document</th>
                    <th scope="col">Type</th>
                    <th scope="col" className="text-right">Records</th>
                    <th scope="col">Processing</th>
                    <th scope="col">Validation</th>
                    <th scope="col">Created</th>
                    <th scope="col" className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.items.map((doc) => {
                    const stats = docStats.get(doc.id);
                    const isProcessingRow = processingIds.has(doc.id) || doc.status === "processing";
                    return (
                      <tr key={doc.id} className="align-top">
                        <td className="max-w-[260px]">
                          <p className="truncate font-medium text-gray-900" title={doc.filename}>
                            {doc.filename}
                          </p>
                          {doc.error_message && doc.status === "failed" && (
                            <p className="mt-0.5 line-clamp-2 text-xs text-red-600" title={doc.error_message}>
                              {doc.error_message}
                            </p>
                          )}
                          {rowErrors[doc.id] && (
                            <p className="mt-0.5 line-clamp-2 text-xs text-red-600">{rowErrors[doc.id]}</p>
                          )}
                        </td>
                        <td>
                          <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${typeBadge(doc.document_type)}`}>
                            {doc.document_type}
                          </span>
                        </td>
                        <td className="text-right tabular-nums">
                          {isProcessingRow ? "…" : stats ? stats.record_count : "—"}
                        </td>
                        <td>
                          <StatusBadge status={doc.status} />
                          {isProcessingRow && <ProcessingPipeline />}
                        </td>
                        <td>
                          {stats?.validation_status ? (
                            <Badge tone={validationTone(stats.validation_status)}>
                              {stats.validation_status.replace("_", " ")}
                            </Badge>
                          ) : stats?.requires_review ? (
                            <Badge tone="review">review required</Badge>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                        <td className="whitespace-nowrap text-xs text-gray-500">{formatDateTime(doc.uploaded_at)}</td>
                        <td>
                          <div className="flex justify-end gap-1.5">
                            <button
                              type="button"
                              className="btn-primary whitespace-nowrap !px-2.5 !py-1.5 text-xs"
                              onClick={() => handleProcess(doc)}
                              disabled={isProcessingRow}
                              title={
                                doc.status === "processed"
                                  ? "Re-process (replaces previous extraction)"
                                  : "Run deterministic extraction"
                              }
                            >
                              {isProcessingRow ? (
                                <>
                                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                                  Processing…
                                </>
                              ) : doc.status === "processed" ? (
                                "Re-process"
                              ) : (
                                "Process"
                              )}
                            </button>
                            {doc.status === "processed" && (
                              <button
                                type="button"
                                className="btn-secondary whitespace-nowrap !px-2.5 !py-1.5 text-xs"
                                onClick={() => openViewer(doc)}
                              >
                                View
                              </button>
                            )}
                            <a
                              href={downloadDocumentUrl(doc.id)}
                              className="btn-secondary whitespace-nowrap !px-2.5 !py-1.5 text-xs"
                              title="Download original file"
                            >
                              Download
                            </a>
                            <button
                              type="button"
                              className="btn-danger whitespace-nowrap !px-2.5 !py-1.5 text-xs"
                              onClick={() => handleDelete(doc)}
                              disabled={deletingId === doc.id}
                            >
                              {deletingId === doc.id ? "Deleting…" : "Delete"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {documents.total > documents.page_size && (
              <div className="mt-4 flex items-center justify-between text-sm">
                <span className="text-gray-500">
                  Page {documents.page} of {Math.ceil(documents.total / documents.page_size)} ·{" "}
                  {documents.total} documents
                </span>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-secondary !px-3 !py-1.5 text-xs"
                    disabled={documents.page <= 1}
                    onClick={() => setPage(documents.page - 1)}
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    className="btn-secondary !px-3 !py-1.5 text-xs"
                    disabled={documents.page >= Math.ceil(documents.total / documents.page_size)}
                    onClick={() => setPage(documents.page + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </section>

      {/* Extracted-content viewer (document detail) */}
      {viewerDoc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-navy-950/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-label={`Extracted content of ${viewerDoc.filename}`}
          onClick={closeViewer}
        >
          <div
            className="card max-h-[80vh] w-full max-w-3xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-gray-900">{viewerDoc.filename}</p>
                <p className="text-xs text-gray-500">
                  Extracted content ·{" "}
                  {viewerContent
                    ? `${viewerContent.sections.length} section${viewerContent.sections.length === 1 ? "" : "s"}`
                    : "loading…"}
                </p>
              </div>
              <button type="button" className="btn-secondary !px-2.5" onClick={closeViewer} aria-label="Close viewer">
                ✕
              </button>
            </div>
            <div className="max-h-[calc(80vh-3rem)] overflow-y-auto px-5 py-4">
              {viewerLoading && <StateBlock variant="loading" title="Loading extracted content…" />}
              {!viewerLoading && viewerError && (
                <StateBlock
                  variant="error"
                  title="Cannot load content"
                  description={viewerError}
                  action={
                    <button type="button" className="btn-primary" onClick={() => openViewer(viewerDoc)}>
                      Retry
                    </button>
                  }
                />
              )}
              {!viewerLoading && !viewerError && viewerContent && viewerContent.sections.length === 0 && (
                <StateBlock
                  variant="empty"
                  title="No extractable content"
                  description="Extraction completed but produced no text or structured units."
                />
              )}
              {!viewerLoading && !viewerError && viewerContent && viewerContent.sections.length > 0 && (
                <div className="space-y-4">
                  {viewerContent.sections.map((section) => (
                    <div key={`${section.type}-${section.number}`} className="rounded-md border border-gray-200">
                      <div className="flex items-center justify-between gap-2 border-b border-gray-100 bg-gray-50 px-3 py-2">
                        <span className="text-xs font-semibold text-gray-700">
                          {section.type} {section.number}
                          {section.reference && section.reference !== `${section.type} ${section.number}`
                            ? ` · ${section.reference}`
                            : ""}
                        </span>
                        <StatusBadge status={section.extraction_status} />
                      </div>
                      <div className="px-3 py-2.5">
                        {section.ocr && (
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <Badge tone={section.ocr.review_required ? "warn" : "ok"}>
                              {section.ocr.review_required
                                ? `Review required (${section.ocr.low_confidence_count ?? 0} low-confidence box${(section.ocr.low_confidence_count ?? 0) === 1 ? "" : "es"})`
                                : "OCR confident"}
                            </Badge>
                            {typeof section.ocr.confidence === "number" && (
                              <span className="text-[10px] text-gray-500">
                                mean confidence {(section.ocr.confidence * 100).toFixed(1)}%
                              </span>
                            )}
                            <span className="text-[10px] text-gray-400">
                              {section.ocr.engine} {section.ocr.engine_version} ·{" "}
                              {section.ocr.bounding_boxes?.length ?? 0} boxes
                            </span>
                          </div>
                        )}
                        {section.type === "image" && section.extraction_status === "ocr_required" ? (
                          <p className="text-xs text-gray-500">
                            Image ({section.structured?.format as string ?? "unknown"},{" "}
                            {section.structured?.width as number ?? "?"}×{section.structured?.height as number ?? "?"}
                            {" "}px, mode {section.structured?.mode as string ?? "?"}) — OCR engine unavailable in this
                            environment.
                          </p>
                        ) : section.structured?.rows ? (
                          <SheetPreview structured={section.structured} />
                        ) : (
                          <pre className="whitespace-pre-wrap break-words font-sans text-xs text-gray-800">
                            {section.text ?? "(no text — flagged for OCR)"}
                          </pre>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function SheetPreview({ structured }: { structured: Record<string, unknown> }) {
  const rows = (structured.rows as unknown[][] | undefined) ?? [];
  const previewRows = rows.slice(0, 10);
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <tbody>
            {previewRows.map((row, r) => (
              <tr key={r} className={r === 0 ? "bg-gray-50 font-semibold text-gray-800" : "text-gray-700"}>
                {row.map((cell, c) => (
                  <td key={c} className="whitespace-nowrap border-b border-gray-100 px-2.5 py-1.5">
                    {cell === null || cell === undefined ? (
                      <span className="text-gray-300">—</span>
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 10 && (
        <p className="mt-2 text-[11px] text-gray-400">
          Showing first 10 of {rows.length} rows (full data stored in the database).
        </p>
      )}
    </div>
  );
}
