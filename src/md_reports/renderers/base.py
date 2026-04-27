"""Renderer-agnostic base class and shared helpers.

A concrete renderer subclasses :class:`BaseRenderer`, implements
:meth:`BaseRenderer.render`, and uses the helpers exposed here for
asset path resolution, CSV parsing, and strict-mode error dispatch.

Per-render mutable state (counters, markdown source directory, the
output handle if any) lives on a :class:`RenderContext` threaded
through the rendering walk, so a single renderer instance can be
reused across multiple ``render()`` calls without state bleeding
between them.
"""

from __future__ import annotations

import csv
import io
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from md_reports.errors import RenderError
from md_reports.model import Document
from md_reports.options import ConversionOptions


@dataclass(kw_only=True)
class RenderContext:
    """Per-render mutable state.

    Subclasses may extend this with format-specific fields (e.g. a
    DOCX document handle). Use ``kw_only`` so subclasses can add
    required fields after the base's defaulted ones.
    """

    markdown_dir: Path | None = None
    figure_counter: int = 0
    table_counter: int = 0


class BaseRenderer(ABC):
    """Abstract base for output-format renderers.

    Configuration (``options``) is set at construction and applies to
    all subsequent ``render()`` calls. Per-call inputs (the document,
    the output path, and any ``markdown_dir`` for resolving relative
    asset paths) are passed to ``render()`` directly.
    """

    def __init__(self, options: ConversionOptions | None = None) -> None:
        self.options = options or ConversionOptions()

    @abstractmethod
    def render(
        self,
        document: Document,
        output_path: Path,
        *,
        markdown_dir: Path | None = None,
    ) -> Path:
        """Render ``document`` to ``output_path`` and return the path."""

    # --- shared helpers ------------------------------------------------

    def _resolve_asset_path(
        self,
        ctx: RenderContext,
        src: str,
        *,
        kind: str = "asset",
    ) -> Path | None:
        """Resolve a relative or absolute asset path.

        Remote (``http(s)://``) sources are rejected with a warning or
        raise. Missing files are reported the same way. Returns ``None``
        if the asset cannot be used.
        """
        if src.startswith(("http://", "https://")):
            self._warn_or_raise(f"Remote {kind} not supported: {src}")
            return None
        candidate = Path(src)
        resolved = (
            candidate
            if candidate.is_absolute()
            else (self._asset_base(ctx) / candidate).resolve()
        )
        if not resolved.exists():
            self._warn_or_raise(f"{kind.capitalize()} not found: {resolved}")
            return None
        return resolved

    def _asset_base(self, ctx: RenderContext) -> Path:
        """Determine the base directory for resolving relative assets.

        ``options.project_root`` always wins when set. Otherwise falls
        back to the markdown source's directory (when known) or the
        current working directory.
        """
        if self.options.project_root is not None:
            return Path(self.options.project_root)
        if ctx.markdown_dir is not None:
            return ctx.markdown_dir
        return Path.cwd()

    def _warn_or_raise(self, msg: str) -> None:
        """Raise :class:`RenderError` in strict mode; warn otherwise."""
        if self.options.strict_mode:
            raise RenderError(msg)
        warnings.warn(msg, stacklevel=3)

    @staticmethod
    def _parse_csv_text(text: str) -> list[list[str]]:
        """Parse CSV text into a list of rows.

        Auto-detects the delimiter via :class:`csv.Sniffer` (commas,
        semicolons, tabs, pipes); falls back to comma. Returns ``[]``
        for whitespace-only input.
        """
        if not text.strip():
            return []
        try:
            dialect = csv.Sniffer().sniff(text[:1024], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        return list(csv.reader(io.StringIO(text), dialect=dialect))
