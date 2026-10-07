from app.indexing.tokenizer import tokenize


def test_tokenizes_basic_text_and_normalizes_case() -> None:
    assert tokenize("Python Programming!") == ["python", "programming"]
    assert tokenize("Python, PYTHON and python.") == [
        "python",
        "python",
        "and",
        "python",
    ]


def test_unicode_compatibility_and_case_normalization() -> None:
    assert tokenize("ＰＹＴＨＯＮ Straße") == ["python", "strasse"]
    assert tokenize("cafe\u0301 café") == ["café", "café"]


def test_punctuation_and_repeated_whitespace_are_boundaries() -> None:
    assert tokenize("  machine,\n\nlearning\ttools... ") == [
        "machine",
        "learning",
        "tools",
    ]


def test_empty_and_none_input_are_safe() -> None:
    assert tokenize("") == []
    assert tokenize(None) == []
    assert tokenize(" \n\t ") == []


def test_numbers_and_mixed_alphanumeric_tokens_are_preserved() -> None:
    assert tokenize("Python 3.12 supports UTF-8 and x86") == [
        "python",
        "3",
        "12",
        "supports",
        "utf",
        "8",
        "and",
        "x86",
    ]


def test_output_is_deterministic_without_stop_word_removal_or_stemming() -> None:
    text = "The learner is learning and learned a lesson."

    assert tokenize(text) == tokenize(text)
    assert tokenize(text) == [
        "the",
        "learner",
        "is",
        "learning",
        "and",
        "learned",
        "a",
        "lesson",
    ]
