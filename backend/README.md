# CMPDI AI Reporting Platform — Backend

FastAPI foundation for the SIH 2026 project (SIH26023).

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows (PowerShell: .venv\Scripts\Activate.ps1)
source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
copy ..\.env.example .env       # Windows (macOS/Linux: cp ..\.env.example .env)
```

## Run

```bash
uvicorn app.main:app --reload
```

Interactive API docs: <http://localhost:8000/docs>

## Test

```bash
pytest
```

The test suite runs without PostgreSQL or any AI credentials.
