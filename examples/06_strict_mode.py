"""Tune behavior with ``ConversionOptions`` and ``strict_mode``.

By default, problems like a missing image, a missing Jinja2 variable,
or an unsupported construct emit a ``UserWarning`` and the conversion
proceeds with a visible breadcrumb. With ``strict_mode=True`` they
raise (``ValidationError`` / ``RenderError`` / ``ParseError``) so the
caller fails fast.

This example demonstrates both halves on a markdown source that
references an undefined Jinja2 variable.

Run from the repo root:

    uv run python examples/06_strict_mode.py
"""

from __future__ import annotations

import warnings
from pathlib import Path

from md_reports import (
    ConversionOptions,
    ValidationError,
    convert_markdown_text,
)

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


SRC = "# Report for {{ client }}\n\nGrowth: **{{ pct }}%**\n"


def lenient() -> None:
    """Default mode — undefined ``client`` becomes a literal breadcrumb."""
    out = OUT / "06_lenient.docx"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        convert_markdown_text(SRC, out, context={"pct": 14.5})
    print(f"wrote {out}")
    for w in caught:
        print(f"  warning: {w.message}")


def strict() -> None:
    """Strict mode — the same source raises ``ValidationError``."""
    opts = ConversionOptions(strict_mode=True)
    try:
        convert_markdown_text(
            SRC,
            OUT / "06_strict.docx",
            options=opts,
            context={"pct": 14.5},
        )
    except ValidationError as exc:
        print(f"strict mode raised as expected: {exc}")


if __name__ == "__main__":
    lenient()
    strict()
