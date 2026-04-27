"""Regenerate the packaged default DOCX template.

Source of truth for any non-trivial style additions to
``src/md_reports/renderers/docx/resources/default_template.docx``.

Run from the repo root::

    uv run python scripts/build_default_template.py

The script edits the template in place. The template starts life as
the default that ``python-docx`` ships and is then patched here so
that styles ``md-reports`` relies on (currently: ``Caption``) have
concrete formatting rather than only a latent-style placeholder.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "md_reports"
    / "renderers"
    / "docx"
    / "resources"
    / "default_template.docx"
)


def _find_concrete_style(styles_el, style_id: str):
    for s in styles_el.findall(qn("w:style")):
        if s.get(qn("w:styleId")) == style_id:
            return s
    return None


def _build_caption_style():
    style = OxmlElement("w:style")
    style.set(qn("w:type"), "paragraph")
    style.set(qn("w:styleId"), "Caption")

    name = OxmlElement("w:name")
    name.set(qn("w:val"), "caption")
    style.append(name)

    based_on = OxmlElement("w:basedOn")
    based_on.set(qn("w:val"), "Normal")
    style.append(based_on)

    nxt = OxmlElement("w:next")
    nxt.set(qn("w:val"), "Normal")
    style.append(nxt)

    ui_priority = OxmlElement("w:uiPriority")
    ui_priority.set(qn("w:val"), "35")
    style.append(ui_priority)

    style.append(OxmlElement("w:qFormat"))

    pPr = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "120")
    spacing.set(qn("w:after"), "240")
    pPr.append(spacing)
    style.append(pPr)

    rPr = OxmlElement("w:rPr")
    rPr.append(OxmlElement("w:i"))
    rPr.append(OxmlElement("w:iCs"))
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "595959")
    rPr.append(color)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "20")
    rPr.append(sz)
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), "20")
    rPr.append(szCs)
    style.append(rPr)

    return style


def main() -> None:
    if not TEMPLATE_PATH.exists():
        raise SystemExit(f"Template not found: {TEMPLATE_PATH}")

    doc = Document(str(TEMPLATE_PATH))
    styles_el = doc.styles.element

    existing = _find_concrete_style(styles_el, "Caption")
    if existing is not None:
        styles_el.remove(existing)
        action = "replaced"
    else:
        action = "added"

    styles_el.append(_build_caption_style())
    doc.save(str(TEMPLATE_PATH))
    print(f"{action} concrete Caption style in {TEMPLATE_PATH}")


if __name__ == "__main__":
    main()
