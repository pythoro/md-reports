"""Chapter-numbered captions (``caption_chapter_level``).

Expected cached values mirror what Word shows after a full field
update; they were checked against Word itself (open, ``Fields.Update``,
compare text).
"""

from __future__ import annotations

import re
import warnings
import zipfile
from pathlib import Path

import pytest
from docx import Document as DocxDocument
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml.ns import qn
from lxml import etree

from md_reports import (
    ConversionOptions,
    DocxRenderer,
    RenderError,
    TemplateError,
    ValidationError,
    convert_markdown_text,
    get_default_template_path,
)
from md_reports.renderers.base import CaptionNumberer
from md_reports.renderers.docx.numbering import add_heading_numbering
from tests.test_renderer import (
    _assert_refs_match_captions,
    _one_pixel_png,
    _open,
)

CHAPTERS = """\
# Introduction

See [](#fig-b) and [](#tab-a).

![Alpha {#fig-a}](p.png)

## Background

![Beta {#fig-b}](p.png)

Table: First table {#tab-a}

| a |
|---|
| 1 |

# Results

![Gamma {#fig-c}](p.png)

Table: Second table {#tab-b}

| a |
|---|
| 1 |

Refs: [](#fig-a), [](#fig-c), [](#tab-b).
"""


def _render(
    tmp_path: Path,
    md_text: str,
    *,
    template: Path | None = None,
    name: str = "out.docx",
    **opts,
) -> Path:
    (tmp_path / "p.png").write_bytes(_one_pixel_png())
    out = tmp_path / name
    options = ConversionOptions(project_root=tmp_path, **opts)
    if template is None:
        convert_markdown_text(md_text, out, options=options)
    else:
        convert_markdown_text(
            md_text,
            out,
            renderer=DocxRenderer(template_path=template, options=options),
        )
    return out


def _texts(path: Path) -> list[str]:
    return [p.text for p in _open(path).paragraphs if p.text]


def _captions(path: Path) -> list[str]:
    return [
        p.text for p in _open(path).paragraphs if p.style.name == "Caption"
    ]


def _part_xml(path: Path, part: str) -> bytes:
    with zipfile.ZipFile(path) as z:
        return z.read(part)


def _canonical(xml: bytes, drop_style_ids: tuple[str, ...] = ()) -> bytes:
    root = etree.fromstring(xml)
    for style in list(root.findall(qn("w:style"))):
        if style.get(qn("w:styleId")) in drop_style_ids:
            root.remove(style)
    return etree.tostring(root, method="c14n")


def _template_copy(tmp_path: Path, name: str = "tmpl.docx"):
    doc = DocxDocument(str(get_default_template_path()))
    return doc, tmp_path / name


# --- option off ---------------------------------------------------------


def test_option_off_leaves_styles_and_numbering_untouched(tmp_path):
    out = _render(tmp_path, CHAPTERS)
    template = get_default_template_path()
    # The ``Image`` style is auto-created for figures regardless of the
    # option; everything else must match the template exactly.
    for part in ("word/styles.xml", "word/numbering.xml"):
        assert _canonical(_part_xml(out, part), ("Image",)) == _canonical(
            _part_xml(template, part)
        ), part
    assert b"STYLEREF" not in _part_xml(out, "word/document.xml")
    assert _captions(out)[:2] == ["Figure 1: Alpha", "Figure 2: Beta"]


# --- level 1 -------------------------------------------------------------


def test_level_one_numbers_captions_per_chapter(tmp_path):
    out = _render(
        tmp_path,
        CHAPTERS,
        caption_chapter_level=1,
        caption_chapter_separator=".",
    )
    assert _captions(out) == [
        "Figure 1.1: Alpha",
        "Figure 1.2: Beta",
        "Table 1.1: First table",
        "Figure 2.1: Gamma",
        "Table 2.1: Second table",
    ]
    texts = _texts(out)
    assert "See Figure 1.2 and Table 1.1." in texts
    assert "Refs: Figure 1.1, Figure 2.1, Table 2.1." in texts
    _assert_refs_match_captions(_open(out))


def test_caption_field_instructions_and_order(tmp_path):
    out = _render(
        tmp_path, "# One\n\n![A {#a}](p.png)\n", caption_chapter_level=1
    )
    cap = next(p for p in _open(out).paragraphs if p.style.name == "Caption")
    pieces: list[str] = []
    for el in cap._p.iter():
        if el.tag == qn("w:bookmarkStart"):
            pieces.append("[")
        elif el.tag == qn("w:bookmarkEnd"):
            pieces.append("]")
        elif el.tag == qn("w:instrText"):
            pieces.append(f"{{{el.text.strip()}}}")
        elif el.tag == qn("w:t"):
            pieces.append(el.text)
    assert "".join(pieces) == (
        "[Figure {STYLEREF 1 \\s}1-{SEQ Figure \\* ARABIC \\s 1}1]: A"
    )


