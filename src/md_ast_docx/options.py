"""Configuration options for conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConversionOptions:
    """Knobs controlling Markdown to DOCX conversion.

    Attributes:
        strict_mode: When True, unsupported constructs, missing assets,
            and link/caption failures raise instead of warning.
        figure_caption_prefix: Label used before the SEQ counter in
            figure captions (default ``Figure``).
        table_caption_prefix: Label used before the SEQ counter in
            table captions (default ``Table``). Also recognised as the
            leading marker on a paragraph that supplies a table caption
            in markdown source.
        project_root: Root for resolving relative paths to external
            assets (images and CSV files). When None, paths resolve
            against the markdown file's directory (for
            ``convert_markdown_file``) or the current working directory
            (for ``convert_markdown_text``).
    """

    strict_mode: bool = False
    figure_caption_prefix: str = "Figure"
    table_caption_prefix: str = "Table"
    project_root: str | Path | None = None
