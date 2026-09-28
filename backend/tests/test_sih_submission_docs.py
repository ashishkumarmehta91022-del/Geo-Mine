"""Step 19 submission-package tests — DB-free.

Validates the SIH submission documentation set: presence of every required
document, problem-statement coverage with honest status vocabulary,
objectives/objectives-matrix structure, live-route-only demo screen map,
checklist structure, presentation outline shape, banned-claim audit across
ALL docs, synthetic-data notices, and resolving documentation links.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"

REQUIRED_DOCS = (
    "SIH_PS_ALIGNMENT.md",
    "SIH_OBJECTIVES_MATRIX.md",
    "SIH_FINAL_PRESENTATION_OUTLINE.md",
    "SIH_FINAL_DEMO_SCRIPT.md",
    "SIH_DEMO_SCREEN_MAP.md",
    "SIH_JUDGE_EVIDENCE_CHECKLIST.md",
    "SIH_DEMO_FAILURE_CHECKLIST.md",
    "SIH_TECHNICAL_CHEAT_SHEET.md",
    "SIH_IMPLEMENTED_VS_FUTURE.md",
    "SIH_90_SECOND_PITCH.md",
    "SIH_VALUE_PROPOSITION.md",
    "SIH_TECHNICAL_NOVELTY.md",
    "SIH_FINAL_STORY.md",
    "SIH_DEMO_RUNBOOK.md",
    "ARCHITECTURE.md",
)

LIVE_ROUTES = (
    "/dashboard", "/documents", "/validation", "/knowledge",
    "/ai-query", "/topic-intelligence", "/data-explorer", "/report-generator",
)

PLACEHOLDER_ROUTES = ("/review-queue", "/audit-logs", "/settings")

PS_STATUSES = ("IMPLEMENTED", "PARTIALLY IMPLEMENTED", "FUTURE", "NOT VERIFIED")

PS_TOPICS = (
    "Scanned PDFs", "Digital documents", "Spreadsheets", "Images",
    "Historical archives", "AI-assisted document processing", "Reporting",
    "Validation", "Consistency", "Traceability", "Historical / current data",
    "AI query-response", "Topic identification", "Automated reporting",
    "Scalability toward CIL subsidiaries",
)

BANNED_CLAIMS = re.compile(
    r"100\s*%|zero hallucination|fully production[- ]ready|guaranteed "
    r"(scal|secur)|\b\d+\s*%\s*(faster|reduction|improvement|accurate)|"
    r"state-of-the-art",
    re.I,
)


def _doc(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


# --- presence (Phase 15) -----------------------------------------------------------


def test_all_required_submission_documents_exist():
    for name in REQUIRED_DOCS:
        assert (DOCS / name).is_file(), name


# --- problem-statement alignment (Phase 2) ------------------------------------------


def test_ps_alignment_covers_all_required_topics_with_honest_statuses():
    text = _doc("SIH_PS_ALIGNMENT.md")
    for topic in PS_TOPICS:
        assert topic in text, topic
    statuses = re.findall(r"\| (IMPLEMENTED|PARTIALLY IMPLEMENTED|FUTURE|NOT VERIFIED)", text)
    assert len(statuses) >= 15
    assert set(statuses) <= set(PS_STATUSES)
    assert "PARTIALLY IMPLEMENTED" in text and "NOT VERIFIED" in text  # honesty kept
    assert "merely because it is planned" in " ".join(
        text.replace(">", " ").split()
    ), "anti-inflation rule stated"


# --- objectives matrix (Phase 3) -----------------------------------------------------


def test_objectives_matrix_covers_ten_objectives_with_all_columns():
    text = _doc("SIH_OBJECTIVES_MATRIX.md")
    for header in ("Objective", "Feature", "Technical implementation",
                   "Demo screen", "Evidence / test"):
        assert header in text, header
    for objective in ("Automated document processing", "Structured extraction",
                      "Validation", "Traceability", "Retrieval", "AI query-response",
                      "Topic intelligence", "Automated report generation",
                      "Analytics", "Auditability"):
        assert objective in text, objective


# --- demo screen map over live routes only (Phase 7 / 15) ----------------------------


def test_screen_map_uses_only_live_routes_and_avoids_placeholders():
    text = _doc("SIH_DEMO_SCREEN_MAP.md")
    app_tsx = (REPO_ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    table_text = "\n".join(
        line for line in text.splitlines() if line.startswith("|")
    )
    used = set(re.findall(r"`(/[a-z-]+)`", table_text))
    assert used <= set(LIVE_ROUTES), used - set(LIVE_ROUTES)
    for route in used:
        assert f'path="{route}"' in app_tsx, route
    # Placeholders may appear ONLY in the explicit warning line, never as a
    # presented screen (no table row references them):
    for banned in PLACEHOLDER_ROUTES:
        assert not re.search(r"^\| .*" + re.escape(banned), text, re.M), banned
    assert "never presented as live features" in text  # routing note preserved


# --- failure + evidence checklists (Phases 11/12) -------------------------------------


def test_failure_checklist_covers_ten_scenarios_with_recovery_structure():
    text = _doc("SIH_DEMO_FAILURE_CHECKLIST.md")
    lowered = text.lower()
    for scenario in ("postgresql unavailable", "backend unavailable",
                     "frontend unavailable", "ocr failure", "embedding unavailable",
                     "llm unavailable", "report generation failure",
                     "validation conflict", "empty search results",
                     "demo data unavailable"):
        assert scenario in lowered, scenario
    for field in ("SYMPTOM", "CHECK", "RECOVERY", "SAY"):
        assert text.count(f"**{field}:**") >= 10, field


def test_evidence_checklist_maps_twelve_items_to_screens_and_apis():
    text = _doc("SIH_JUDGE_EVIDENCE_CHECKLIST.md")
    for evidence in ("Uploaded document", "Extracted text", "OCR result",
                     "Source reference", "Validation result", "Review-required conflict",
                     "Search result with provenance", "AI evidence with citations",
                     "Topic/keyword output", "KPI / trend / comparison",
                     "Generated DOCX", "Audit activity"):
        assert evidence in text, evidence
    assert text.count("Backing API") == 1 and "/api/" in text


# --- presentation outline + final story (Phases 8/16/17) ------------------------------


def test_presentation_outline_has_twelve_slides_with_visual_and_say():
    text = _doc("SIH_FINAL_PRESENTATION_OUTLINE.md")
    slides = re.findall(r"### Slide (\d+) — ", text)
    assert [int(n) for n in slides] == list(range(1, 13))
    assert text.count("- **Visual:**") == 12
    assert text.count("- **Say:**") == 12
    assert "10–12 minutes" in text and "≈5 minutes" in text  # pacing guidance


def test_final_story_has_all_eleven_sections_and_usp():
    text = _doc("SIH_FINAL_STORY.md")
    for section in ("The Problem", "Why Existing Workflow Is Difficult", "Our Solution",
                    "How the Pipeline Works", "Where AI Is Used",
                    "How We Prevent Unverified Answers", "How Conflicts Are Handled",
                    "How Reports Are Generated", "Why the Solution Can Scale",
                    "Current Limitations", "Final USP"):
        assert re.search(rf"^#+\s*\d*\.?\s*{re.escape(section)}\s*$", text, re.M), section
    assert "From Unstructured Documents to Verified, Traceable" in " ".join(
        text.split()
    ) or "From Unstructured Documents to Verified, Traceable" in text


# --- value proposition + novelty (Phases 4/5) ------------------------------------------


def test_value_proposition_states_no_benchmark_and_has_all_sections():
    text = _doc("SIH_VALUE_PROPOSITION.md")
    for section in ("Current Problem", "Proposed Solution", "What Changes for the User",
                    "Why AI Helps", "Why Validation Matters", "Why Traceability Matters",
                    "Why This Architecture Can Scale", "Current Limitations"):
        assert f"## {section}" in text, section
    assert ("Quantitative improvement is not claimed because production "
            "baseline measurements are not yet available.") in " ".join(text.split())


def test_novelty_audit_rejects_library_innovation_framing():
    text = _doc("SIH_TECHNICAL_NOVELTY.md")
    assert "are off-the-shelf and are **not** claimed as innovations" in text
    for characteristic in ("Deterministic extraction before AI", "Validation-aware RAG",
                           "Evidence objects", "Conflict preservation", "Provenance continuity",
                           "hybrid retrieval", "Local embeddings", "Structured-data-first reporting",
                           "Human review", "Rebuildable knowledge index", "Modular provider"):
        assert characteristic.lower() in text.lower(), characteristic


# --- synthetic data + claims audit across ALL docs (Phases 8/10) ------------------------


def test_synthetic_data_notices_present_in_submission_docs():
    notice = "synthetic"
    for name in ("SIH_VALUE_PROPOSITION.md", "SIH_FINAL_STORY.md",
                 "SIH_DEMO_SCREEN_MAP.md", "SIH_FINAL_DEMO_SCRIPT.md"):
        assert notice in _doc(name).lower(), name


def test_no_banned_claims_across_entire_documentation_set():
    for doc in sorted(DOCS.glob("*.md")):
        match = BANNED_CLAIMS.search(doc.read_text(encoding="utf-8"))
        assert match is None, (doc.name, match.group(0) if match else "")


def test_no_official_cmpdi_cil_figures_presented_as_real():
    for doc in sorted(DOCS.glob("*.md")):
        text = doc.read_text(encoding="utf-8")
        for match in re.finditer(r"official CMPDI/CIL", text):
            window = text[max(0, match.start() - 80):match.end()].lower()
            assert any(neg in window for neg in
                       ("not", "never", "do not", "only")), (doc.name, window)


# --- README documentation index + link resolution (Phases 14/15) ------------------------


def test_readme_has_submission_index_linking_all_documents():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "## SIH Submission & Demo Documentation" in readme
    for name in REQUIRED_DOCS:
        assert f"](docs/{name})" in readme, name


def test_all_markdown_links_in_sih_docs_resolve_to_files():
    for doc in sorted(DOCS.glob("*.md")):
        text = doc.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#]+?\.md)\)", text):
            assert (DOCS / target).is_file() or (REPO_ROOT / target).is_file(), (
                doc.name, target
            )
