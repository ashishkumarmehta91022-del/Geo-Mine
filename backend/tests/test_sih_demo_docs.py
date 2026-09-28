"""Step 18 judge-readiness documentation tests — DB-free.

Enforces: presence and structure of the SIH demo script / pitch / cheat
sheet / implemented-vs-future matrix, route consistency of the demo flow
with the real frontend routes, synthetic-data warnings, honest-claims
guardrails, and cheat-sheet versions matching the verified dependency pins.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"

SYNTHETIC_NOTICE = (
    "All values shown in this demonstration are synthetic demonstration "
    "data and do not represent official CMPDI/CIL figures."
)

FORBIDDEN_OVERCLAIMS = (
    "100% accurate",
    "zero hallucinations",
    "fully production ready",
    "state-of-the-art",
)

LIVE_DEMO_ROUTES = (
    "/dashboard", "/documents", "/validation", "/knowledge",
    "/ai-query", "/topic-intelligence", "/data-explorer", "/report-generator",
)

DEMO_ONLY_ROUTES = {
    "fastapi": "0.141.1", "uvicorn": "0.54.0", "pydantic": "2.13.5",
    "pydantic-settings": "2.15.0", "sqlalchemy": "2.1.1", "alembic": "1.20.0",
    "pymupdf": "1.28.2", "python-docx": "1.2.0", "openpyxl": "3.1.5",
    "xlrd": "2.0.2", "pillow": "12.3.0", "rapidocr-onnxruntime": "1.2.3",
    "onnxruntime": "1.30.0", "fastembed": "0.8.1",
}


def _doc(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


# --- demo documentation presence & structure (Phases 2/3/9) -----------------------


def test_final_demo_script_exists_with_storyline_and_ten_steps():
    text = _doc("SIH_FINAL_DEMO_SCRIPT.md")
    assert "UNSTRUCTURED DATA → DOCUMENT INGESTION → OCR / EXTRACTION" in text
    for step in ("Step 1 — Dashboard", "Step 2 — Document", "Step 3 — Extraction",
                 "Step 4 — Validation", "Step 5 — Knowledge Search",
                 "Step 6 — AI Query", "Step 7 — Topic Intelligence",
                 "Step 8 — Analytics", "Step 9 — Report", "Step 10 — Audit"):
        assert step in text, step
    assert "5-Minute Storyline" in text and "Opening — 20 seconds" in text


def test_demo_script_contains_twenty_judge_questions_and_architecture():
    text = _doc("SIH_FINAL_DEMO_SCRIPT.md")
    assert "## Expected Judge Questions" in text
    for topic in ("main innovation", "hallucinate", "conflicting documents",
                  "hybrid search", "LLM is unavailable", "PostgreSQL is unavailable",
                  "next production step"):
        assert topic in text, topic
    assert "INPUT" in text and "PROCESS" in text and "OUTPUT" in text
    for stage in ("Ingestion", "Extraction/OCR", "Structured Records",
                  "Validation", "Knowledge Index", "Evidence-Grounded AI",
                  "Reports", "Audit"):
        assert stage in text, stage


def test_failure_demonstration_preserves_both_conflicting_values():
    text = _doc("SIH_FINAL_DEMO_SCRIPT.md")
    assert "Source A → 1200" in text and "Source B → 1350" in text
    assert "REVIEW REQUIRED" in text
    assert "no automatic winner" in text


# --- synthetic-data safety (Phase 8) ----------------------------------------------


def test_synthetic_data_warning_present_in_demo_script():
    text = " ".join(_doc("SIH_FINAL_DEMO_SCRIPT.md").replace(">", " ").split())
    assert SYNTHETIC_NOTICE in text
    assert "DEMO_borehole_log.pdf" in text  # DEMO_ labels actually referenced


def test_no_real_cmpdi_cil_figures_in_demo_docs():
    for name in ("SIH_FINAL_DEMO_SCRIPT.md", "SIH_90_SECOND_PITCH.md",
                 "SIH_IMPLEMENTED_VS_FUTURE.md", "SIH_TECHNICAL_CHEAT_SHEET.md"):
        text = _doc(name)
        # The only permitted mention is the disclaimer itself (never figures).
        assert not re.search(r"CMPDI/CIL figure[s]?\s*[:=]\s*\d", text)
        assert "1200" in _doc("SIH_FINAL_DEMO_SCRIPT.md")  # synthetic demo values only


# --- implemented-vs-future matrix accuracy (Phase 12) ------------------------------


def test_matrix_rows_mark_future_clearly():
    text = _doc("SIH_IMPLEMENTED_VS_FUTURE.md")
    rows = [line for line in text.splitlines() if line.startswith("| ") and "---" not in line]
    assert len(rows) > 10  # header + capability rows
    statuses = [cells[1].strip() for cells in
                (row.split("|")[1:-1] for row in rows[1:])]
    assert any(status == "Future" for status in statuses)      # honesty kept
    assert all(status in ("Implemented", "Future",
                          "Implemented (statically verified)")
               for status in statuses)


def test_matrix_implemented_evidence_paths_exist_in_repo():
    text = _doc("SIH_IMPLEMENTED_VS_FUTURE.md")
    for row in text.splitlines():
        if not row.startswith("| ") or "---" in row:
            continue
        cells = [c.strip() for c in row.split("|")[1:-1]]
        if len(cells) < 3 or cells[0] == "Capability":
            continue
        status = cells[1]
        if not status.startswith("Implemented"):
            continue
        for token in re.findall(r"`([^`]+)`", cells[2]):
            token = re.sub(r"^(GET|POST)\s+", "", token)
            looks_like_path = token.endswith(
                (".py", ".yml", ".txt", ".json", ".ts", ".tsx")
            ) or token.startswith(("app/", "scripts/", "frontend/", "backend/", "docs/"))
            if not looks_like_path:
                continue
            assert (REPO_ROOT / "backend" / token).exists() or (
                REPO_ROOT / token
            ).exists(), token


# --- pitch presence, length and honest claims (Phases 13/14) -----------------------


def test_pitch_has_nine_part_structure_and_elevator_version():
    text = _doc("SIH_90_SECOND_PITCH.md")
    for part in ("Problem", "Current limitation", "Solution", "AI components",
                 "Validation", "Traceability", "Business/administrative value",
                 "Scalability", "USP"):
        assert part in text, part
    assert "30-Second Elevator Version" in text
    block = re.search(r"30-Second Elevator Version.*?\n((?:> .*\n)+)", text, re.S)
    assert block, "elevator pitch blockquote missing"
    words = len(re.sub(r"[>\s]+", " ", block.group(1)).split())
    assert words <= 115, f"elevator version too long: {words} words"
    assert "From Unstructured Documents to Verified, Traceable" in text


def test_docs_avoid_exaggerated_claims():
    for name in ("SIH_FINAL_DEMO_SCRIPT.md", "SIH_90_SECOND_PITCH.md",
                 "SIH_IMPLEMENTED_VS_FUTURE.md", "SIH_TECHNICAL_CHEAT_SHEET.md"):
        lowered = _doc(name).lower()
        for phrase in FORBIDDEN_OVERCLAIMS:
            assert phrase not in lowered, (name, phrase)


# --- demo route consistency (Phase 16) ---------------------------------------------


def test_every_live_demo_route_exists_in_the_frontend():
    app_tsx = (REPO_ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    for route in LIVE_DEMO_ROUTES:
        assert f'path="{route}"' in app_tsx, route


def test_demo_flow_avoids_placeholder_routes():
    """/review-queue, /audit-logs, /settings are placeholders; the demo flow
    routes judges to the live equivalents instead."""
    text = _doc("SIH_FINAL_DEMO_SCRIPT.md")
    for route in ('Navigate to `/review-queue`', 'Navigate to `/audit-logs`',
                  'Navigate to `/settings`', "Route: `/review-queue`"):
        assert route not in text, route
    assert "do **not** click in the demo" in text  # placeholders are flagged


# --- cheat sheet version accuracy (Phase 15) ----------------------------------------


def test_cheat_sheet_versions_match_verified_pins():
    cheat = _doc("SIH_TECHNICAL_CHEAT_SHEET.md").lower()
    constraints = "\n".join([
        (REPO_ROOT / "backend" / "constraints.txt").read_text(encoding="utf-8"),
        (REPO_ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8"),
    ])
    for package, pin in DEMO_ONLY_ROUTES.items():
        pinned = f"{package}=={pin}"
        assert pinned in constraints, pinned       # pin is real
        assert pin in cheat, (package, pin)         # cheat sheet cites it
    package_json = (REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    for dependency in ("react", "vite", "react-router-dom", "tailwindcss", "typescript"):
        assert f'"{dependency}"' in package_json
        base = dependency.split("-")[0]
        assert base in cheat or dependency in cheat


def test_cheat_sheet_states_honest_limitations():
    text = _doc("SIH_TECHNICAL_CHEAT_SHEET.md")
    assert "No authentication/RBAC" in text
    assert "NOT VERIFIED" in text  # Docker/PostgreSQL runtime honesty
