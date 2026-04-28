"""Embed generated charts as figures and cross-reference them in prose.

A block-level image (an ``![alt](path)`` that is the only content of
its paragraph) becomes a figure: the picture is followed by a
Caption-styled paragraph ``Figure N: <alt>`` whose number comes from a
Word ``SEQ`` field. Figure and table counters are independent, so a
document mixing both stays correctly numbered.

This example also demonstrates **cross-references**. Append
``{#label}`` to a figure's alt text or a table caption to mark a
target, then refer to it from anywhere in the document with a markdown
link whose href is ``#label``:

* ``[Figure 1](#fig-revenue)`` — link text becomes the cached display
  value (and is what shows until Word updates fields with F9).
* ``[](#fig-revenue)`` — empty link text auto-fills with
  ``"<Prefix> <N>"`` (e.g. ``Figure 1``) from the parser's pre-walk,
  so forward references work too.

In the produced DOCX, each labelled caption is wrapped in a Word
bookmark and each ``#label`` link becomes a Word ``REF`` field, so
reordering or inserting figures keeps numbers and references in sync
once Word recomputes fields.

Relative image paths in the markdown resolve against the markdown
file's directory by default, or against ``ConversionOptions.project_root``
when set — used here to point at a temporary directory holding the
chart PNG. The temp directory is cleaned up after the conversion;
the embedded copy lives inside the DOCX.

Requires the ``examples`` extra::

    uv sync --extra examples
    uv run python examples/07_figures.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from md_reports import ConversionOptions, convert_markdown_text

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


MARKDOWN = """\
# Quarterly performance

This report cross-references a few figures and a table. Forward
references work too: see [](#fig-headcount) further down for headcount
detail, and [Table 1](#tab-headline) at the end for the headline
numbers.

## Revenue trend

[](#fig-revenue) shows quarterly revenue across our three regions.

![Quarterly revenue by region {#fig-revenue}](revenue.png)

Revenue continued to climb through the year, with **AMER** leading the
pack. See [the headcount chart](#fig-headcount) for a complementary
view.

## Headcount

![Headcount by team {#fig-headcount}](headcount.png)

Both charts get independent ``Figure N`` numbers, regardless of any
tables that appear between or around them. The closing summary in
[](#tab-headline) ties them together.

Table: Closing headline numbers. {#tab-headline}

| Metric           | 2026 |
|------------------|-----:|
| Revenue (USD M)  |   54 |
| Headcount        |   54 |
"""


def _render_revenue_chart(path: Path) -> None:
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    series = {
        "EMEA": [4, 6, 7, 9],
        "APAC": [3, 4, 5, 6],
        "AMER": [8, 9, 11, 12],
    }
    fig, ax = plt.subplots(figsize=(6, 3.2))
    for label, values in series.items():
        ax.plot(quarters, values, marker="o", label=label)
    ax.set_ylabel("Revenue (USD millions)")
    ax.set_title("Quarterly revenue")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _render_headcount_chart(path: Path) -> None:
    teams = ["Platform", "Research", "GTM"]
    counts_2025 = [14, 9, 22]
    counts_2026 = [18, 11, 25]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = range(len(teams))
    ax.bar([i - 0.2 for i in x], counts_2025, width=0.4, label="2025")
    ax.bar([i + 0.2 for i in x], counts_2026, width=0.4, label="2026")
    ax.set_xticks(list(x))
    ax.set_xticklabels(teams)
    ax.set_ylabel("Headcount")
    ax.set_title("Team size, year over year")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        _render_revenue_chart(tmpdir / "revenue.png")
        _render_headcount_chart(tmpdir / "headcount.png")
        out = OUT / "07_figures.docx"
        convert_markdown_text(
            MARKDOWN,
            out,
            options=ConversionOptions(project_root=tmpdir),
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
