const searchForm = document.querySelector("#search-form");
const searchQuery = document.querySelector("#search-query");
const searchStatus = document.querySelector("#search-status");

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchStatus.textContent = searchQuery.value.trim()
    ? "Search is coming soon. EduSearch is still being built."
    : "Enter a topic you would like to learn about.";
});

searchQuery.addEventListener("input", () => {
  searchStatus.textContent = "";
});
