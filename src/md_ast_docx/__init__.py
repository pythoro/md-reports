"""md_ast_docx — Convert Markdown to DOCX with template-driven styling.

Public API:
    convert_markdown_text(markdown_text, output_path, *, template_path,
        options) -> Path
    convert_markdown_file(markdown_path, output_path, *, template_path,
        options) -> Path
    MarkdownDocxConverter(template_path=None, options=None)
    ConversionOptions(...)
    get_default_template_path() -> Path
"""

from __future__ import annotations

from md_ast_docx.api import (
    MarkdownDocxConverter,
    convert_markdown_file,
    convert_markdown_text,
)
from md_ast_docx.errors import (
    MdAstDocxError,
    ParseError,
    RenderError,
    TemplateError,
    ValidationError,
)
from md_ast_docx.options import ConversionOptions
from md_ast_docx.template import get_default_template_path

__all__ = [
    "ConversionOptions",
    "MarkdownDocxConverter",
    "MdAstDocxError",
    "ParseError",
    "RenderError",
    "TemplateError",
    "ValidationError",
    "convert_markdown_file",
    "convert_markdown_text",
    "get_default_template_path",
]
