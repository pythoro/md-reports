"""Set DOCX document properties (title, author, subject, etc.).

The ``properties`` keyword on ``convert_markdown_text`` /
``convert_markdown_file`` writes user-supplied metadata into the
DOCX's core properties (``docProps/core.xml``). These are the same
properties Word's *File > Info* pane shows under "Properties", and
they drive built-in fields like ``{ TITLE }`` and ``{ AUTHOR }`` that
you can place in a template's body, header, or footer.

To make the values appear in the rendered document, edit the template
(or the default template) and insert fields via:

    Insert > Quick Parts > Field…

then pick ``Title``, ``Author``, ``Subject``, ``Keywords``, etc. The
fields render with whatever this script writes into core properties.
After opening the file, press F9 (or print) to refresh fields if Word
doesn't auto-update them.

Aliases: ``tags`` -> keywords, ``categories`` -> category, ``creator``
-> author, ``description`` -> comments. Keys are case-insensitive.

Run from the repo root::

    uv run python examples/08_properties.py
"""

from __future__ import annotations

from pathlib import Path

from md_reports import MarkdownConverter, convert_markdown_text

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


MARKDOWN = """\
# {{ title }}

Reference: **{{ reference }}** — Author: {{ author }}

This document's title and author also live on the DOCX core
properties. Add ``{ TITLE }`` and ``{ AUTHOR }`` fields to your
template (or the header / footer) and Word will display them next to
the body text once fields are updated (F9).
"""


def single_call() -> None:
    out = OUT / "08_properties.docx"
    convert_markdown_text(
        MARKDOWN,
        out,
        context={
            "title": "Q4 Report",
            "reference": "REP-2026-Q4",
            "author": "Jane Doe",
        },
        properties={
            "title": "Q4 Report",
            "author": "Jane Doe",
            "subject": "Quarterly review",
            "tags": "revenue, headcount",
            "comments": "Reference: REP-2026-Q4",
            "category": "Finance",
        },
    )
    print(f"wrote {out}")


def reusable_converter() -> None:
    """Pin defaults on a converter and override per call."""
    conv = MarkdownConverter(
        default_properties={
            "author": "Jane Doe",
            "category": "Finance",
        },
    )
    out = OUT / "08_properties_reusable.docx"
    conv.convert_text(
        MARKDOWN,
        out,
        context={
            "title": "Q1 Report",
            "reference": "REP-2027-Q1",
            "author": "Jane Doe",
        },
        properties={
            "title": "Q1 Report",
            "comments": "Reference: REP-2027-Q1",
        },
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    single_call()
    reusable_converter()
