import { useCallback, useRef, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { downloadDocumentUrl, deleteDocument, uploadDocument } from "@/lib/documentApi";
import { useDocuments } from "@/hooks/useDocuments";
import {
  MAX_UPLOAD_SIZE_MB,
  SUPPORTED_FILE_TYPES,
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

/** Documents page: upload interface + uploaded document list (Step 3 scope). */
export default function DocumentsPage() {
  const { documents, isLoading, isError, error, setPage, refetch } = useDocuments();
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
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
        const message =
          cause instanceof Error ? cause.message : "Upload failed unexpectedly.";
        setUploadError(message);
      } finally {
        setIsUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
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

  return (
    <>
      <PageHeader
        title="Documents"
        description="Upload and manage geological, mining and production reports"
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
            description="Upload a PDF, DOCX, XLSX, XLS or image file to get started. Processing (OCR, extraction) arrives in later steps."
          />
        )}

        {!isLoading && !isError && documents && documents.items.length > 0 && (
          <>
            <div className="card divide-y divide-gray-100">
              {documents.items.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between gap-4 px-5 py-3.5">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase ${typeBadge(doc.document_type)}`}
                      >
                        {doc.document_type}
                      </span>
                      <p className="truncate text-sm font-medium text-gray-900">{doc.filename}</p>
                    </div>
                    <p className="mt-0.5 text-xs text-gray-500">
                      {formatDateTime(doc.uploaded_at)} · status: {doc.status}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
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
              ))}
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
    </>
  );
}
