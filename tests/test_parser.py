"""Parser unit tests."""

from __future__ import annotations

import pytest

from md_reports.errors import ParseError
from md_reports.model import (
    BlockQuote,
    BulletList,
    CodeBlock,
    Emphasis,
    Heading,
    ImageBlock,
    InlineCode,
    InlineImage,
    Link,
    OrderedList,
    Paragraph,
    Strong,
    Table,
    Text,
)
from md_reports.options import ConversionOptions
from md_reports.parser import parse


def test_headings_levels_1_to_6():
    src = "\n".join(f"{'#' * lvl} h{lvl}" for lvl in range(1, 7))
    doc = parse(src)
    assert [b.level for b in doc.blocks] == [1, 2, 3, 4, 5, 6]
    assert all(isinstance(b, Heading) for b in doc.blocks)
    assert doc.blocks[0].children[0].text == "h1"


def test_paragraph_with_inlines():
    doc = parse("plain **bold** *italic* `code` end")
    para = doc.blocks[0]
    assert isinstance(para, Paragraph)
    kinds = [type(c).__name__ for c in para.children]
    assert "Strong" in kinds
    assert "Emphasis" in kinds
    assert "InlineCode" in kinds


def test_markdown_link():
    doc = parse("see [docs](https://example.com)")
    para = doc.blocks[0]
    link = next(c for c in para.children if isinstance(c, Link))
    assert link.href == "https://example.com"
    assert isinstance(link.children[0], Text)
    assert link.children[0].text == "docs"


def test_html_anchor_link_minimal():
    doc = parse('see <a href="https://x">x</a> here')
    para = doc.blocks[0]
    link = next(c for c in para.children if isinstance(c, Link))
    assert link.href == "https://x"
    assert any(isinstance(c, Text) and c.text == "x" for c in link.children)


def test_other_inline_html_warns():
    with pytest.warns(UserWarning):
        parse("a <span>b</span> c")


def test_other_inline_html_strict_raises():
    with pytest.raises(ParseError):
        parse(
            "a <span>b</span> c",
            ConversionOptions(strict_mode=True),
        )


def test_bullet_list_with_nested():
    src = "- one\n- two\n  - nested\n- three\n"
    doc = parse(src)
    lst = doc.blocks[0]
    assert isinstance(lst, BulletList)
    assert len(lst.items) == 3
    second_item_blocks = lst.items[1].blocks
    assert any(isinstance(b, BulletList) for b in second_item_blocks)


def test_ordered_list():
    doc = parse("1. a\n2. b\n3. c\n")
    lst = doc.blocks[0]
    assert isinstance(lst, OrderedList)
    assert len(lst.items) == 3


def test_blockquote():
    doc = parse("> quoted text\n> more\n")
    bq = doc.blocks[0]
    assert isinstance(bq, BlockQuote)
    assert isinstance(bq.blocks[0], Paragraph)


def test_fenced_code_block():
    doc = parse("```python\nprint(1)\n```\n")
    cb = doc.blocks[0]
    assert isinstance(cb, CodeBlock)
    assert cb.language == "python"
    assert "print(1)" in cb.text


def test_table_basic():
    src = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
    doc = parse(src)
    t = doc.blocks[0]
    assert isinstance(t, Table)
    assert len(t.header.cells) == 2
    assert len(t.body) == 2
    assert t.body[1].cells[1].children[0].text == "4"


def test_table_alignments():
    src = "| L | C | R |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n"
    doc = parse(src)
    t = doc.blocks[0]
    assert t.alignments == ["left", "center", "right"]


def test_table_caption_consumed_from_preceding_paragraph():
    src = "Table: Quarterly numbers.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    doc = parse(src)
    assert len(doc.blocks) == 1
    t = doc.blocks[0]
    assert isinstance(t, Table)
    assert t.caption is not None
    cap_text = "".join(c.text for c in t.caption if isinstance(c, Text))
    assert "Quarterly numbers" in cap_text


def test_table_without_caption_is_unmodified():
    src = "| a |\n|---|\n| 1 |\n"
    doc = parse(src)
    assert isinstance(doc.blocks[0], Table)
    assert doc.blocks[0].caption is None


