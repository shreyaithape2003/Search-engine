# EduSearch

EduSearch is a specialized search experience for discovering publicly
accessible educational resources across school, university, professional,
technical, academic, and research domains. It is a focused vertical search
engine, not a replacement for general-purpose search engines.

## Phase 1 status

The project foundation is in place: a small FastAPI backend, a health check,
and a responsive landing/search screen. Search itself is not implemented yet;
submitting the form displays a clear "coming soon" message and does not show
fabricated results.

## Technology stack

- Python 3.12+
- FastAPI and Pydantic Settings
- Uvicorn
- pytest and HTTPX
- Plain HTML, CSS, and JavaScript for the initial UI

## Local setup

From the repository root, create and activate a virtual environment, then
install the dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, use the virtual
environment's Python executable directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use that same executable in place of `python` in the run and test commands
below.

## Run the backend

```powershell
python -m uvicorn app.main:app --reload
```

The API runs at <http://127.0.0.1:8000>. Check
<http://127.0.0.1:8000/health> for the service health response and open
<http://127.0.0.1:8000/docs> for interactive OpenAPI documentation.

The backend accepts `EDUSEARCH_SERVICE_NAME` and `EDUSEARCH_LOG_LEVEL`
environment variables. The defaults are `EduSearch` and `INFO`.

## Open the UI

Open `frontend/index.html` in a browser. The landing page is a static frontend
and does not need a separate server in this phase. The search form is
presentation-only until a later milestone adds search functionality.

## Run tests

```powershell
python -m pytest
```

## Current limitations

- No search endpoint, search index, or real search results.
- No crawler, persistence, ranking, semantic search, or AI features.
- The landing page is static and is not served by FastAPI.

## Upcoming phases

Later milestones can add search behavior, educational content ingestion,
indexing and retrieval, evaluation, and additional product capabilities. Each
will be implemented incrementally; none is included in Phase 1.
