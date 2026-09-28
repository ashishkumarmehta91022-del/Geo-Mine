import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/ui/PageHeader";
import StateBlock from "@/components/ui/StateBlock";
import { listDocuments } from "@/lib/documentApi";
import {
  fetchCorpusIntelligence,
  fetchDocumentIntelligence,
  summarizeDocument,
} from "@/lib/intelligenceApi";
import type {
  DocumentSummary,
  IntelligenceResponse,
  WordCloudTerm,
} from "@/types/intelligence";

const inputClass =
  "w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none";

interface DocumentOption {
  id: number;
  filename: string;
}

/** Lightweight inline-SVG-free word cloud: scaled term list (data-driven). */
function WordCloud({ terms }: { terms: WordCloudTerm[] }) {
  if (terms.length === 0) return null;
  const maxSize = 28;
  const minSize = 12;
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      {terms.map((term) => {
        const size = minSize + term.weight * (maxSize - minSize);
        return (
          <span
            key={term.term}
            title={`${term.display_term} — frequency ${term.frequency}, documents ${term.document_frequency}, weight ${term.weight.toFixed(2)}`}
            style={{ fontSize: `${size.toFixed(1)}px` }}
            className={`font-semibold ${term.weight > 0.66 ? "text-brand-700" : term.weight > 0.33 ? "text-brand-600" : "text-gray-500"}`}
          >
            {term.display_term}
          </span>
        );
      })}
    </div>
  );
}

function SourceList({ sources }: { sources: { document_id: number; page_number: number | null; source_reference: string | null }[] }) {
  if (sources.length === 0) return null;
  return (
    <p className="mt-1 text-[11px] text-gray-400">
      Sources:{" "}
      {sources.slice(0, 4).map((source, index) => (
        <span key={index} className="font-mono">
          doc {source.document_id}
          {source.page_number !== null ? ` · p${source.page_number}` : ""}
          {index < Math.min(sources.length, 4) - 1 ? ", " : ""}
        </span>
      ))}
      {sources.length > 4 && <span> +{sources.length - 4} more</span>}
    </p>
  );
}

