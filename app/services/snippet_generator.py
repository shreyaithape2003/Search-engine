import unicodedata
from collections.abc import Iterator, Sequence

from app.indexing.tokenizer import tokenize


class SnippetGenerator:
    """Select a short, query-relevant passage from stored document text."""

    _MAX_CANDIDATES = 64

    def __init__(self, maximum_length: int = 240) -> None:
        if maximum_length < 1:
            raise ValueError("maximum_length must be a positive integer.")
        self.maximum_length = maximum_length

    def generate(
        self,
        query: str,
        *,
        description: str | None = None,
        headings: Sequence[str] | None = None,
        body: str | None = None,
    ) -> str:
        """Return a plain-text excerpt, preferring fields and passages with matches."""
        query_terms = set(tokenize(query))
        heading_text = " ".join(
            heading.strip()
            for heading in headings or ()
            if isinstance(heading, str) and heading.strip()
        )
        fields = (
            description.strip() if description and description.strip() else "",
            heading_text,
            body.strip() if body and body.strip() else "",
        )

        best_snippet = ""
        best_key = (-1, -1, -1, 0)
        for field_order, text in enumerate(fields):
            if not text:
                continue

            token_spans = self._token_spans(text)
            matching_anchors: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}
            for term, start, end in token_spans:
                if term not in query_terms:
                    continue
                span = (start, end)
                if term in matching_anchors:
                    matching_anchors[term] = (matching_anchors[term][0], span)
                else:
                    matching_anchors[term] = (span, span)

            if matching_anchors:
                starts = [0]
                seen_starts = {0}
                for first, last in matching_anchors.values():
                    for match_start, _ in (first, last):
                        for candidate_start in (
                            max(0, match_start - self.maximum_length // 2),
                            match_start,
                        ):
                            if candidate_start not in seen_starts:
                                seen_starts.add(candidate_start)
                                starts.append(candidate_start)
                                if len(starts) >= self._MAX_CANDIDATES:
                                    break
                        if len(starts) >= self._MAX_CANDIDATES:
                            break
                    if len(starts) >= self._MAX_CANDIDATES:
                        break

                for start in starts:
                    snippet, excerpt_start, excerpt_end = self._excerpt(text, start)
                    included_terms = (
                        term
                        for term in self._matching_terms(
                            text,
                            excerpt_start,
                            excerpt_end,
                            query_terms,
                        )
                    )
                    distinct_terms: set[str] = set()
                    match_count = 0
                    for term in included_terms:
                        distinct_terms.add(term)
                        match_count += 1
                    key = (
                        len(distinct_terms),
                        match_count,
                        -field_order,
                        -excerpt_start,
                    )
                    if key > best_key:
                        best_key = key
                        best_snippet = snippet
            else:
                snippet, _, _ = self._excerpt(text, 0)
                key = (0, 0, -field_order, 0)
                if key > best_key:
                    best_key = key
                    best_snippet = snippet

        return best_snippet

    def _excerpt(self, text: str, desired_start: int) -> tuple[str, int, int]:
        if len(text) <= self.maximum_length:
            return text, 0, len(text)

        start = min(max(desired_start, 0), len(text) - 1)
        if start:
            previous_space = next(
                (
                    index
                    for index in range(start - 1, max(-1, start - 25), -1)
                    if text[index].isspace()
                ),
                -1,
            )
            if previous_space >= start - 24:
                start = previous_space + 1
            else:
                next_space = next(
                    (
                        index
                        for index in range(start, min(len(text), start + 24))
                        if text[index].isspace()
                    ),
                    -1,
                )
                if next_space >= 0:
                    start = next_space + 1

        while start < len(text) and text[start].isspace():
            start += 1
        if start >= len(text):
            return "", len(text), len(text)

        while True:
            available_length = self.maximum_length - int(start > 0)
            if available_length <= 0:
                return "…", start, start
            remaining_length = len(text) - start
            if remaining_length <= available_length:
                end = len(text)
                break

            content_budget = available_length - 1
            if content_budget <= 0:
                return "…", start, start
            target_end = start + content_budget
            boundary = next(
                (
                    index
                    for index in range(target_end - 1, start, -1)
                    if text[index].isspace()
                ),
                -1,
            )
            if boundary > start:
                end = boundary
                break

            next_boundary = next(
                (
                    index
                    for index in range(target_end, len(text))
                    if text[index].isspace()
                ),
                -1,
            )
            if next_boundary == target_end:
                end = target_end
                break
            if next_boundary >= 0:
                start = next_boundary + 1
                while start < len(text) and text[start].isspace():
                    start += 1
                if start >= len(text):
                    return "…", len(text), len(text)
                continue

            # An unbroken token longer than the limit cannot fit whole.
            end = target_end
            break

        while end > start and text[end - 1].isspace():
            end -= 1

        snippet = (
            f"{'…' if start > 0 else ''}"
            f"{text[start:end]}"
            f"{'…' if end < len(text) else ''}"
        )
        return snippet, start, end

    def _matching_terms(
        self,
        text: str,
        start: int,
        end: int,
        query_terms: set[str],
    ) -> Iterator[str]:
        excerpt = text[start:end]
        left_is_partial = (
            start > 0
            and end > start
            and self._is_token_character(text[start - 1])
            and self._is_token_character(text[start])
        )
        right_is_partial = (
            end < len(text)
            and end > start
            and self._is_token_character(text[end - 1])
            and self._is_token_character(text[end])
        )
        for term, token_start, token_end in self._token_spans(excerpt):
            if left_is_partial and token_start == 0:
                continue
            if right_is_partial and token_end == len(excerpt):
                continue
            if term in query_terms:
                yield term

    @staticmethod
    def _is_token_character(character: str) -> bool:
        return unicodedata.category(character)[0] in {"L", "N", "M"}

    @staticmethod
    def _token_spans(text: str) -> Iterator[tuple[str, int, int]]:
        token_start: int | None = None
        token_characters: list[str] = []

        for index, character in enumerate(text):
            category = unicodedata.category(character)
            is_letter_or_number = category[0] in {"L", "N"}
            is_combining_mark = category[0] == "M" and bool(token_characters)
            if is_letter_or_number or is_combining_mark:
                if token_start is None:
                    token_start = index
                token_characters.append(character)
            elif token_characters:
                for term in tokenize("".join(token_characters)):
                    yield term, token_start, index
                token_start = None
                token_characters.clear()

        if token_characters and token_start is not None:
            for term in tokenize("".join(token_characters)):
                yield term, token_start, len(text)
