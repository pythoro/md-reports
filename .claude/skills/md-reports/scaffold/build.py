"""Build this report: data -> figures -> build/report.md -> report.docx.

Run from anywhere:

    uv run python reports/<slug>/build.py

Everything this script writes goes under ``build/``, which is
generated and safe to delete. Source files (this script,
``report.md``, ``data/``, ``assets/``) are never modified.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed
import matplotlib.pyplot as plt  # noqa: E402

from md_reports import (  # noqa: E402
    ConversionOptions,
    convert_markdown_file,
    render_markdown_template,
)

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
FIGURES = BUILD / "figures"

TITLE = "Quarterly Sales Report"
OPTIONS = ConversionOptions(strict_mode=True)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def md_table(rows: list[dict[str, str]]) -> str:
    """Render rows as a pipe table (previews well, unlike csv fences)."""
    headers = list(rows[0])
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(r[h] for h in headers) + " |" for r in rows]
    return "\n".join(lines)


def make_figures(rows: list[dict[str, str]]) -> None:
    quarters = [r["quarter"] for r in rows]
    revenue = [float(r["revenue"]) for r in rows]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(quarters, revenue)
    ax.set_ylabel("Revenue ($k)")
    fig.tight_layout()
    fig.savefig(FIGURES / "revenue.png", dpi=150)
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    if (HERE / "assets").is_dir():
        shutil.copytree(HERE / "assets", BUILD / "assets", dirs_exist_ok=True)

    rows = load_rows(HERE / "data" / "sales.csv")
    make_figures(rows)

    revenue = [float(r["revenue"]) for r in rows]
    growth = (revenue[-1] - revenue[0]) / revenue[0] * 100
    context = {
        "title": TITLE,
        "total": f"{sum(revenue):,.0f}",
        "growth": f"{growth:.1f}",
        "sales_table": md_table(rows),
    }

    source = (HERE / "report.md").read_text(encoding="utf-8")
    built_md = BUILD / "report.md"
    built_md.write_text(
        render_markdown_template(source, context, options=OPTIONS),
        encoding="utf-8",
    )

    docx = convert_markdown_file(
        built_md,
        BUILD / "report.docx",
        options=OPTIONS,
        properties={"title": TITLE},
    )
    print(f"Wrote {built_md}")
    print(f"Wrote {docx}")


if __name__ == "__main__":
    main()
