"""Template loading tests."""

from __future__ import annotations

import pytest

from md_ast_docx.errors import TemplateError
from md_ast_docx.template import (
    get_default_template_path,
    load_template,
    style_exists,
)


def test_default_template_path_exists():
    p = get_default_template_path()
    assert p.exists(), f"missing packaged default template: {p}"


def test_load_default_template_has_required_styles():
    doc = load_template(None)
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
        load_template("does/not/exist.docx")
