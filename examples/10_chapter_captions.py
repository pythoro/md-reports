"""Number figure and table captions per chapter.

``ConversionOptions(caption_chapter_level=1)`` numbers captions within
each ``#`` chapter, so the second figure in chapter 2 reads
``Figure 2.2`` (with ``caption_chapter_separator="."``) instead of a
document-wide ``Figure 5``. Cross-references auto-fill in the same
form.

This uses Word's own chapter numbering. The chapter part of the
caption is a ``STYLEREF`` field that reads the heading's list number,
so chapter headings are numbered in the output (``1 Introduction``).
The default template has no heading numbering, so it is added to the
output document.

Every ``#`` heading is a chapter. Don't use ``#`` for the document
title here; put the title in the template, or use
``caption_chapter_level=2``.

Run from the repo root::

    uv run python examples/10_chapter_captions.py
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

from md_reports import ConversionOptions, convert_markdown_text

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

# A 1x1 PNG keeps the example free of plotting dependencies; see
# 07_figures.py for real charts.
PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQ"
    "VR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


MARKDOWN = """\
# Introduction

This report has two chapters. Figures and tables are numbered within
each chapter: see [](#fig-scope) and [](#tab-sites), and, further on,
[](#fig-trend).

![Project scope {#fig-scope}](chart.png)

## Sites

Sub-sections do not start a new chapter, so numbering carries on.

Table: Sites in scope {#tab-sites}

| Site   | Region |
|--------|--------|
| Alpha  | EMEA   |
| Bravo  | APAC   |

# Results

Numbering restarts in each chapter: [](#fig-trend) is the first
figure of chapter 2, and [](#tab-totals) its first table.

![Quarterly trend {#fig-trend}](chart.png)

Table: Totals by site {#tab-totals}

| Site   | Total |
|--------|------:|
| Alpha  |    12 |
| Bravo  |     9 |
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "chart.png").write_bytes(PIXEL)
        out = OUT / "10_chapter_captions.docx"
        convert_markdown_text(
            MARKDOWN,
            out,
            options=ConversionOptions(
                project_root=tmpdir,
                caption_chapter_level=1,
                caption_chapter_separator=".",
            ),
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
