"""DOCX renderer subpackage."""

from __future__ import annotations

from md_ast_docx.renderers.docx.renderer import DocxRenderer
from md_ast_docx.renderers.docx.template import (
    get_default_template_path,
    load_docx_template,
    style_exists,
)

__all__ = [
    "DocxRenderer",
    "get_default_template_path",
    "load_docx_template",
    "style_exists",
]
