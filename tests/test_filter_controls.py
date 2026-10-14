from html.parser import HTMLParser
from pathlib import Path

import pytest


class FilterControlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.controls: dict[str, dict[str, object]] = {}
        self.labelled_control_ids: set[str] = set()
        self._current_control: dict[str, object] | None = None
        self._current_option: dict[str, str] | None = None
        self._text_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = dict(attrs)
        if tag == "label" and attributes.get("for") is not None:
            self.labelled_control_ids.add(attributes["for"])
        elif tag == "select" and "data-search-filter" in attributes:
            control_id = attributes["id"]
            assert control_id is not None
            self._current_control = {
                "filter": attributes["data-search-filter"],
                "options": [],
            }
            self.controls[control_id] = self._current_control
        elif tag == "option" and self._current_control is not None:
            self._current_option = {"value": attributes.get("value", "") or ""}
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_option is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self._current_option is not None:
            self._current_option["label"] = "".join(self._text_parts).strip()
            options = self._current_control["options"]
            assert isinstance(options, list)
            options.append(self._current_option)
            self._current_option = None
            self._text_parts = []
        elif tag == "select":
            self._current_control = None


@pytest.fixture
def filter_controls() -> tuple[dict[str, dict[str, object]], set[str]]:
    frontend = Path(__file__).resolve().parents[1] / "frontend" / "index.html"
    parser = FilterControlParser()
    parser.feed(frontend.read_text(encoding="utf-8"))
    return parser.controls, parser.labelled_control_ids


def test_filter_dropdowns_have_accessible_labels_and_expected_values(
    filter_controls: tuple[dict[str, dict[str, object]], set[str]],
) -> None:
    controls, labelled_control_ids = filter_controls
    assert set(controls) == {
        "filter-education-level",
        "filter-subject",
        "filter-content-type",
    }
    assert set(controls) <= labelled_control_ids
    expected_options = {
        "filter-education-level": [
            ("", "Any level"),
            ("School", "School"),
            ("University", "College / University"),
            ("Professional", "Professional"),
            ("Research", "Research"),
        ],
        "filter-subject": [
            ("", "Any subject"),
            ("Computer Science", "Computer Science"),
            ("Engineering", "Engineering"),
            ("Mathematics", "Mathematics"),
            ("Physics", "Physics"),
            ("Chemistry", "Chemistry"),
            ("Biology", "Biology"),
            ("Medicine", "Medicine"),
            ("Business / MBA", "Business / MBA"),
            ("Economics", "Economics"),
            ("Humanities", "Humanities"),
            ("Social Sciences", "Social Sciences"),
            ("Other / Specialized", "Other / Specialized"),
        ],
        "filter-content-type": [
            ("", "Any resource type"),
            ("course", "Course"),
            ("documentation", "Documentation"),
            ("article", "Article"),
            ("tutorial", "Tutorial"),
            ("research paper", "Research Paper"),
            ("lecture", "Lecture"),
            ("blog", "Blog"),
            ("study material", "Study Material"),
            ("Other / Specialized", "Other / Specialized"),
        ],
    }
    expected_filter_fields = {
        "filter-education-level": "education_level",
        "filter-subject": "subject",
        "filter-content-type": "content_type",
    }

    for control_id, expected in expected_options.items():
        control = controls[control_id]
        assert control["filter"] == expected_filter_fields[control_id]
        options = control["options"]
        assert options == [
            {"value": value, "label": label} for value, label in expected
        ]


def test_any_options_are_blank_and_other_is_a_filter_value(
    filter_controls: tuple[dict[str, dict[str, object]], set[str]],
) -> None:
    controls, _ = filter_controls
    for control in controls.values():
        options = control["options"]
        assert isinstance(options, list)
        assert options[0]["value"] == ""

    for control_id in ("filter-subject", "filter-content-type"):
        options = controls[control_id]["options"]
        assert isinstance(options, list)
        other_option = next(
            option for option in options if option["label"] == "Other / Specialized"
        )
        assert other_option["value"] == "Other / Specialized"
