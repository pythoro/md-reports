"""Public conversion API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from md_reports.errors import ValidationError
from md_reports.options import ConversionOptions
from md_reports.parser import parse
from md_reports.renderers.base import BaseRenderer
from md_reports.renderers.docx import DocxRenderer


def convert_markdown_text(
    markdown_text: str,
    output_path: str | Path,
    *,
    renderer: BaseRenderer | None = None,
    options: ConversionOptions | None = None,
    context: dict[str, Any] | None = None,
    properties: dict[str, str] | None = None,
) -> Path:
    """Convert a Markdown string to a document at ``output_path``.

    The output format is decided by ``renderer``. If omitted, defaults
    to :class:`DocxRenderer` so a plain ``.docx`` is produced.

    If ``options`` is given alongside ``renderer``, ``ValidationError``
    is raised — pass options to whichever you construct, not both.

    If ``context`` is provided, the markdown is rendered as a Jinja2
    template against it before parsing.

    ``properties`` sets document-level metadata (e.g. ``title``,
    ``author``, ``subject``, ``keywords``/``tags``, ``comments``,
    ``category``). Values land on the DOCX's core properties and feed
    template fields like ``{ TITLE }`` or ``{ AUTHOR }``.
    """
    if not isinstance(markdown_text, str):
        raise ValidationError("markdown_text must be a string")
    return _convert(
        markdown_text=markdown_text,
        output_path=Path(output_path),
        renderer=renderer,
        options=options,
        context=context,
        properties=properties,
        markdown_dir=None,
    )


def convert_markdown_file(
    markdown_path: str | Path,
    output_path: str | Path,
    *,
    renderer: BaseRenderer | None = None,
    options: ConversionOptions | None = None,
    context: dict[str, Any] | None = None,
    properties: dict[str, str] | None = None,
) -> Path:
    """Read a Markdown file and write the rendered document to disk.

    Same parameters as :func:`convert_markdown_text` but reads the
    source from ``markdown_path``.
    """
    md_path = Path(markdown_path)
    if not md_path.exists():
        raise ValidationError(f"Markdown file not found: {md_path}")
    text = md_path.read_text(encoding="utf-8")
    return _convert(
        markdown_text=text,
        output_path=Path(output_path),
        renderer=renderer,
        options=options,
        context=context,
        properties=properties,
        markdown_dir=md_path.parent.resolve(),
    )


def _convert(
    *,
    markdown_text: str,
    output_path: Path,
    renderer: BaseRenderer | None,
    options: ConversionOptions | None,
    context: dict[str, Any] | None,
    properties: dict[str, str] | None,
    markdown_dir: Path | None,
) -> Path:
    if renderer is not None and options is not None:
        raise ValidationError(
            "Pass options to either the renderer or convert_*, not both"
        )
    opts = (renderer.options if renderer else options) or ConversionOptions()
    document = parse(markdown_text, opts, context=context)
    r = renderer or DocxRenderer(options=opts)
    return r.render(
        document,
        output_path,
        markdown_dir=markdown_dir,
        properties=properties,
    )


class MarkdownConverter:
    """Reusable converter holding renderer, options, and a default
    Jinja2 context.

    The renderer drives output format. Defaults to
    :class:`DocxRenderer`. Per-call ``context`` arguments are merged
    over ``default_context`` (call-site keys win).
    """

    def __init__(
        self,
        renderer: BaseRenderer | None = None,
        options: ConversionOptions | None = None,
        default_context: dict[str, Any] | None = None,
        default_properties: dict[str, str] | None = None,
    ) -> None:
        if renderer is not None and options is not None:
            raise ValidationError(
                "Pass options to either the renderer or "
                "MarkdownConverter, not both"
            )
        self.options = (
            renderer.options if renderer else options
        ) or ConversionOptions()
        self.renderer: BaseRenderer = renderer or DocxRenderer(
            options=self.options
        )
        self.default_context: dict[str, Any] = dict(default_context or {})
        self.default_properties: dict[str, str] = dict(
            default_properties or {}
        )

    def convert_text(
        self,
        markdown_text: str,
        output_path: str | Path,
        *,
        context: dict[str, Any] | None = None,
        properties: dict[str, str] | None = None,
    ) -> Path:
        return convert_markdown_text(
            markdown_text,
            output_path,
            renderer=self.renderer,
            context=self._merge_context(context),
            properties=self._merge_properties(properties),
        )

    def convert_file(
        self,
        markdown_path: str | Path,
        output_path: str | Path,
        *,
        context: dict[str, Any] | None = None,
        properties: dict[str, str] | None = None,
    ) -> Path:
        return convert_markdown_file(
            markdown_path,
            output_path,
            renderer=self.renderer,
            context=self._merge_context(context),
            properties=self._merge_properties(properties),
        )

    def _merge_context(
        self, override: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if not self.default_context and not override:
            return None
        return {**self.default_context, **(override or {})}

    def _merge_properties(
        self, override: dict[str, str] | None
    ) -> dict[str, str] | None:
        if not self.default_properties and not override:
            return None
        return {**self.default_properties, **(override or {})}
