"""Tables, CSV embedding, and auto-numbered captions.

Three ways to put tabular data into the document:

1. A standard markdown table.
2. A ``csv-file`` fenced block — the body is a path to a CSV file.
3. A ``csv`` fenced block — the body is the literal CSV data.

A paragraph that begins with ``Table:`` immediately before any table
is consumed as a Caption-styled, auto-numbered caption above the
table. Figure and table counters are independent.

Relative asset paths in the markdown are resolved against the markdown
file's directory by default, or against ``ConversionOptions.project_root``
when set — used here so the inline ``csv-file`` reference finds
``assets/quarterly.csv``.

Run from the repo root:

    uv run python examples/03_tables_and_csv.py
"""

from __future__ import annotations

from pathlib import Path

from md_reports import ConversionOptions, convert_markdown_text

EXAMPLES = Path(__file__).parent
OUT = EXAMPLES / "output"
OUT.mkdir(exist_ok=True)


MARKDOWN = """\
# Tabular data

## Markdown table

Table: Revenue by region (USD millions, markdown source).

| Region | Q1 | Q2 | Q3 | Q4 |
|--------|---:|---:|---:|---:|
| EMEA   |  4 |  6 |  7 |  9 |
| APAC   |  3 |  4 |  5 |  6 |
| AMER   |  8 |  9 | 11 | 12 |

## CSV file embed

Table: Revenue by region (loaded from CSV).

```csv-file
assets/quarterly.csv
```

## Inline CSV

Table: Headcount by team (inline CSV literal).

```csv
team,2024,2025,2026
Platform,12,14,18
Research,7,9,11
GTM,20,22,25
```
"""


def main() -> None:
    out = OUT / "03_tables_and_csv.docx"
    convert_markdown_text(
        MARKDOWN,
        out,
        options=ConversionOptions(project_root=EXAMPLES),
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
