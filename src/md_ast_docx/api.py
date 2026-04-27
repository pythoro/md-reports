"""Public conversion API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from md_ast_docx.errors import ValidationError
from md_ast_docx.options import ConversionOptions
from md_ast_docx.parser import parse
from md_ast_docx.renderer import Renderer
from md_ast_docx.template import load_template


def convert_markdown_text(
    markdown_text: str,
    output_path: str | Path,
    *,
    template_path: str | Path | None = None,
    options: ConversionOptions | None = None,
    context: dict[str, Any] | None = None,
) -> Path:
    """Convert a Markdown string to DOCX written at ``output_path``.

    If ``context`` is provided, the markdown is rendered as a Jinja2
    template against it before parsing.
    """
    if not isinstance(markdown_text, str):
        raise ValidationError("markdown_text must be a string")
    return _convert(
        markdown_text=markdown_text,
        output_path=Path(output_path),
        template_path=template_path,
        options=options,
        markdown_dir=None,
        context=context,
    )


def convert_markdown_file(
    markdown_path: str | Path,
    output_path: str | Path,
    *,
    template_path: str | Path | None = None,
    options: ConversionOptions | None = None,
    context: dict[str, Any] | None = None,
) -> Path:
    """Read a Markdown file and write a DOCX at ``output_path``.

    If ``context`` is provided, the markdown is rendered as a Jinja2
    template against it before parsing.
    """
    md_path = Path(markdown_path)
    if not md_path.exists():
        raise ValidationError(f"Markdown file not found: {md_path}")
    text = md_path.read_text(encoding="utf-8")
    return _convert(
        markdown_text=text,
        output_path=Path(output_path),
        template_path=template_path,
        options=options,
        markdown_dir=md_path.parent.resolve(),
        context=context,
    )


def _convert(
    *,
    markdown_text: str,
    output_path: Path,
    template_path: str | Path | None,
    options: ConversionOptions | None,
    markdown_dir: Path | None,
    context: dict[str, Any] | None,
) -> Path:
    opts = options or ConversionOptions()
    document = parse(markdown_text, opts, context=context)
    docx_doc = load_template(template_path)
    Renderer(docx_doc, opts, markdown_dir).render(document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    docx_doc.save(str(output_path))
    return output_path


class MarkdownDocxConverter:
    """Reusable converter holding template, options, and a default
    Jinja2 context.

    Per-call ``context`` arguments are merged over ``default_context``
    (call-site keys win).
    """

    def __init__(
        self,
        template_path: str | Path | None = None,
        options: ConversionOptions | None = None,
        default_context: dict[str, Any] | None = None,
    ) -> None:
        self.template_path = template_path
        self.options = options or ConversionOptions()
        self.default_context: dict[str, Any] = dict(default_context or {})

    def convert_text(
        self,
        markdown_text: str,
        output_path: str | Path,
        *,
        context: dict[str, Any] | None = None,
    ) -> Path:
        return convert_markdown_text(
            markdown_text,
            output_path,
            template_path=self.template_path,
            options=self.options,
            context=self._merge_context(context),
        )

    def convert_file(
        self,
        markdown_path: str | Path,
        output_path: str | Path,
        *,
        context: dict[str, Any] | None = None,
    ) -> Path:
        return convert_markdown_file(
            markdown_path,
            output_path,
            template_path=self.template_path,
            options=self.options,
            context=self._merge_context(context),
        )

    def _merge_context(
        self, override: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if not self.default_context and not override:
            return None
        return {**self.default_context, **(override or {})}
