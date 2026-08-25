"""Tests for PDFParser's tolerance of pages with no extractable text.

The parser joins per-page strings, so a single page yielding None turns the
whole document into a ParsingError. These tests inject a fake PyPDF2 rather
than requiring the optional `parsers` extra to be installed.

Scope note: PyPDF2 3.0.1's `extract_text()` is annotated `-> str` and returns
"" for a page with no text layer (verified against a blank page and against a
page stripped of /Contents and /Resources). The None case these tests pin is
therefore a defensive invariant covering other backends and versions — not a
reproduction of a live PyPDF2 3.0.1 bug.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pytest

from wizard_core import document_parsers
from wizard_core.document_parsers import PDFParser, ParsingError


class _FakePage:
    def __init__(self, text: Optional[str]):
        self._text = text

    def extract_text(self) -> Optional[str]:
        return self._text


class _FakeReader:
    def __init__(self, pages: List[_FakePage]):
        self.pages = pages


def _install_fake_pdf(monkeypatch: pytest.MonkeyPatch, texts: List[Optional[str]]) -> None:
    """Point document_parsers at a PyPDF2 stand-in yielding `texts`."""
    class _FakePyPDF2:
        @staticmethod
        def PdfReader(stream):  # noqa: N802 — mirrors the real API name
            return _FakeReader([_FakePage(t) for t in texts])

    monkeypatch.setattr(document_parsers, "PDF_AVAILABLE", True)
    monkeypatch.setattr(document_parsers, "PyPDF2", _FakePyPDF2, raising=False)


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    """A file that merely has to exist; the fake reader ignores its bytes."""
    path = tmp_path / "doc.pdf"
    path.write_bytes(b"%PDF-1.4\n")
    return path


def test_page_returning_none_does_not_fail_the_parse(
    monkeypatch: pytest.MonkeyPatch, pdf_file: Path
) -> None:
    _install_fake_pdf(monkeypatch, ["Real text", None, "More text"])
    result = PDFParser(str(pdf_file)).parse()

    assert result["text"] == "Real text\n\nMore text"
    assert result["pages"] == ["Real text", "", "More text"]
    assert result["num_pages"] == 3
    # Every page is a string, so downstream joins and len() calls are safe.
    assert all(isinstance(page, str) for page in result["pages"])


def test_all_pages_none_yields_empty_text(
    monkeypatch: pytest.MonkeyPatch, pdf_file: Path
) -> None:
    """A fully scanned document parses to empty text rather than raising."""
    _install_fake_pdf(monkeypatch, [None, None])
    result = PDFParser(str(pdf_file)).parse()

    assert result["text"] == "\n"
    assert result["pages"] == ["", ""]
    assert result["num_pages"] == 2


def test_normal_pages_are_unchanged(
    monkeypatch: pytest.MonkeyPatch, pdf_file: Path
) -> None:
    """The guard must not disturb documents that have a text layer."""
    _install_fake_pdf(monkeypatch, ["Page one", "Page two"])
    result = PDFParser(str(pdf_file)).parse()

    assert result["text"] == "Page one\nPage two"
    assert result["pages"] == ["Page one", "Page two"]


def test_empty_string_pages_are_preserved(
    monkeypatch: pytest.MonkeyPatch, pdf_file: Path
) -> None:
    """What real PyPDF2 3.0.1 actually returns for a blank page."""
    _install_fake_pdf(monkeypatch, ["Real text", "", "More text"])
    result = PDFParser(str(pdf_file)).parse()

    assert result["text"] == "Real text\n\nMore text"
    assert result["pages"] == ["Real text", "", "More text"]


def test_missing_file_still_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_fake_pdf(monkeypatch, ["x"])
    with pytest.raises(ParsingError, match="PDF file not found"):
        PDFParser(str(tmp_path / "nope.pdf"))
