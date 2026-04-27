"""Template loading tests."""

from __future__ import annotations

import pytest
from docx.oxml.ns import qn

from md_reports.errors import TemplateError
from md_reports.renderers.docx.template import (
    get_default_template_path,
    load_docx_template,
    style_exists,
)


def test_default_template_path_exists():
    p = get_default_template_path()
    assert p.exists(), f"missing packaged default template: {p}"


def test_load_default_template_has_required_styles():
    doc = load_docx_template(None)
    for required in (
        "Normal",
        "Heading 1",
        "Heading 2",
        "Heading 3",
        "Caption",
        "List Bullet",
        "List Number",
        "Quote",
        "Table Grid",
    ):
        assert style_exists(doc, required), (
            f"required style missing in default template: {required}"
        )


def test_load_template_missing_path_raises():
    with pytest.raises(TemplateError):
        load_docx_template("does/not/exist.docx")


def test_default_template_caption_is_italic():
    """The packaged default template must ship a Caption style with
    real formatting. A previous version of the template had Caption
    flagged ``semiHidden`` with bold-blue-9pt formatting, which Word
    rendered inconsistently and looked nothing like a conventional
    caption."""
    doc = load_docx_template(None)
    rPr = doc.styles["Caption"].element.find(qn("w:rPr"))
    assert rPr is not None
    assert rPr.find(qn("w:i")) is not None
