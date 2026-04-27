"""Convert markdown to DOCX — the simplest possible usage.

Two forms are shown:

* ``convert_markdown_text`` — pass a markdown string directly.
* ``convert_markdown_file`` — read from a ``.md`` file on disk. Relative
  asset paths in the markdown resolve against the file's directory.

Run from the repo root:

    uv run python examples/01_quickstart.py
"""

from __future__ import annotations

from pathlib import Path

from md_reports import convert_markdown_file, convert_markdown_text

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


def from_string() -> None:
    md = (
        "# Hello, md-reports\n\n"
        "This document was generated from a Python string.\n\n"
        "- Bold: **important**\n"
        "- Italic: *gentle emphasis*\n"
        "- Code: `convert_markdown_text(...)`\n"
        "- A link: [Anthropic](https://www.anthropic.com)\n"
    )
    convert_markdown_text(md, OUT / "01_from_string.docx")
    print(f"wrote {OUT / '01_from_string.docx'}")


def from_file() -> None:
    src = Path(__file__).parent / "sample_report.md"
    convert_markdown_file(src, OUT / "01_from_file.docx")
    print(f"wrote {OUT / '01_from_file.docx'}")


if __name__ == "__main__":
    from_string()
    from_file()
