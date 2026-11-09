"""Heading list numbering, used for chapter-numbered captions.

Word's chapter-numbered captions (``Figure { STYLEREF 1 \\s }-{ SEQ
Figure \\s 1 }``) read the chapter number from the list numbering of
the chapter heading. These helpers inspect a document's heading
numbering and, when there is none, add a plain ``1`` / ``1.1`` scheme
to the output document.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

from docx.document import Document as DocxDoc
from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.parts.numbering import NumberingPart


def _numbering_element(doc: DocxDoc) -> Any | None:
    """Return the ``w:numbering`` root, or None if the doc has none."""
    try:
        part = doc.part.part_related_by(RT.NUMBERING)
    except KeyError:
        return None
    return part.element


def _get_or_add_numbering_element(doc: DocxDoc) -> Any:
    """Return the ``w:numbering`` root, creating the part if missing.

    ``doc.part.numbering_part`` is not used: when the part is missing
    python-docx calls ``NumberingPart.new()``, which raises
    ``NotImplementedError``.
    """
    numbering = _numbering_element(doc)
    if numbering is not None:
        return numbering
    part = NumberingPart(
        PackURI("/word/numbering.xml"),
        CT.WML_NUMBERING,
        parse_xml(f"<w:numbering {nsdecls('w')}/>"),
        doc.part.package,
    )
    doc.part.relate_to(part, RT.NUMBERING)
    return part.element


def _val(el: Any | None, tag: str) -> str | None:
    if el is None:
        return None
    child = el.find(qn(tag))
    return None if child is None else child.get(qn("w:val"))


def _effective_num_pr(style: Any) -> tuple[int, int] | None:
    """Return ``(numId, ilvl)`` a style applies, following ``basedOn``.

    The nearest style in the chain that sets ``w:numPr`` wins. A
    ``numId`` of 0 (numbering explicitly off) returns None.
    """
    seen: set[str] = set()
    while style is not None and style.style_id not in seen:
        seen.add(style.style_id)
        ppr = style.element.pPr
        num_pr = None if ppr is None else ppr.find(qn("w:numPr"))
        if num_pr is not None:
            num_id = _val(num_pr, "w:numId")
            if num_id is None or int(num_id) == 0:
                return None
            return int(num_id), int(_val(num_pr, "w:ilvl") or 0)
        style = style.base_style
    return None


def _resolve_lvl(
    doc: DocxDoc, numbering: Any, num_id: int, ilvl: int, depth: int = 0
) -> Any | None:
    """Resolve ``numId``/``ilvl`` to the ``w:lvl`` element Word uses."""
    num = _child_with(numbering, "w:num", "w:numId", str(num_id))
    if num is None:
        return None
    override = _child_with(num, "w:lvlOverride", "w:ilvl", str(ilvl))
    if override is not None and override.find(qn("w:lvl")) is not None:
        return override.find(qn("w:lvl"))
    abstract_id = _val(num, "w:abstractNumId")
    abstract = _child_with(
        numbering, "w:abstractNum", "w:abstractNumId", abstract_id
    )
    if abstract is None:
        return None
    link = _val(abstract, "w:numStyleLink")
    if link is not None:
        # Numbering defined through a list style: follow that style.
        if depth >= 3:
            return None
        for style in doc.styles:
            if style.style_id == link:
                target = _effective_num_pr(style)
                if target is None:
                    return None
                return _resolve_lvl(doc, numbering, target[0], ilvl, depth + 1)
        return None
    return _child_with(abstract, "w:lvl", "w:ilvl", str(ilvl))


def _child_with(
    parent: Any, tag: str, attr: str, value: str | None
) -> Any | None:
    """First ``tag`` child of ``parent`` whose ``attr`` equals
    ``value``. Avoids ``xpath``, which needs a namespace map that
    plain (non-oxml) lxml elements lack."""
    for child in parent.findall(qn(tag)):
        if child.get(qn(attr)) == value:
            return child
    return None


def heading_numbering_levels(
    doc: DocxDoc, up_to_level: int
) -> list[Any | None]:
    """Return the numbering ``w:lvl`` for each of Heading 1..N.

    An entry is None when that heading style is not usefully numbered:
    no ``numPr``, ``numId`` 0, an unresolvable definition, ``numFmt``
    ``none``, or a ``lvlText`` without its own level placeholder (so
    ``STYLEREF \\s`` would find no number). The heading styles must
    exist.
    """
    numbering = _numbering_element(doc)
    levels: list[Any | None] = []
    for n in range(1, up_to_level + 1):
        target = _effective_num_pr(doc.styles[f"Heading {n}"])
        lvl = None
        if target is not None and numbering is not None:
            lvl = _resolve_lvl(doc, numbering, *target)
        if lvl is not None:
            ilvl = int(lvl.get(qn("w:ilvl")) or 0)
            fmt = _val(lvl, "w:numFmt") or "decimal"
            text = _val(lvl, "w:lvlText") or ""
            if fmt == "none" or f"%{ilvl + 1}" not in text:
                lvl = None
        levels.append(lvl)
    return levels


def numbering_state(levels: list[Any | None]) -> str:
    """Classify heading numbering: ``"none"``, ``"all"`` or
    ``"partial"``."""
    numbered = [lvl is not None for lvl in levels]
    if all(numbered):
        return "all"
    if not any(numbered):
        return "none"
    return "partial"


def numbering_is_plain_decimal(levels: list[Any | None]) -> bool:
    """True if Word's chapter number reads ``1``, ``1.2``, ...

    Every level must be decimal and start at 1, and the chapter
    level's text must join the level numbers with ``.`` (surrounding
    literal text such as ``Chapter %1`` is fine; ``STYLEREF \\s``
    drops it). Decides whether cached chapter numbers are exact.
    """
    for lvl in levels:
        if lvl is None:
            return False
        if (_val(lvl, "w:numFmt") or "decimal") != "decimal":
            return False
        if _val(lvl, "w:start") != "1":
            return False
    text = _val(levels[-1], "w:lvlText") or ""
    m = re.search(r"%\d(?:[^%]*%\d)*", text)
    expected = ".".join(f"%{i}" for i in range(1, len(levels) + 1))
    return m is not None and m.group(0) == expected


def _lvl_xml(ilvl: int, up_to_level: int, style_ids: list[str]) -> str:
    if ilvl < up_to_level:
        text = ".".join(f"%{k}" for k in range(1, ilvl + 2))
        return (
            f'<w:lvl w:ilvl="{ilvl}"><w:start w:val="1"/>'
            '<w:numFmt w:val="decimal"/>'
            f'<w:pStyle w:val="{style_ids[ilvl]}"/>'
            '<w:suff w:val="space"/>'
            f'<w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/>'
            '<w:pPr><w:ind w:left="0" w:hanging="0"/></w:pPr>'
            "</w:lvl>"
        )
    return (
        f'<w:lvl w:ilvl="{ilvl}"><w:start w:val="1"/>'
        '<w:numFmt w:val="none"/><w:suff w:val="nothing"/>'
        '<w:lvlText w:val=""/><w:lvlJc w:val="left"/>'
        "</w:lvl>"
    )


def _inherits_from(style: Any, style_ids: set[str]) -> bool:
    base = style.base_style
    seen: set[str] = set()
    while base is not None and base.style_id not in seen:
        if base.style_id in style_ids:
            return True
        seen.add(base.style_id)
        base = base.base_style
    return False


def add_heading_numbering(doc: DocxDoc, up_to_level: int) -> None:
    """Number Heading 1..N as ``1``, ``1.1``, ... via a new list.

    Adds a multilevel ``w:abstractNum`` (before the first ``w:num``,
    as the schema requires) and a ``w:num``, and links Heading 1..N to
    it. Paragraph styles inheriting from those headings via
    ``basedOn`` (e.g. ``TOC Heading``) get ``numId`` 0 so they are not
    numbered or counted as chapters. Only ``doc`` changes, never the
    template file it was loaded from.
    """
    numbering = _get_or_add_numbering_element(doc)
    ids = [
        int(a.get(qn("w:abstractNumId")))
        for a in numbering.findall(qn("w:abstractNum"))
    ]
    abstract_id = max(ids) + 1 if ids else 0
    style_ids = [
        doc.styles[f"Heading {n}"].style_id for n in range(1, up_to_level + 1)
    ]
    abstract = parse_xml(
        f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{abstract_id}">'
        f'<w:nsid w:val="{secrets.token_hex(4).upper()}"/>'
        '<w:multiLevelType w:val="multilevel"/>'
        + "".join(_lvl_xml(i, up_to_level, style_ids) for i in range(9))
        + "</w:abstractNum>"
    )
    anchor = numbering.find(qn("w:num"))
    if anchor is None:
        anchor = numbering.find(qn("w:numIdMacAtCleanup"))
    if anchor is not None:
        anchor.addprevious(abstract)
    else:
        numbering.append(abstract)
    num_id = numbering.add_num(abstract_id).numId

    for n in range(1, up_to_level + 1):
        style = doc.styles[f"Heading {n}"]
        num_pr = style.element.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_ilvl().val = n - 1
        num_pr.get_or_add_numId().val = num_id

    numbered = set(style_ids)
    for style in doc.styles:
        if style.style_id in numbered:
            continue
        if style.element.get(qn("w:type")) != "paragraph":
            continue
        if not _inherits_from(style, numbered):
            continue
        ppr = style.element.pPr
        if ppr is not None and ppr.find(qn("w:numPr")) is not None:
            continue
        num_pr = style.element.get_or_add_pPr().get_or_add_numPr()
        num_pr.get_or_add_numId().val = 0
