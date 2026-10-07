const searchForm = document.querySelector("#search-form");
const searchQuery = document.querySelector("#search-query");
const searchStatus = document.querySelector("#search-status");
const searchButton = document.querySelector("#search-button");
const resultsSection = document.querySelector("#results-section");
const resultsTitle = document.querySelector("#results-title");
const resultsList = document.querySelector("#results-list");
const loadingIndicator = document.querySelector("#loading-indicator");
const pageShell = document.querySelector(".page-shell");

const API_BASE_URL = "http://127.0.0.1:8000";
const RESULT_LIMIT = 10;
let isSearching = false;

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (isSearching) {
    return;
  }

  const query = searchQuery.value.trim();
  if (!query) {
    showValidationMessage("Enter a topic you would like to learn about.");
    searchQuery.focus();
    return;
  }

  await search(query);
});

searchQuery.addEventListener("input", () => {
  if (searchStatus.dataset.state === "validation") {
    setStatus("");
  }
});

async function search(query) {
  isSearching = true;
  setSearching(true);
  setStatus("");
  clearResults();
  resultsSection.hidden = false;
  pageShell.classList.add("has-results");
  resultsSection.setAttribute("aria-busy", "true");
  resultsTitle.textContent = "Searching…";
  loadingIndicator.hidden = false;

  const url = new URL("/api/v1/search", API_BASE_URL);
  url.search = new URLSearchParams({ q: query, limit: String(RESULT_LIMIT) });

  try {
    const response = await fetch(url);
    if (response.status === 422) {
      resultsTitle.textContent = "Try a shorter search";
      setStatus("Please shorten or simplify your query, then try again.");
      return;
    }
    if (!response.ok) {
      throw new Error("The search request was not successful.");
    }

    const payload = await response.json();
    if (!isValidSearchResponse(payload)) {
      throw new Error("The search response was not valid.");
    }

    if (payload.results.length === 0) {
      resultsTitle.textContent = "No results found";
      setStatus("Try a broader or different search.");
      return;
    }

    resultsTitle.textContent = `Results for “${query}”`;
    renderResults(payload.results);
    setStatus(`${payload.total} ${payload.total === 1 ? "result" : "results"} found.`);
  } catch {
    resultsTitle.textContent = "Search is temporarily unavailable";
    setStatus("Please try again in a moment.");
  } finally {
    isSearching = false;
    setSearching(false);
    resultsSection.setAttribute("aria-busy", "false");
    loadingIndicator.hidden = true;
  }
}

function isValidSearchResponse(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    typeof payload.query === "string" &&
    Number.isInteger(payload.total) &&
    payload.total >= 0 &&
    Array.isArray(payload.results) &&
    payload.total === payload.results.length &&
    payload.results.every(
      (result) =>
        result !== null &&
        typeof result === "object" &&
        Number.isInteger(result.document_id) &&
        (typeof result.title === "string" || result.title === null) &&
        typeof result.url === "string" &&
        isWebUrl(result.url) &&
        (typeof result.description === "string" || result.description === null) &&
        typeof result.score === "number" &&
        Number.isFinite(result.score) &&
        Array.isArray(result.matched_terms) &&
        result.matched_terms.every((term) => typeof term === "string"),
    )
  );
}

function isWebUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function renderResults(results) {
  const fragment = document.createDocumentFragment();

  for (const result of results) {
    const item = document.createElement("li");
    item.className = "result-card";

    const link = document.createElement("a");
    link.className = "result-title";
    link.href = result.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = result.title?.trim() || readableHost(result.url) || "Untitled resource";

    const address = document.createElement("p");
    address.className = "result-url";
    address.textContent = readableAddress(result.url);
    address.title = result.url;

    item.append(link, address);

    if (result.description?.trim()) {
      const description = document.createElement("p");
      description.className = "result-description";
      description.textContent = result.description.trim();
      item.append(description);
    }

    fragment.append(item);
  }

  resultsList.replaceChildren(fragment);
}

function readableAddress(value) {
  const url = new URL(value);
  return `${url.hostname}${url.pathname === "/" ? "" : url.pathname}`;
}

function readableHost(value) {
  try {
    return new URL(value).hostname;
  } catch {
    return "";
  }
}

function showValidationMessage(message) {
  resultsSection.hidden = true;
  pageShell.classList.remove("has-results");
  setStatus(message, "validation");
}

function setStatus(message, state = "") {
  searchStatus.textContent = message;
  searchStatus.dataset.state = state;
}

function setSearching(searching) {
  searchButton.disabled = searching;
  searchQuery.disabled = searching;
  searchForm.setAttribute("aria-busy", String(searching));
  searchButton.querySelector("span").textContent = searching ? "Searching" : "Search";
}

function clearResults() {
  resultsTitle.textContent = "";
  resultsList.replaceChildren();
}