def test_references_match_captions_in_tricky_layouts(tmp_path):
    md_text = (
        "# One\n\nSee [](#t1), [](#f2) and [](#t2).\n\n"
        "> # Quoted chapter\n\n"
        "![Missing](missing.png)\n\n"
        "Text **![Bold](p.png)** more.\n\n"
        "![Target {#f2}](p.png)\n\n"
        "Table: Csv {#t1}\n\n```csv\na,b\n1,2\n```\n\n"
        "# Two\n\nTable: Md {#t2}\n\n| a |\n|---|\n| 1 |\n"
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = _render(tmp_path, md_text, caption_chapter_level=1)
    assert _captions(out) == [
        "Figure 2-1: Bold",
        "Figure 2-2: Target",
        "Table 2-1: Csv",
        "Table 3-1: Md",
    ]
    _assert_refs_match_captions(_open(out))


# --- level 2 -------------------------------------------------------------


def test_level_two_numbering_and_stale_chapter(tmp_path):
    md_text = (
        "# One\n\n## One A\n\n![A {#a}](p.png)\n\n### Deep\n\n"
        "![A2 {#a2}](p.png)\n\n## One B\n\n![B {#b}](p.png)\n\n"
        "# Two\n\n![Stale {#s}](p.png)\n\n## Two A\n\n![C {#c}](p.png)\n\n"
        "Refs: [](#a) [](#a2) [](#b) [](#s) [](#c).\n"
    )
    with pytest.warns(UserWarning, match="previous chapter"):
        out = _render(tmp_path, md_text, caption_chapter_level=2)
    assert _captions(out) == [
        "Figure 1.1-1: A",
        "Figure 1.1-2: A2",
        "Figure 1.2-1: B",
        "Figure 1.2-1: Stale",
        "Figure 2.1-1: C",
    ]
    _assert_refs_match_captions(_open(out))
    xml = _part_xml(out, "word/document.xml").decode()
    assert "STYLEREF 2 \\s" in xml and "\\s 2 " in xml


# --- before the first chapter -------------------------------------------


def test_caption_before_first_chapter_takes_next_chapter(tmp_path):
    md_text = (
        "See [](#e).\n\n![Early {#e}](p.png)\n\n# One\n\n"
        "![Later {#l}](p.png)\n\nRefs: [](#l).\n"
    )
    with pytest.warns(UserWarning, match="before the first level-1"):
        out = _render(tmp_path, md_text, caption_chapter_level=1)
    assert _captions(out) == ["Figure 1-1: Early", "Figure 1-1: Later"]
    _assert_refs_match_captions(_open(out))


def test_caption_before_first_chapter_strict_raises(tmp_path):
    with pytest.raises(RenderError):
        _render(
            tmp_path,
            "![Early](p.png)\n\n# One\n",
            caption_chapter_level=1,
            strict_mode=True,
        )


# --- numbering XML --------------------------------------------------------


def test_added_numbering_xml_is_well_ordered(tmp_path):
    # CHAPTERS has captions directly under H1s, which warn at level 2.
    with pytest.warns(UserWarning, match="level-2"):
        out = _render(tmp_path, CHAPTERS, caption_chapter_level=2)
    numbering = etree.fromstring(_part_xml(out, "word/numbering.xml"))
    kinds = [etree.QName(c).localname for c in numbering]
    last_abstract = max(i for i, k in enumerate(kinds) if k == "abstractNum")
    first_num = kinds.index("num")
    assert last_abstract < first_num
    abstract_ids = [
        a.get(qn("w:abstractNumId"))
        for a in numbering.findall(qn("w:abstractNum"))
    ]
    assert len(abstract_ids) == len(set(abstract_ids)) == 10
    template = etree.fromstring(
        _part_xml(get_default_template_path(), "word/numbering.xml")
    )
    assert len(template.findall(qn("w:abstractNum"))) == 9

    doc = _open(out)
    for n in (1, 2):
        ppr = doc.styles[f"Heading {n}"].element.pPr
        tags = [etree.QName(c).localname for c in ppr]
        assert tags.index("numPr") < tags.index("spacing")
        assert ppr.find(qn("w:numPr")).find(qn("w:ilvl")).get(
            qn("w:val")
        ) == str(n - 1)
    new_abstract = numbering.findall(qn("w:abstractNum"))[-1]
    pstyles = [el.get(qn("w:val")) for el in new_abstract.iter(qn("w:pStyle"))]
    assert pstyles == ["Heading1", "Heading2"]
    toc = doc.styles["TOC Heading"].element.pPr.find(qn("w:numPr"))
    assert toc.find(qn("w:numId")).get(qn("w:val")) == "0"


def test_template_without_numbering_part(tmp_path):
    doc, template = _template_copy(tmp_path)
    for r_id, rel in list(doc.part.rels.items()):
        if rel.reltype == RT.NUMBERING:
            del doc.part.rels[r_id]
    doc.save(str(template))
    with zipfile.ZipFile(template) as z:
        assert "word/numbering.xml" not in z.namelist()

    with pytest.warns(UserWarning, match="no heading numbering"):
        out = _render(
            tmp_path, CHAPTERS, template=template, caption_chapter_level=1
        )
    with zipfile.ZipFile(out) as z:
        assert "word/numbering.xml" in z.namelist()
        types = z.read("[Content_Types].xml").decode()
    assert "numbering+xml" in types
    assert _captions(out)[0] == "Figure 1-1: Alpha"
    assert _open(out).part.part_related_by(RT.NUMBERING) is not None


# --- custom templates ---------------------------------------------------


def test_already_numbered_template_is_left_alone(tmp_path):
    doc, template = _template_copy(tmp_path)
    add_heading_numbering(doc, 1)
    doc.save(str(template))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = _render(
            tmp_path, CHAPTERS, template=template, caption_chapter_level=1
        )
    assert _canonical(_part_xml(out, "word/numbering.xml")) == _canonical(
        _part_xml(template, "word/numbering.xml")
    )
    assert _captions(out)[0] == "Figure 1-1: Alpha"


def test_partially_numbered_template_falls_back(tmp_path):
    doc, template = _template_copy(tmp_path)
    add_heading_numbering(doc, 1)
    doc.save(str(template))
    with pytest.warns(UserWarning, match="only some"):
        out = _render(
            tmp_path, CHAPTERS, template=template, caption_chapter_level=2
        )
    assert _captions(out)[0] == "Figure 1: Alpha"
    with pytest.raises(RenderError):
        _render(
            tmp_path,
            CHAPTERS,
            template=template,
            caption_chapter_level=2,
            strict_mode=True,
        )


def test_non_decimal_template_numbering_warns(tmp_path):
    doc, template = _template_copy(tmp_path)
    add_heading_numbering(doc, 1)
    for fmt in doc.part.part_related_by(RT.NUMBERING).element.iter(
        qn("w:numFmt")
    ):
        if fmt.get(qn("w:val")) == "decimal":
            fmt.set(qn("w:val"), "upperRoman")
    doc.save(str(template))
    with pytest.warns(UserWarning, match="not plain decimal"):
        _render(tmp_path, CHAPTERS, template=template, caption_chapter_level=1)


def test_template_body_headings_count_as_chapters(tmp_path):
    doc, template = _template_copy(tmp_path)
    doc.add_paragraph("Front matter", style="Heading 1")
    doc.save(str(template))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = _render(
            tmp_path, CHAPTERS, template=template, caption_chapter_level=1
        )
    messages = " | ".join(str(w.message) for w in caught)
    assert "template body has 1" in messages
    assert "no heading numbering" in messages
    assert _captions(out)[0] == "Figure 2-1: Alpha"


def test_missing_heading_style_raises(tmp_path):
    doc, template = _template_copy(tmp_path)
    el = doc.styles["Heading 2"].element
    el.getparent().remove(el)
    doc.save(str(template))
    with pytest.raises(TemplateError, match="Heading 2"):
        _render(tmp_path, CHAPTERS, template=template, caption_chapter_level=2)


def test_typed_heading_number_warns(tmp_path):
    with pytest.warns(UserWarning, match="starts with a number"):
        _render(tmp_path, "# 1 Introduction\n", caption_chapter_level=1)


# --- numberer and options -------------------------------------------------


def test_numberer_document_wide_when_off():
    n = CaptionNumberer(None)
    n.on_heading(1)
    assert [n.next("figure").display for _ in range(2)] == ["1", "2"]
    assert n.next("table").display == "1"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"caption_chapter_level": 0},
        {"caption_chapter_level": 7},
        {"caption_chapter_level": True},
        {"caption_chapter_level": "1"},
        {"caption_chapter_separator": ""},
        {"caption_chapter_separator": "a\nb"},
    ],
)
def test_invalid_chapter_options_raise(kwargs):
    with pytest.raises(ValidationError):
        ConversionOptions(**kwargs)


def test_separator_in_cross_reference_auto_fill(tmp_path):
    out = _render(
        tmp_path,
        "# One\n\nSee [](#a).\n\n![A {#a}](p.png)\n",
        caption_chapter_level=1,
        caption_chapter_separator="–",
    )
    assert any(re.fullmatch(r"See Figure 1–1\.", t) for t in _texts(out))
