import { useCallback, useRef, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import {
  deleteDocument,
  downloadDocumentUrl,
  fetchDocumentContent,
  processDocument,
  uploadDocument,
} from "@/lib/documentApi";
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
      return "bg-blue-50 text-blue-700 border-blue-200";
    case "xlsx":
      return "bg-emerald-50 text-emerald-700 border-emerald-200";
    case "image":
      return "bg-purple-50 text-purple-700 border-purple-200";
    default:
      return "bg-gray-100 text-gray-700 border-gray-200";
  }
}

function statusPill(status: string): { classes: string; label: string } {
  switch (status) {
    case "processed":
      return { classes: "bg-emerald-50 text-emerald-700 border-emerald-200", label: "Processed" };
    case "processing":
      return { classes: "bg-blue-50 text-blue-700 border-blue-200", label: "Processing…" };
    case "failed":
      return { classes: "bg-red-50 text-red-700 border-red-200", label: "Failed" };
    case "queued":
      return { classes: "bg-amber-50 text-amber-700 border-amber-200", label: "Queued" };
    default:
      return { classes: "bg-gray-100 text-gray-600 border-gray-200", label: "Uploaded" };
  }
}

/** Documents page: upload, processing and extracted-content viewer (Steps 3–4). */
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
  const fileInputRef = useRef<HTMLInputElement>(null);

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
          setUploadSuccess(`"${doc.filename}" processed (${status.extraction_status}).`);
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
        title="Documents"
        description="Upload, process and inspect geological, mining and production reports"
      />

      {/* Upload panel */}
      <section aria-label="Upload a document" className="mb-8">
        <div
          className={`card flex flex-col items-center justify-center border-dashed px-6 py-10 text-center transition-colors ${
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
              <p className="text-sm font-medium text-gray-700">
                Drag &amp; drop a file here, or
              </p>
              <button type="button" className="btn-primary mt-3" onClick={() => fileInputRef.current?.click()}>
                Choose file
              </button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept={SUPPORTED_FILE_TYPES}
                onChange={(e) => handleUpload(e.target.files)}
              />
              <p className="mt-3 text-xs text-gray-500">
                Supported: PDF, DOCX, XLSX, XLS, PNG, JPG, JPEG · Max {MAX_UPLOAD_SIZE_MB} MB per file
              </p>
            </>
          )}
        </div>

        {uploadSuccess && (
          <div
            role="status"
            className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800"
          >
            {uploadSuccess}
            <button type="button" className="ml-3 text-emerald-700 underline" onClick={() => setUploadSuccess(null)}>
              dismiss
            </button>
          </div>
        )}
        {uploadError && (
          <div
            role="alert"
            className="mt-3 rounded-md border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700"
          >
            {uploadError}
            <button type="button" className="ml-3 text-red-600 underline" onClick={() => setUploadError(null)}>
              dismiss
            </button>
          </div>
        )}
      </section>

      {/* Document list */}
      <section aria-label="Uploaded documents">
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
          Uploaded documents
        </h3>

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
            title="No documents uploaded yet"
            description="Upload a PDF, DOCX, XLSX, XLS or image file to get started."
          />
        )}

        {!isLoading && !isError && documents && documents.items.length > 0 && (
          <>
            <div className="card divide-y divide-gray-100">
              {documents.items.map((doc) => {
                const pill = statusPill(doc.status);
                const isProcessingRow = processingIds.has(doc.id) || doc.status === "processing";
                return (
                  <div key={doc.id} className="px-5 py-3.5">
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${typeBadge(doc.document_type)}`}
                          >
                            {doc.document_type}
                          </span>
                          <p className="truncate text-sm font-medium text-gray-900">{doc.filename}</p>
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${pill.classes}`}>
                            {pill.label}
                          </span>
                        </div>
                        <p className="mt-0.5 text-xs text-gray-500">
                          Uploaded {formatDateTime(doc.uploaded_at)}
                          {doc.status === "processed" && " · extraction complete"}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          className="btn-primary !px-2.5 !py-1.5 text-xs"
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
                            className="btn-secondary !px-2.5 !py-1.5 text-xs"
                            onClick={() => openViewer(doc)}
                          >
                            View content
                          </button>
                        )}
                        <a
                          href={downloadDocumentUrl(doc.id)}
                          className="btn-secondary !px-2.5 !py-1.5 text-xs"
                          title="Download original file"
                        >
                          Download
                        </a>
                        <button
                          type="button"
                          className="btn-secondary !px-2.5 !py-1.5 text-xs !text-red-600 hover:!bg-red-50"
                          onClick={() => handleDelete(doc)}
                          disabled={deletingId === doc.id}
                        >
                          {deletingId === doc.id ? "Deleting…" : "Delete"}
                        </button>
                      </div>
                    </div>
                    {doc.error_message && doc.status === "failed" && (
                      <p className="mt-2 rounded bg-red-50 px-2.5 py-1.5 text-xs text-red-700">
                        {doc.error_message}
                      </p>
                    )}
                    {rowErrors[doc.id] && (
                      <p className="mt-2 rounded bg-red-50 px-2.5 py-1.5 text-xs text-red-700">
                        {rowErrors[doc.id]}
                      </p>
                    )}
                  </div>
                );
              })}
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

      {/* Extracted-content viewer */}
      {viewerDoc && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/50 p-4"
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
                  description="Extraction completed but produced no text or structured units. This file may need the future OCR step."
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
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                            section.extraction_status === "extracted"
                              ? "bg-emerald-100 text-emerald-700"
                              : section.extraction_status === "no_text"
                                ? "bg-amber-100 text-amber-700"
                                : section.extraction_status === "ocr_required"
                                  ? "bg-purple-100 text-purple-700"
                                  : "bg-red-100 text-red-700"
                          }`}
                        >
                          {section.extraction_status.replace("_", " ")}
                        </span>
                      </div>
                      <div className="px-3 py-2.5">
                        {section.ocr && (
                          <div className="mb-2 flex flex-wrap items-center gap-2">
                            <span
                              className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                                section.ocr.review_required
                                  ? "bg-amber-100 text-amber-800"
                                  : "bg-emerald-100 text-emerald-700"
                              }`}
                            >
                              {section.ocr.review_required
                                ? `Review required (${section.ocr.low_confidence_count ?? 0} low-confidence box${(section.ocr.low_confidence_count ?? 0) === 1 ? "" : "es"})`
                                : "OCR confident"}
                            </span>
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
                            {section.structured?.width as number ?? "?"}×{section.structured?.height as number ?? "?"}{" "}
                            px, mode {section.structured?.mode as string ?? "?"}) — OCR engine unavailable in this
                            environment.
                          </p>
                        ) : section.structured?.rows ? (
                          <SheetPreview structured={section.structured} />
                        ) : (
                          <pre className="whitespace-pre-wrap break-words font-sans text-xs text-gray-800">
                            {section.text ?? "(no text — flagged for the future OCR step)"}
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
