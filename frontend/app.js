const searchForm = document.querySelector("#search-form");
const searchQuery = document.querySelector("#search-query");
const searchStatus = document.querySelector("#search-status");
const searchButton = document.querySelector("#search-button");
const resultsSection = document.querySelector("#results-section");
const resultsTitle = document.querySelector("#results-title");
const resultsList = document.querySelector("#results-list");
const loadingIndicator = document.querySelector("#loading-indicator");
const pageShell = document.querySelector(".page-shell");
const searchWidget = document.querySelector("#search-widget");
const suggestionList = document.querySelector("#suggestion-list");
const filterControls = [...document.querySelectorAll("[data-search-filter]")];
const clearFiltersButton = document.querySelector("#clear-filters");

const API_BASE_URL = "http://127.0.0.1:8000";
const RESULT_LIMIT = 10;
const SUGGESTION_LIMIT = 6;
const SUGGESTION_MINIMUM_LENGTH = 2;
const SUGGESTION_DEBOUNCE_MS = 220;
let isSearching = false;
let suggestionTimer;
let suggestionController;
let suggestionRequestId = 0;
let activeSuggestionIndex = -1;

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
  scheduleSuggestions(searchQuery.value.trim());
});

searchQuery.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (!suggestionList.hidden) {
      event.preventDefault();
      cancelSuggestions();
    }
    return;
  }

  if (
    event.key === "Enter" &&
    !suggestionList.hidden &&
    activeSuggestionIndex >= 0
  ) {
    event.preventDefault();
    const selected = suggestionList.querySelectorAll('[role="option"]')[
      activeSuggestionIndex
    ];
    if (selected) {
      const suggestion = selected.textContent ?? "";
      searchQuery.value = suggestion;
      search(suggestion);
    }
    return;
  }

  if (suggestionList.hidden || !["ArrowDown", "ArrowUp"].includes(event.key)) {
    return;
  }

  event.preventDefault();
  const options = suggestionList.querySelectorAll('[role="option"]');
  if (!options.length) {
    return;
  }
  const direction = event.key === "ArrowDown" ? 1 : -1;
  activeSuggestionIndex =
    activeSuggestionIndex === -1
      ? direction === 1
        ? 0
        : options.length - 1
      : (activeSuggestionIndex + direction + options.length) % options.length;
  options.forEach((option, index) => {
    option.setAttribute("aria-selected", String(index === activeSuggestionIndex));
  });
  searchQuery.setAttribute(
    "aria-activedescendant",
    options[activeSuggestionIndex].id,
  );
});

document.addEventListener("click", (event) => {
  if (!searchWidget.contains(event.target)) {
    cancelSuggestions();
  }
});

clearFiltersButton.addEventListener("click", () => {
  for (const filter of filterControls) {
    filter.value = "";
  }
  const query = searchQuery.value.trim();
  if (query) {
    search(query);
  }
});

async function search(query) {
  if (isSearching) {
    return;
  }
  cancelSuggestions();
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
  const parameters = new URLSearchParams({ q: query, limit: String(RESULT_LIMIT) });
  for (const filter of filterControls) {
    const value = filter.value.trim();
    if (value) {
      parameters.set(filter.dataset.searchFilter, value);
    }
  }
  url.search = parameters;

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
    renderResults(payload.results, query);
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

function scheduleSuggestions(query) {
  cancelSuggestions();
  if (query.length < SUGGESTION_MINIMUM_LENGTH) {
    return;
  }

  const requestId = suggestionRequestId;
  suggestionTimer = setTimeout(
    () => fetchSuggestions(query, requestId),
    SUGGESTION_DEBOUNCE_MS,
  );
}

async function fetchSuggestions(query, requestId) {
  const controller = new AbortController();
  suggestionController = controller;
  const url = new URL("/api/v1/search/suggestions", API_BASE_URL);
  url.search = new URLSearchParams({
    q: query,
    limit: String(SUGGESTION_LIMIT),
  });

  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    if (
      requestId !== suggestionRequestId ||
      searchQuery.value.trim() !== query ||
      !isValidSuggestionsResponse(payload)
    ) {
      return;
    }
    renderSuggestions(payload.suggestions);
  } catch {
    if (!controller.signal.aborted) {
      closeSuggestions();
    }
  } finally {
    if (suggestionController === controller) {
      suggestionController = undefined;
    }
  }
}

