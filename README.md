# EduSearch

EduSearch is a specialized search experience for discovering publicly
accessible educational resources across school, university, professional,
technical, academic, and research domains. It is a focused vertical search
engine, not a replacement for general-purpose search engines.

## Phase 2 status

Phase 1 provides the FastAPI health check and a responsive landing/search
screen. Phase 2 adds the document model, SQLite persistence, Pydantic data
schemas, a focused repository, and deterministic development sample data.
EduSearch still does not crawl websites or perform searches.

## Technology stack

- Python 3.12+
- FastAPI and Pydantic Settings
- SQLAlchemy 2.x and SQLite
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

The backend accepts `EDUSEARCH_SERVICE_NAME`, `EDUSEARCH_LOG_LEVEL`, and
`EDUSEARCH_DATABASE_URL` environment variables. Defaults are `EduSearch`,
`INFO`, and `sqlite:///./edusearch.db`. The default database is a local file
in the current working directory; SQLite is included with Python and does not
need a separate server or installation.

## Phase 2 data layer

The storage path is:

```text
FastAPI
  -> DocumentRepository
  -> SQLAlchemy 2.x session
  -> SQLite
```

`Document` stores the resource URL and canonical URL, its derived domain,
educational metadata, text, ordered headings, a content hash, and separate
source/EduSearch timestamps. Headings are a JSON array of strings in one
SQLite column; this preserves heading order without introducing a separate
table. URL and non-null canonical URL values are unique. `content_hash` is
indexed, not unique, so storing identical content at multiple URLs is not
prematurely prohibited.

The `DocumentRepository` accepts a SQLAlchemy session and provides
`create`, `get_by_id`, `get_by_url`, `list`, `update`, and `delete`. Duplicate
URL or canonical URL writes are reported as `DuplicateDocumentError`. URL
values are validated as HTTP(S) URLs in Pydantic schemas. `created_at` and
`updated_at` are EduSearch timestamps; `source_updated_at` describes the
original resource when that metadata is known. Stored timestamps are
normalized to timezone-aware UTC values.

The engine and session factory are configured in `app.db.database`. Importing
the app does not create a database or tables. Initialize the schema explicitly
from the repository root:

```powershell
python -m app.db.init_db
```

For a custom location, set `EDUSEARCH_DATABASE_URL` before running that
command, for example:

```powershell
$env:EDUSEARCH_DATABASE_URL = "sqlite:///./local-edusearch.db"
python -m app.db.init_db
```

The same configuration is used by the optional sample-data command:

```powershell
python -m app.db.seed
```

This adds four deterministic development examples (university course,
technical documentation, science education, and professional learning).
Repeated runs skip existing sample URLs; the data is text and metadata only
and does not require network access. The default `edusearch.db` file is ignored
by Git.

## Example development workflow

```powershell
python -m pip install -r requirements.txt
python -m app.db.init_db
python -m app.db.seed
python -m uvicorn app.main:app --reload
```

The database operations are not currently exposed as HTTP endpoints. `/health`
continues to report application health, and the static Phase 1 UI remains
unchanged.

## Open the UI

Open `frontend/index.html` in a browser. The landing page is a static frontend
and does not need a separate server in this phase. The search form is
presentation-only until a later milestone adds search functionality.

## Run tests

```powershell
python -m pytest
```

Phase 2 and Phase 3 database tests create fresh temporary SQLite databases;
they do not read from or write to the developer's local database.

## Phase 3 curated seed sources

A `SeedSource` is a curated website entry point and metadata for a future
crawler; it is not a `Document`. A document represents one educational
resource, while a seed source describes a website from which a future phase
may discover resources. Keeping the registry curated gives ingestion an
intentional set of educational sources and scoped URL prefixes to start from.

```text
Curated educational sources
  -> SeedSource registry
  -> SQLite
  -> Future crawler
```

The `seed_sources` table stores each source's name, HTTPS start URL, derived
hostname, description, source type, education levels, subjects, allowed URL
prefixes, active status, priority, and UTC creation/update timestamps. The
start URL is unique; domains are indexed but not unique. URL prefixes and
categorical lists are stored as JSON arrays. The registry has no public API
endpoints.

Initialize both Phase 2 and Phase 3 tables with the existing command:

```powershell
python -m app.db.init_db
```

Insert the 12 deterministic curated sources with:

```powershell
python -m app.db.seed_sources
```

The seed command performs no network requests. It skips start URLs already in
the database, so a repeat run reports zero additional source records.

Phase 3 only prepares the persistent source registry. It does not crawl,
download, or parse websites. Crawling, URL discovery, and robots.txt handling
remain future responsibilities; a later phase can build crawler behavior
against this registry.

## Current limitations and scope

- No web crawler, robots.txt handling, URL discovery, HTML download, or HTML
  parsing.
- No search endpoint, index, BM25, vector search, semantic search, ranking,
  PageRank, or real search results.
- No embeddings, AI answers, LLM integration, authentication, or user accounts.
- The landing page is static and is not served by FastAPI.

## Upcoming phases

The next phase can implement carefully scoped crawling and ingestion from the
curated registry, including robots.txt handling. Indexing, retrieval,
evaluation, and other product capabilities remain later milestones; none is
included in Phase 3.