def test_table_caption_custom_prefix():
    opts = ConversionOptions(table_caption_prefix="Tableau")
    src = "Tableau: French caption.\n\n| a |\n|---|\n| 1 |\n"
    doc = parse(src, opts)
    assert doc.blocks[0].caption is not None


def test_block_image_lifted():
    doc = parse("![alt text](pic.png)")
    blk = doc.blocks[0]
    assert isinstance(blk, ImageBlock)
    assert blk.src == "pic.png"
    assert blk.alt == "alt text"


def test_inline_image_in_mixed_paragraph_not_lifted():
    doc = parse("hello ![pic](x.png) world")
    blk = doc.blocks[0]
    assert isinstance(blk, Paragraph)
    assert any(isinstance(c, InlineImage) for c in blk.children)


def test_strong_with_inline_code():
    doc = parse("**bold `code` here**")
    para = doc.blocks[0]
    strong = para.children[0]
    assert isinstance(strong, Strong)
    assert any(isinstance(c, InlineCode) for c in strong.children)


def test_emphasis_nested():
    doc = parse("*just italic*")
    para = doc.blocks[0]
    assert isinstance(para.children[0], Emphasis)


def test_block_image_label_extracted_from_alt():
    doc = parse("![Quarterly revenue {#fig-revenue}](chart.png)")
    blk = doc.blocks[0]
    assert isinstance(blk, ImageBlock)
    assert blk.label == "fig-revenue"
    assert blk.alt == "Quarterly revenue"


def test_inline_image_label_extracted_from_alt():
    doc = parse("see ![inline {#fig-inline}](x.png) here")
    para = doc.blocks[0]
    assert isinstance(para, Paragraph)
    img = next(c for c in para.children if isinstance(c, InlineImage))
    assert img.label == "fig-inline"
    assert img.alt == "inline"


def test_image_without_label_unchanged():
    doc = parse("![just alt](pic.png)")
    blk = doc.blocks[0]
    assert isinstance(blk, ImageBlock)
    assert blk.label is None
    assert blk.alt == "just alt"


def test_table_caption_label_extracted():
    src = "Table: Sales data {#tab-sales}\n\n| a |\n|---|\n| 1 |\n"
    doc = parse(src)
    t = doc.blocks[0]
    assert isinstance(t, Table)
    assert t.label == "tab-sales"
    cap_text = "".join(
        c.text for c in (t.caption or []) if isinstance(c, Text)
    )
    assert "Sales data" in cap_text
    assert "{#tab-sales}" not in cap_text


def test_table_caption_label_with_inline_formatting():
    src = "Table: *Quarterly* sales {#tab-q}\n\n| a |\n|---|\n| 1 |\n"
    doc = parse(src)
    t = doc.blocks[0]
    assert t.label == "tab-q"
    # caption still has formatted inline runs
    assert any(isinstance(c, Emphasis) for c in (t.caption or []))


def test_table_caption_hidden_html_comment_label_extracted():
    src = (
        "Table: Sales data <!-- {#tab-sales} -->\n\n"
        "| a |\n|---|\n| 1 |\n"
    )
    doc = parse(src)
    t = doc.blocks[0]
    assert isinstance(t, Table)
    assert t.label == "tab-sales"
    cap_text = "".join(
        c.text for c in (t.caption or []) if isinstance(c, Text)
    )
    assert "Sales data" in cap_text
    assert "<!--" not in cap_text
    assert "{#" not in cap_text


def test_hidden_html_comment_label_does_not_warn(recwarn):
    src = (
        "Table: Sales data <!-- {#tab-sales} -->\n\n"
        "| a |\n|---|\n| 1 |\n"
    )
    parse(src)
    html_warns = [
        w for w in recwarn.list if "Inline HTML" in str(w.message)
    ]
    assert not html_warns


def test_table_caption_hidden_label_with_extra_whitespace():
    src = (
        "Table: Sales data    <!--   {#tab-sales}   -->\n\n"
        "| a |\n|---|\n| 1 |\n"
    )
    doc = parse(src)
    t = doc.blocks[0]
    assert t.label == "tab-sales"
