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
        sandboxed_context: When True, the Jinja2 substitution step uses
            :class:`jinja2.sandbox.SandboxedEnvironment`, blocking
            access to most attributes and built-ins. Enable when the
            markdown source is not fully trusted. Note: sandboxing
            blocks dunder/attribute access in expressions, which can
            disable duck-typed filter calls like ``{{ df | to_csv }}``
            depending on what attributes the filter touches.
        confine_assets: When True, image and CSV asset paths must
            resolve to a location *under* the asset base
            (``project_root`` if set, otherwise the markdown file's
            directory). Absolute paths and ``..`` traversals that
            escape the base are rejected (warned, or raised under
            ``strict_mode``). Enable when the markdown source is not
            fully trusted.
    """

    strict_mode: bool = False
    figure_caption_prefix: str = "Figure"
    table_caption_prefix: str = "Table"
    project_root: str | Path | None = None
    sandboxed_context: bool = False
    confine_assets: bool = False