/** Topic Intelligence (Step 13): deterministic derived intelligence. */
export default function TopicIntelligencePage() {
  const [documents, setDocuments] = useState<DocumentOption[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<number | null>(null);
  const [data, setData] = useState<IntelligenceResponse | null>(null);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isError, setIsError] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDocuments()
      .then((response) => {
        const options = (response.items ?? []).map((d) => ({
          id: d.id,
          filename: d.filename,
        }));
        setDocuments(options);
        if (options.length > 0) setSelectedDocument(options[0].id);
      })
      .catch(() => setDocuments([]));
  }, []);

  const load = useCallback(async (documentId: number | null) => {
    setIsLoading(true);
    setIsError(false);
    setError(null);
    setSummary(null);
    try {
      const result = documentId
        ? await fetchDocumentIntelligence(documentId)
        : await fetchCorpusIntelligence(null);
      setData(result);
      if (result.summary) setSummary(result.summary);
    } catch (cause: unknown) {
      setIsError(true);
      setError(cause instanceof Error ? cause.message : "Could not load intelligence.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load(selectedDocument);
  }, [load, selectedDocument]);

  const runSummarize = async () => {
    if (!selectedDocument) return;
    setIsSummarizing(true);
    try {
      const result = await summarizeDocument(selectedDocument, false);
      setSummary(result.summary);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Could not summarize.");
    } finally {
      setIsSummarizing(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Topic Intelligence"
        description="Deterministic keywords, phrases, topics and word-cloud data derived from the knowledge index — every term traces back to its source"
      />

      <section aria-label="Scope selection" className="card mb-6 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[240px] flex-1">
            <label className="mb-1 block text-xs font-semibold text-gray-600">
              Scope (document or whole corpus)
            </label>
            <select
              className={inputClass}
              value={selectedDocument ?? ""}
              onChange={(e) =>
                setSelectedDocument(e.target.value === "" ? null : Number(e.target.value))
              }
            >
              <option value="">Whole corpus (all indexed documents)</option>
              {documents.map((document) => (
                <option key={document.id} value={document.id}>
                  {document.filename}
                </option>
              ))}
            </select>
          </div>
          <button type="button" className="btn-primary" disabled={isLoading} onClick={() => load(selectedDocument)}>
            {isLoading ? "Analyzing…" : "Re-analyze"}
          </button>
          {selectedDocument && (
            <button type="button" className="btn-secondary" disabled={isSummarizing} onClick={runSummarize}>
              {isSummarizing ? "Summarizing…" : "Summarize document"}
            </button>
          )}
        </div>
        <p className="mt-2 text-xs text-gray-400">
          Topic labels are derived from corpus terms — they are not official CMPDI/CIL topic definitions.
          Click a topic term to search it in the Knowledge Base.
        </p>
      </section>

      {isLoading && <StateBlock variant="loading" title="Building intelligence…" />}
      {isError && (
        <StateBlock
          variant="error"
          title="Intelligence unavailable"
          description={error ?? undefined}
          action={
            <button type="button" className="btn-primary" onClick={() => load(selectedDocument)}>
              Retry
            </button>
          }
        />
      )}

      {!isLoading && !isError && data && (
        <>
          {summary && (
            <section aria-label="Document summary" className="card mb-6 p-4">
              <h2 className="text-sm font-semibold text-gray-700">
                Summary — {summary.document_name}
              </h2>
              <p className="mt-1 text-sm text-gray-600">{summary.summary_text}</p>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 font-semibold text-gray-600">
                  {summary.page_count} pages
                </span>
                <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 font-semibold text-gray-600">
                  {summary.record_count} records
                </span>
                {summary.warning_error_review_count > 0 && (
                  <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 font-semibold text-amber-700">
                    {summary.warning_error_review_count} review items
                  </span>
                )}
                {summary.corpus_truncated && (
                  <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 font-semibold text-amber-700">
                    corpus truncated (limits)
                  </span>
                )}
                <span className="rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 font-semibold text-emerald-700">
                  DETERMINISTIC
                </span>
              </div>
              {summary.key_metrics.length > 0 && (
                <div className="mt-3 overflow-x-auto">
                  <table className="min-w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-200 text-left font-semibold uppercase tracking-wide text-gray-500">
                        <th className="px-2 py-1.5">Entity</th>
                        <th className="px-2 py-1.5">Metric</th>
                        <th className="px-2 py-1.5">Raw value</th>
                        <th className="px-2 py-1.5">Unit</th>
                        <th className="px-2 py-1.5">Period</th>
                        <th className="px-2 py-1.5">Validation</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {summary.key_metrics.slice(0, 6).map((metric) => (
                        <tr key={metric.record_id} className="text-gray-700">
                          <td className="px-2 py-1.5 font-medium">{metric.entity ?? "—"}</td>
                          <td className="px-2 py-1.5 font-mono">{metric.metric ?? "—"}</td>
                          <td className="px-2 py-1.5 font-mono">{metric.value_raw ?? "—"}</td>
                          <td className="px-2 py-1.5">{metric.unit ?? "—"}</td>
                          <td className="px-2 py-1.5">{metric.reporting_period ?? "—"}</td>
                          <td className="px-2 py-1.5">{metric.validation_status ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}

          <section aria-label="Word cloud" className="card mb-6 p-4">
            <h2 className="mb-2 text-sm font-semibold text-gray-700">Word cloud (data-driven)</h2>
            <WordCloud terms={data.word_cloud} />
            {data.word_cloud.length === 0 && (
              <p className="text-sm text-gray-500">No terms met the frequency thresholds.</p>
            )}
          </section>

          <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <section aria-label="Topics" className="card p-4">
              <h2 className="mb-2 text-sm font-semibold text-gray-700">Topics</h2>
              {data.topics.length === 0 && (
                <p className="text-sm text-gray-500">No topics met the clustering thresholds.</p>
              )}
              <div className="space-y-3">
                {data.topics.map((topic) => (
                  <div key={topic.topic_id} className="rounded-md border border-gray-100 p-2">
                    <div className="flex items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold text-gray-800">{topic.label}</h3>
                      <span className="rounded border border-gray-200 bg-gray-50 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                        score {topic.score.toFixed(1)}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {topic.representative_terms.map((term) => (
                        <Link
                          key={term}
                          to={`/knowledge?q=${encodeURIComponent(term)}`}
                          className="rounded-full border border-brand-200 bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-100"
                          title={`Search "${term}" in the Knowledge Base`}
                        >
                          {term}
                        </Link>
                      ))}
                    </div>
                    <SourceList sources={topic.sources} />
                    <p className="mt-1 text-[10px] text-gray-400">
                      Documents: {topic.document_ids.join(", ") || "—"} · method: {topic.method}
                    </p>
                  </div>
                ))}
              </div>
            </section>

            <section aria-label="Topic document relationships" className="card p-4">
              <h2 className="mb-2 text-sm font-semibold text-gray-700">Topic ↔ Document relationships</h2>
              {data.topic_document_matches.length === 0 && (
                <p className="text-sm text-gray-500">No relationships computed yet.</p>
              )}
              <ul className="space-y-2">
                {data.topic_document_matches.slice(0, 12).map((match) => (
                  <li key={`${match.topic_id}-${match.document_id}`} className="text-sm text-gray-700">
                    <span className="font-semibold">{match.topic_label}</span>
                    {" → "}
                    <span className="font-mono text-xs">document {match.document_id}</span>
                    <span className="ml-1 text-xs text-gray-400">(score {match.score.toFixed(0)})</span>
                    <p className="text-[11px] text-gray-500">
                      supporting terms: {match.supporting_terms.slice(0, 5).join(", ")}
                    </p>
                    <SourceList sources={match.sources} />
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section aria-label="Key terms" className="card mb-6 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-2.5">Term</th>
                  <th className="px-4 py-2.5">Kind</th>
                  <th className="px-4 py-2.5">Frequency</th>
                  <th className="px-4 py-2.5">Documents</th>
                  <th className="px-4 py-2.5">Score</th>
                  <th className="px-4 py-2.5">Ranking signal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.keywords.slice(0, 15).map((keyword) => (
                  <tr key={`${keyword.kind}-${keyword.term}`} className="text-gray-700">
                    <td className="px-4 py-2.5 font-medium">{keyword.display_term}</td>
                    <td className="px-4 py-2.5 text-xs text-gray-500">{keyword.kind}</td>
                    <td className="px-4 py-2.5 font-mono">{keyword.frequency}</td>
                    <td className="px-4 py-2.5 font-mono">{keyword.document_frequency}</td>
                    <td className="px-4 py-2.5 font-mono">{keyword.score.toFixed(2)}</td>
                    <td className="px-4 py-2.5 text-xs text-gray-400">{keyword.score_reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.keywords.length === 0 && (
              <p className="p-4 text-sm text-gray-500">No keywords met the thresholds.</p>
            )}
          </section>

          {data.limitations.length > 0 && (
            <section aria-label="Limitations" className="card p-4">
              <h2 className="mb-1 text-sm font-semibold text-gray-700">Limitations</h2>
              <ul className="list-disc pl-5 text-xs text-gray-500">
                {data.limitations.map((limitation) => (
                  <li key={limitation}>{limitation}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      {!isLoading && !isError && !data && documents.length === 0 && (
        <StateBlock
          variant="empty"
          title="No documents to analyze"
          description="Upload and process documents first — intelligence is derived from the extracted, indexed content."
        />
      )}
    </>
  );
}
