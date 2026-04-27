"""Embed a pandas DataFrame as a DOCX table.

The built-in ``to_csv`` Jinja2 filter calls ``.to_csv(index=False)`` on
the value and strips the trailing newline. Drop the result inside a
``csv`` fence and it becomes a real DOCX table — header bolded, shared
``Table N`` counter, and the same caption rules as any other table.

The filter is duck-typed on ``.to_csv()``, so pandas is **not** a
dependency of ``md-reports``. This example uses pandas if it's
installed; otherwise it falls back to a tiny stand-in that exposes the
same method.

Run from the repo root:

    uv run python examples/04_dataframe.py
"""

from __future__ import annotations

from pathlib import Path

from md_reports import convert_markdown_text

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


def _make_dataframe():
    try:
        import pandas as pd
    except ImportError:
        return _MiniDF(
            ["region", "q1", "q2", "q3", "q4"],
            [
                ["EMEA", 4, 6, 7, 9],
                ["APAC", 3, 4, 5, 6],
                ["AMER", 8, 9, 11, 12],
            ],
        )
    return pd.DataFrame(
        {
            "region": ["EMEA", "APAC", "AMER"],
            "q1": [4, 3, 8],
            "q2": [6, 4, 9],
            "q3": [7, 5, 11],
            "q4": [9, 6, 12],
        }
    )


class _MiniDF:
    """Stand-in used when pandas is not installed."""

    def __init__(self, columns: list[str], rows: list[list[object]]) -> None:
        self.columns = columns
        self.rows = rows

    def to_csv(self, *, index: bool = True, sep: str = ",") -> str:
        lines = [sep.join(self.columns)]
        lines.extend(sep.join(str(c) for c in r) for r in self.rows)
        return "\n".join(lines) + "\n"


MARKDOWN = """\
# Quarterly revenue

Table: Revenue by region (sourced from a DataFrame).

```csv
{{ df | to_csv }}
```

The same DataFrame, with a different separator passed through to
``to_csv``:

Table: Same data, semicolon-delimited.

```csv
{{ df | to_csv(sep=';') }}
```
"""


def main() -> None:
    df = _make_dataframe()
    out = OUT / "04_dataframe.docx"
    convert_markdown_text(MARKDOWN, out, context={"df": df})
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
