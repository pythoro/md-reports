"""Tests for the ``properties`` kwarg that drives DOCX core properties."""

from __future__ import annotations

import pytest
from docx import Document as DocxDocument

from md_reports import (
    ConversionOptions,
    MarkdownConverter,
    convert_markdown_text,
)


def _open(path):
    return DocxDocument(str(path))


def test_properties_set_core_metadata(tmp_path):
    out = tmp_path / "props.docx"
    convert_markdown_text(
        "# Hello",
        out,
        properties={
            "title": "Q4 Report",
            "author": "Jane Doe",
            "subject": "Quarterly review",
            "keywords": "revenue, headcount",
            "comments": "Reference: REP-2026-Q4",
            "category": "Finance",
        },
    )
    cp = _open(out).core_properties
    assert cp.title == "Q4 Report"
    assert cp.author == "Jane Doe"
    assert cp.subject == "Quarterly review"
    assert cp.keywords == "revenue, headcount"
    assert cp.comments == "Reference: REP-2026-Q4"
    assert cp.category == "Finance"


def test_properties_aliases(tmp_path):
    """Word UI labels (Tags, Categories) and DC synonyms map correctly."""
    out = tmp_path / "alias.docx"
    convert_markdown_text(
        "# Hello",
        out,
        properties={
            "tags": "alpha, beta",
            "categories": "Internal",
            "creator": "Mx. Author",
            "description": "A short note.",
        },
    )
    cp = _open(out).core_properties
    assert cp.keywords == "alpha, beta"
    assert cp.category == "Internal"
    assert cp.author == "Mx. Author"
    assert cp.comments == "A short note."


def test_properties_keys_are_case_insensitive(tmp_path):
    out = tmp_path / "case.docx"
    convert_markdown_text(
        "# Hello",
        out,
        properties={"Title": "Mixed Case", "AUTHOR": "Loud"},
    )
    cp = _open(out).core_properties
    assert cp.title == "Mixed Case"
    assert cp.author == "Loud"


def test_unknown_property_warns(tmp_path):
    out = tmp_path / "unknown.docx"
    with pytest.warns(UserWarning, match="Unknown document property"):
        convert_markdown_text(
            "# Hello",
            out,
            properties={"company": "Acme Corp"},
        )
    # Output should still be produced
    assert out.exists()


def test_unknown_property_raises_in_strict_mode(tmp_path):
    from md_reports.errors import RenderError

    out = tmp_path / "strict.docx"
    with pytest.raises(RenderError, match="Unknown document property"):
        convert_markdown_text(
            "# Hello",
            out,
            options=ConversionOptions(strict_mode=True),
            properties={"company": "Acme Corp"},
        )


def test_no_properties_is_noop(tmp_path):
    out_a = tmp_path / "a.docx"
    out_b = tmp_path / "b.docx"
    convert_markdown_text("# Hello", out_a)
    convert_markdown_text("# Hello", out_b, properties={})
    # Both render successfully and don't pick up stray metadata
    cp_a = _open(out_a).core_properties
    cp_b = _open(out_b).core_properties
    # title from default template is empty / unset
    assert (cp_a.title or "") == (cp_b.title or "")


def test_converter_default_properties_apply(tmp_path):
    conv = MarkdownConverter(
        default_properties={"title": "Default Title", "author": "Alice"}
    )
    out = tmp_path / "default.docx"
    conv.convert_text("# Body", out)
    cp = _open(out).core_properties
    assert cp.title == "Default Title"
    assert cp.author == "Alice"


def test_converter_per_call_overrides_defaults(tmp_path):
    conv = MarkdownConverter(
        default_properties={"title": "Default", "author": "Alice"}
    )
    out = tmp_path / "override.docx"
    conv.convert_text(
        "# Body",
        out,
        properties={"title": "Override"},
    )
    cp = _open(out).core_properties
    assert cp.title == "Override"
    # default merged through unchanged
    assert cp.author == "Alice"


def test_properties_dont_bleed_across_calls(tmp_path):
    """Each render starts from a fresh template — properties from one
    call must not survive to the next."""
    conv = MarkdownConverter()
    out_a = tmp_path / "a.docx"
    out_b = tmp_path / "b.docx"
    conv.convert_text("# A", out_a, properties={"title": "First"})
    conv.convert_text("# B", out_b)
    cp_b = _open(out_b).core_properties
    assert (cp_b.title or "") != "First"
