# EduSearch

EduSearch is a specialized search experience for discovering publicly
accessible educational resources across school, university, professional,
technical, academic, and research domains. It is a focused vertical search
engine, not a replacement for general-purpose search engines.

## Project status

Phase 1 provides the FastAPI health check and a responsive landing/search
screen. Phase 2 adds the document model, SQLite persistence, Pydantic data
schemas, a focused repository, and deterministic development sample data.
Phase 3 adds the curated SeedSource registry. Phase 4A provides the crawler
foundation. Phase 4B adds HTML and metadata extraction, canonical URL handling,
content hashing, Document creation, and SQLite persistence. Phase 5 adds
field-aware tokenization, a SQLite inverted-index foundation, and
term/document/field statistics. BM25 ranking, the search API, frontend search,
semantic/vector search, and AI search are not implemented.

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

Phase 3 prepared the persistent source registry but did not crawl, download,
or parse websites. The development crawler described below is the first
crawling functionality and uses this registry as its configuration.

## Phase 4A development crawler

The generic asynchronous crawler reads configuration from a `SeedSource` and
fetches HTML pages in breadth-first order. It checks the exact hostname and
configured allowed URL prefixes before following discovered links. The start
URL itself is allowed even when the source uses narrower prefixes to limit
links discovered from its landing page.

Robots rules are parsed with Python's standard-library `urllib.robotparser`
and cached per origin for each crawl. When `robots.txt` cannot be retrieved,
the crawler conservatively denies the page and records the reason; it does
not assume permission. Redirects are followed manually so each target is
checked against both scope and robots rules.

Development defaults cap a crawl at 20 attempted pages and depth 2, use a
10-second request timeout, wait one second between requests, identify as
`EduSearchBot/0.1`, and limit each response to 5 MB. Only HTML and XHTML are
accepted; a small standard-library HTML parser extracts anchor links. HTTP
requests are asynchronous and sequential. These safeguards are for
development crawling, not production-scale crawling.

Phase 4A returns in-memory crawl result models only. It does not write fetched
pages to `documents`, expose a crawler API, or add search functionality.
Crawler tests use mocked HTTP responses and do not access the network.

## Phase 4B HTML extraction and ingestion

The ingestion flow is:

```text
CrawlPage
  -> local HTML extraction
  -> DocumentCreate
  -> DocumentRepository
  -> SQLite
```

Phase 4B parses fetched HTML locally with Beautiful Soup, normalizes extracted
titles, descriptions, headings, body text, and available metadata, and stores
the result through the existing `DocumentRepository`. Canonical URLs are
normalized and must remain within the SeedSource hostname and allowed URL
prefixes; otherwise ingestion falls back to the fetched page URL. A stable
SHA-256 hash is generated from normalized title, headings, and body content.
SeedSource `source_type` is retained; subject and education level are only
copied when the source metadata has a single unambiguous value.

Repeated ingestion uses existing URL/canonical URL uniqueness rules and
returns the existing document rather than creating a duplicate. `CrawlPage`
remains an in-memory crawler result, separate from the persisted `Document`
model.

## Phase 5 inverted-index foundation

The indexing flow is:

```text
Documents in SQLite
  -> field-aware tokenization
  -> inverted-index postings and field statistics
  -> SQLite
```

Phase 5 indexes title, description, headings, and body separately. It stores
term frequencies, token positions, document lengths per field, and term
statistics. Re-indexing replaces the document's previous postings and
statistics.

## Phase 6 BM25 ranking

Phase 6 ranks matching documents from the inverted index using field-aware
Okapi BM25. Each field uses its own document frequency and length statistics.
The configurable defaults are `k1=1.2`, `b=0.75`, and field weights of title
`4.0`, headings `2.5`, description `2.0`, and body `1.0`.

```text
query -> existing tokenizer -> inverted-index postings -> BM25
      -> weighted field scores -> ranked document IDs
```

This provides ranking infrastructure only. A public search API and functional
frontend search remain future phases; semantic/vector search and AI search are
not implemented.

## Current limitations and scope

- No production crawler or distributed crawling.
- No sophisticated article extraction or educational content classification.
- No search endpoint, frontend search, vector search, semantic search,
  PageRank, or real search results.
- No embeddings, AI answers, LLM integration, authentication, or user accounts.
- The landing page is static and is not served by FastAPI.

## Upcoming phases

The next major phase is the public search API built on the BM25 ranking engine.
