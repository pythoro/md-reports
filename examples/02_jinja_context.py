"""Inject Python values into markdown via the Jinja2 ``context``.

The full Jinja2 syntax is available — variables, filters, conditionals,
and loops. Substitution runs once on the raw markdown text before
parsing, so values flow into headings, body text, captions, table
cells, image paths, and link URLs alike.

Run from the repo root:

    uv run python examples/02_jinja_context.py
"""

from __future__ import annotations

from pathlib import Path

from md_reports import convert_markdown_text

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


TEMPLATE = """\
# {{ title | upper }}

Prepared for **{{ client }}** on {{ date }}.

## Findings

{% for finding in findings %}
{{ loop.index }}. {{ finding }}
{% endfor %}

{% if show_appendix %}
## Appendix

See [the source data]({{ appendix_url }}).
{% endif %}
"""


def main() -> None:
    context = {
        "title": "q1 results",
        "client": "Acme Corp",
        "date": "2026-04-27",
        "findings": [
            "Revenue grew 14.5% year over year.",
            "Three new regions came online.",
            "Operating costs held flat.",
        ],
        "show_appendix": True,
        "appendix_url": "https://example.com/q1-data",
    }
    out = OUT / "02_jinja_context.docx"
    convert_markdown_text(TEMPLATE, out, context=context)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
