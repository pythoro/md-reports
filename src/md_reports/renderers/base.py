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
from dataclasses import dataclass, field
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

    ``label_registry`` maps user-defined labels (from ``{#label}``
    markers on figures and tables) to ``(prefix, number)`` so
    cross-references can resolve forward and backward.
    """

    markdown_dir: Path | None = None
    figure_counter: int = 0
    table_counter: int = 0
    label_registry: dict[str, tuple[str, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class CaptionNumber:
    """The number a caption receives.

    ``chapter`` is the chapter part (``"2"``, ``"1.3"``) or ``None``
    when chapter numbering is off. ``status`` is ``"ok"``, or one of
    ``"before_first_chapter"`` / ``"stale_chapter"`` when the caption
    sits where Word's chapter lookup will not give a sensible number.
    """

    chapter: str | None
    seq: int
    separator: str = "-"
    status: str = "ok"

    @property
    def display(self) -> str:
        if self.chapter is None:
            return str(self.seq)
        return f"{self.chapter}{self.separator}{self.seq}"


class CaptionNumberer:
    """Track chapter and caption counters during a render walk.

    Mirrors Word's caption fields so cached values match what Word
    shows after a field update (verified against Word): the chapter
    part is the number of the most recent heading at ``level`` (as
    ``STYLEREF`` finds it), and counters restart at every heading at
    ``level`` *or above* (as ``SEQ \\s`` does). With ``level=None``
    numbering is document-wide.

    Before the first heading at ``level`` Word's ``STYLEREF`` looks
    forward to the next one; the renderer fills that number in once
    it is known (see :attr:`last_chapter`).
    """

    def __init__(self, level: int | None, separator: str = "-") -> None:
        self.level = level
        self.separator = separator
        self._path: list[int] = [0] * (level or 0)
        self._last_chapter: str | None = None
        # A heading above ``level`` arrived since the last chapter.
        self._stale = False
        self._counters: dict[str, int] = {}

    def on_heading(self, level: int) -> None:
        """Record a heading at ``level`` (1 = top)."""
        if self.level is None or level > self.level:
            return
        self._path[level - 1] += 1
        for i in range(level, self.level):
            self._path[i] = 0
        self._counters.clear()
        if level == self.level:
            self._last_chapter = ".".join(str(n) for n in self._path)
            self._stale = False
        else:
            self._stale = self._last_chapter is not None

    @property
    def last_chapter(self) -> str | None:
        """Number of the most recent heading at ``level``, if any."""
        return self._last_chapter

    def next(self, kind: str) -> CaptionNumber:
        """Return the next number for caption ``kind`` (e.g. figure)."""
        seq = self._counters.get(kind, 0) + 1
        self._counters[kind] = seq
        if self.level is None:
            return CaptionNumber(None, seq)
        if self._last_chapter is None:
            return CaptionNumber(
                "0", seq, self.separator, "before_first_chapter"
            )
        status = "stale_chapter" if self._stale else "ok"
        return CaptionNumber(self._last_chapter, seq, self.separator, status)


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
        properties: dict[str, str] | None = None,
    ) -> Path:
        """Render ``document`` to ``output_path`` and return the path.

        ``properties`` carries document-level metadata (title, author,
        etc.). Concrete renderers may apply or ignore it depending on
        the format's metadata model.
        """

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

        When :attr:`ConversionOptions.confine_assets` is set, the
        resolved path must lie under the asset base
        (``project_root`` if configured, otherwise the markdown
        directory or CWD); absolute paths and ``..`` traversals that
        escape the base are rejected.
        """
        if src.startswith(("http://", "https://")):
            self._warn_or_raise(f"Remote {kind} not supported: {src}")
            return None
        base = self._asset_base(ctx).resolve()
        candidate = Path(src)
        if candidate.drive:
            # Windows drive-anchored (e.g. "C:/foo") or
            # UNC ("\\\\server\\share\\foo").
            # True absolute — resolve directly.
            resolved = candidate.resolve()
        elif src.startswith(("/", "\\")):
            # Leading-slash convention: resolve relative to the asset base
            # ("project root"), matching HTML/web semantics. Without this,
            # pathlib's join drops the base's directory on Windows
            # (Path("C:/x") / "/y" -> Path("C:/y")) and POSIX treats the path
            # as filesystem-absolute.
            resolved = (base / Path(src.lstrip("/\\"))).resolve()
        else:
            resolved = (base / candidate).resolve()
        if self.options.confine_assets:
            try:
                resolved.relative_to(base)
            except ValueError:
                self._warn_or_raise(
                    f"{kind.capitalize()} path escapes asset base "
                    f"(confine_assets=True): {src!r}"
                )
                return None
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
