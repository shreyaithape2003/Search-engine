import unicodedata
from collections.abc import Iterator, Sequence

from app.indexing.tokenizer import tokenize


class SnippetGenerator:
    """Select a short, query-relevant passage from stored document text."""

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
                starts = {0}
                for first, last in matching_anchors.values():
                    for start, _ in {first, last}:
                        starts.update(
                            (
                                max(0, start - self.maximum_length // 3),
                                max(0, start - self.maximum_length // 2),
                                start,
                            )
                        )
                for start in starts:
                    snippet, excerpt_start, excerpt_end = self._excerpt(text, start)
                    included = list(
                        self._token_spans(text[excerpt_start:excerpt_end])
                    )
                    included_terms = [
                        term for term, _, _ in included if term in query_terms
                    ]
                    key = (
                        len(set(included_terms)),
                        len(included_terms),
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

        leading_ellipsis = start > 0
        end = min(
            len(text),
            start + self.maximum_length - int(leading_ellipsis),
        )
        if end < len(text):
            end -= 1
            boundary = next(
                (
                    index
                    for index in range(end, start, -1)
                    if text[index - 1].isspace()
                ),
                -1,
            )
            if boundary > start:
                end = boundary

        excerpt = text[start:end].strip()
        snippet = f"{'…' if leading_ellipsis else ''}{excerpt}"
        if end < len(text):
            snippet += "…"
        if len(snippet) > self.maximum_length:
            snippet = snippet[: self.maximum_length - 1].rstrip() + "…"
        return snippet, start, end

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