function isValidSuggestionsResponse(payload) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    typeof payload.query === "string" &&
    Array.isArray(payload.suggestions) &&
    payload.suggestions.length <= SUGGESTION_LIMIT &&
    payload.suggestions.every((suggestion) => typeof suggestion === "string")
  );
}

function renderSuggestions(suggestions) {
  if (!suggestions.length) {
    closeSuggestions();
    return;
  }

  const fragment = document.createDocumentFragment();
  suggestions.forEach((suggestion, index) => {
    const option = document.createElement("button");
    option.type = "button";
    option.id = `suggestion-option-${index}`;
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    option.textContent = suggestion;
    option.addEventListener("click", () => {
      searchQuery.value = suggestion;
      search(suggestion);
    });
    fragment.append(option);
  });

  suggestionList.replaceChildren(fragment);
  suggestionList.hidden = false;
  searchQuery.setAttribute("aria-expanded", "true");
  activeSuggestionIndex = -1;
}

function cancelSuggestions() {
  clearTimeout(suggestionTimer);
  suggestionController?.abort();
  suggestionController = undefined;
  suggestionRequestId += 1;
  closeSuggestions();
}

function closeSuggestions() {
  suggestionList.replaceChildren();
  suggestionList.hidden = true;
  searchQuery.setAttribute("aria-expanded", "false");
  searchQuery.removeAttribute("aria-activedescendant");
  activeSuggestionIndex = -1;
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
        typeof result.snippet === "string" &&
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

function renderResults(results, query) {
  const fragment = document.createDocumentFragment();
  const queryTerms = getQueryTerms(query);

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

    if (result.snippet.trim()) {
      const snippet = document.createElement("p");
      snippet.className = "result-snippet";
      appendHighlightedText(snippet, result.snippet, queryTerms);
      item.append(snippet);
    }

    fragment.append(item);
  }

  resultsList.replaceChildren(fragment);
}

function getQueryTerms(query) {
  const terms = query.match(/[\p{L}\p{N}\p{M}]+/gu) ?? [];
  return new Set(terms.map(normalizeHighlightTerm));
}

function normalizeHighlightTerm(value) {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/ß/g, "ss")
    .replace(/ς/g, "σ");
}

function appendHighlightedText(container, text, queryTerms) {
  const tokenPattern = /[\p{L}\p{N}\p{M}]+/gu;
  const fragment = document.createDocumentFragment();
  let previousEnd = 0;
  let match;

  while ((match = tokenPattern.exec(text)) !== null) {
    if (match.index > previousEnd) {
      fragment.append(document.createTextNode(text.slice(previousEnd, match.index)));
    }
    if (queryTerms.has(normalizeHighlightTerm(match[0]))) {
      const mark = document.createElement("mark");
      mark.textContent = match[0];
      fragment.append(mark);
    } else {
      fragment.append(document.createTextNode(match[0]));
    }
    previousEnd = tokenPattern.lastIndex;
  }

  if (previousEnd < text.length) {
    fragment.append(document.createTextNode(text.slice(previousEnd)));
  }
  container.replaceChildren(fragment);
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
  for (const filter of filterControls) {
    filter.disabled = searching;
  }
  clearFiltersButton.disabled = searching;
  searchForm.setAttribute("aria-busy", String(searching));
  searchButton.querySelector("span").textContent = searching ? "Searching" : "Search";
}

function clearResults() {
  resultsTitle.textContent = "";
  resultsList.replaceChildren();
}
