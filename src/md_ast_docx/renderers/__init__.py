"""Renderer plugins for md_ast_docx.

A renderer takes a parsed :class:`~md_ast_docx.model.Document` and emits an
output file in some format. The base abstraction lives in :mod:`.base`;
concrete renderers live in subpackages (e.g. :mod:`.docx`).
"""

from __future__ import annotations

from md_ast_docx.renderers.base import BaseRenderer, RenderContext
from md_ast_docx.renderers.docx import DocxRenderer

__all__ = ["BaseRenderer", "DocxRenderer", "RenderContext"]
