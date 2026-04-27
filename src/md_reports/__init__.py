"""md_reports — Markdown to document conversion with pluggable renderers.

Public API:
    convert_markdown_text(markdown_text, output_path, *, renderer,
        options, context) -> Path
    convert_markdown_file(markdown_path, output_path, *, renderer,
        options, context) -> Path
    MarkdownConverter(renderer=None, options=None, default_context=None)

Renderers:
    BaseRenderer            — abstract base for output-format renderers
    DocxRenderer(template_path=None, options=None) — default renderer
    RenderContext           — per-render mutable state container

DOCX-specific helpers:
    get_default_template_path() -> Path

Configuration:
    ConversionOptions(...)

Errors:
    MdAstDocxError, ParseError, RenderError, TemplateError, ValidationError
"""

from __future__ import annotations

from md_reports.api import (
    MarkdownConverter,
    convert_markdown_file,
    convert_markdown_text,
)
from md_reports.errors import (
    MdAstDocxError,
    ParseError,
    RenderError,
    TemplateError,
    ValidationError,
)
from md_reports.options import ConversionOptions
from md_reports.renderers.base import BaseRenderer, RenderContext
from md_reports.renderers.docx import (
    DocxRenderer,
    get_default_template_path,
)

__all__ = [
    "BaseRenderer",
    "ConversionOptions",
    "DocxRenderer",
    "MarkdownConverter",
    "MdAstDocxError",
    "ParseError",
    "RenderContext",
    "RenderError",
    "TemplateError",
    "ValidationError",
    "convert_markdown_file",
    "convert_markdown_text",
    "get_default_template_path",
]
