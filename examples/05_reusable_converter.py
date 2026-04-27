"""Reuse a converter across multiple reports with a shared context.

``MarkdownConverter`` keeps the renderer (and its loaded template)
alive across calls, and accepts a ``default_context`` that gets merged
with each per-call ``context`` (call-site keys win on conflict).

Use this when you're producing many reports back-to-back — quarterly
roll-ups, per-customer briefs, etc. — and want to share branding,
shared metadata, and a single template load.

Run from the repo root:

    uv run python examples/05_reusable_converter.py
"""

from __future__ import annotations

from pathlib import Path

from md_reports import MarkdownConverter

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


TEMPLATE = """\
# {{ company }} — {{ quarter }} brief

Prepared by {{ author }} for the {{ company }} board.

## Headline

{{ headline }}

## Numbers

| Metric  | Value |
|---------|------:|
| Revenue | {{ revenue }} |
| Growth  | {{ growth }}% |
"""


def main() -> None:
    conv = MarkdownConverter(
        default_context={
            "company": "Acme Corp",
            "author": "Reporting Bot",
        },
    )
    quarters = [
        {
            "quarter": "Q1",
            "headline": "Steady growth across all regions.",
            "revenue": "$12M",
            "growth": 14.5,
        },
        {
            "quarter": "Q2",
            "headline": "APAC expansion drove a record quarter.",
            "revenue": "$15M",
            "growth": 21.0,
        },
    ]
    for q in quarters:
        out = OUT / f"05_brief_{q['quarter'].lower()}.docx"
        conv.convert_text(TEMPLATE, out, context=q)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
