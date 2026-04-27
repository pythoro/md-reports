"""Parse Markdown into the internal document model.

Uses markdown-it-py with the GFM table extension enabled. Tokens are
walked recursively and assembled into the model defined in
:mod:`md_reports.model`.
"""

from __future__ import annotations

import re
import warnings
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from md_reports.context import apply_context
from md_reports.errors import ParseError
from md_reports.model import (
    Block,
    BlockQuote,
    BulletList,
    CodeBlock,
    CsvFileEmbed,
    CsvInlineEmbed,
    Document,
    Emphasis,
    Heading,
    ImageBlock,
    Inline,
    InlineCode,
    InlineImage,
    LineBreak,
    Link,
    ListItem,
    OrderedList,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from md_reports.options import ConversionOptions

_HTML_LINK_OPEN = re.compile(
    r'<a\s+[^>]*href\s*=\s*"([^"]*)"[^>]*>',
    re.IGNORECASE,
)
_HTML_LINK_CLOSE = re.compile(r"</a\s*>", re.IGNORECASE)


def parse(
    text: str,
    options: ConversionOptions | None = None,
    context: dict[str, Any] | None = None,
) -> Document:
    """Parse markdown text into a :class:`Document`.

    If ``context`` is provided, the markdown is first rendered as a
    Jinja2 template against it. See :mod:`md_reports.context` for
    behavior on undefined variables and template errors.
    """
    opts = options or ConversionOptions()
    if context:
        text = apply_context(text, context, opts.strict_mode)
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(text)
    blocks, _ = _parse_blocks(tokens, 0, len(tokens), opts)
    blocks = _apply_table_captions(blocks, opts)
    return Document(blocks=blocks)


def _parse_blocks(
    tokens: list[Token],
    start: int,
    end: int,
    opts: ConversionOptions,
) -> tuple[list[Block], int]:
    blocks: list[Block] = []
    i = start
    while i < end:
        tok = tokens[i]
        t = tok.type
        if t == "heading_open":
            level = int(tok.tag[1])
            children = _parse_inlines((tokens[i + 1].children or []), opts)
            blocks.append(Heading(level=level, children=children))
            i += 3
        elif t == "paragraph_open":
            children = _parse_inlines((tokens[i + 1].children or []), opts)
            blk = _maybe_block_image(children) or Paragraph(children=children)
            blocks.append(blk)
            i += 3
        elif t == "fence":
            blocks.append(_make_fence_block(tok))
            i += 1
        elif t == "code_block":
            blocks.append(CodeBlock(text=tok.content, language=None))
            i += 1
        elif t == "blockquote_open":
            close = _find_matching(tokens, i, "blockquote_close")
            inner, _ = _parse_blocks(tokens, i + 1, close, opts)
            blocks.append(BlockQuote(blocks=inner))
            i = close + 1
        elif t == "bullet_list_open":
            close = _find_matching(tokens, i, "bullet_list_close")
            items = _parse_list_items(tokens, i + 1, close, opts)
            blocks.append(BulletList(items=items))
            i = close + 1
        elif t == "ordered_list_open":
            close = _find_matching(tokens, i, "ordered_list_close")
            items = _parse_list_items(tokens, i + 1, close, opts)
            start_attr = tok.attrGet("start")
            try:
                start_n = int(start_attr) if start_attr else 1
            except (TypeError, ValueError):
                start_n = 1
            blocks.append(OrderedList(items=items, start=start_n))
            i = close + 1
        elif t == "table_open":
            close = _find_matching(tokens, i, "table_close")
            blocks.append(_parse_table(tokens, i, close, opts))
            i = close + 1
        elif t == "hr":
            i += 1
        elif t == "html_block":
            _warn_or_raise(
                f"Inline HTML block is not supported: {tok.content[:60]!r}",
                opts,
            )
            i += 1
        else:
            i += 1
    return blocks, i


def _make_fence_block(tok: Token) -> Block:
    """Map a markdown-it ``fence`` token to a model block.

    Recognised info-string kinds:
      * ``csv-file``  — body is a single path; emits ``CsvFileEmbed``
      * ``csv``       — body is literal CSV; emits ``CsvInlineEmbed``
      * anything else — emits ``CodeBlock``

    Both CSV kinds accept a ``no-header`` flag elsewhere in the info
    string.
    """
    info = (tok.info or "").strip()
    if not info:
        return CodeBlock(text=tok.content, language=None)
    parts = info.split()
    kind = parts[0]
    flags = set(parts[1:])
    if kind == "csv-file":
        return CsvFileEmbed(
            path=tok.content.strip(),
            has_header="no-header" not in flags,
        )
    if kind == "csv":
        return CsvInlineEmbed(
            data=tok.content,
            has_header="no-header" not in flags,
        )
    return CodeBlock(text=tok.content, language=info or None)


def _find_matching(tokens: list[Token], start: int, close_type: str) -> int:
    open_type = tokens[start].type
    depth = 0
    for j in range(start, len(tokens)):
        if tokens[j].type == open_type:
            depth += 1
        elif tokens[j].type == close_type:
            depth -= 1
            if depth == 0:
                return j
    raise ParseError(f"Unterminated block at token {start}: {open_type}")


def _parse_list_items(
    tokens: list[Token],
    start: int,
    end: int,
    opts: ConversionOptions,
) -> list[ListItem]:
    items: list[ListItem] = []
    i = start
    while i < end:
        if tokens[i].type != "list_item_open":
            i += 1
            continue
        close = _find_matching(tokens, i, "list_item_close")
        inner, _ = _parse_blocks(tokens, i + 1, close, opts)
        items.append(ListItem(blocks=inner))
        i = close + 1
    return items


def _parse_table(
    tokens: list[Token],
    start: int,
    end: int,
    opts: ConversionOptions,
) -> Table:
    header = TableRow()
    body: list[TableRow] = []
    alignments: list[str | None] = []
    in_thead = False
    current_row: TableRow | None = None
    is_header_row = False
    for i in range(start, end + 1):
        tok = tokens[i]
        if tok.type == "thead_open":
            in_thead = True
        elif tok.type == "thead_close":
            in_thead = False
        elif tok.type == "tr_open":
            current_row = TableRow()
            is_header_row = in_thead
        elif tok.type == "tr_close":
            if current_row is not None:
                if is_header_row:
                    header = current_row
                else:
                    body.append(current_row)
                current_row = None
        elif tok.type in ("th_open", "td_open"):
            style = tok.attrGet("style") or ""
            align: str | None = None
            if "text-align:left" in style:
                align = "left"
            elif "text-align:right" in style:
                align = "right"
            elif "text-align:center" in style:
                align = "center"
            cell_children = _parse_inlines(
                (tokens[i + 1].children or []), opts
            )
            if current_row is not None:
                current_row.cells.append(TableCell(children=cell_children))
            if is_header_row:
                alignments.append(align)
    return Table(header=header, body=body, alignments=alignments)


def _parse_inlines(
    children: list[Token],
    opts: ConversionOptions,
) -> list[Inline]:
    out: list[Inline] = []
    stack: list[list[Inline]] = [out]
    in_html_link = False
    for tok in children:
        t = tok.type
        if t == "text":
            if tok.content:
                stack[-1].append(Text(tok.content))
        elif t == "softbreak":
            stack[-1].append(Text(" "))
        elif t == "hardbreak":
            stack[-1].append(LineBreak())
        elif t == "code_inline":
            stack[-1].append(InlineCode(tok.content))
        elif t == "strong_open":
            node = Strong()
            stack[-1].append(node)
            stack.append(node.children)
        elif t == "strong_close":
            stack.pop()
        elif t == "em_open":
            node = Emphasis()
            stack[-1].append(node)
            stack.append(node.children)
        elif t == "em_close":
            stack.pop()
        elif t == "link_open":
            node = Link(
                href=tok.attrGet("href") or "",
                title=tok.attrGet("title"),
            )
            stack[-1].append(node)
            stack.append(node.children)
        elif t == "link_close":
            stack.pop()
        elif t == "image":
            alt = "".join(
                c.content for c in (tok.children or []) if c.type == "text"
            )
            stack[-1].append(
                InlineImage(
                    src=tok.attrGet("src") or "",
                    alt=alt,
                    title=tok.attrGet("title"),
                )
            )
        elif t == "html_inline":
            in_html_link = _handle_html_inline(
                tok.content, stack, opts, in_html_link
            )
        else:
            stack[-1].append(Text(getattr(tok, "content", "")))
    return out


def _handle_html_inline(
    raw: str,
    stack: list[list[Inline]],
    opts: ConversionOptions,
    in_html_link: bool,
) -> bool:
    open_m = _HTML_LINK_OPEN.match(raw)
    if open_m:
        node = Link(href=open_m.group(1))
        stack[-1].append(node)
        stack.append(node.children)
        return True
    if _HTML_LINK_CLOSE.match(raw):
        if in_html_link:
            stack.pop()
            return False
        return in_html_link
    _warn_or_raise(f"Inline HTML is not supported: {raw!r}", opts)
    stack[-1].append(Text(raw))
    return in_html_link


def _maybe_block_image(
    children: list[Inline],
) -> ImageBlock | None:
    image: InlineImage | None = None
    for c in children:
        if isinstance(c, InlineImage):
            if image is not None:
                return None
            image = c
        elif isinstance(c, Text):
            if c.text.strip():
                return None
        else:
            return None
    if image is None:
        return None
    return ImageBlock(src=image.src, alt=image.alt, title=image.title)


def _apply_table_captions(
    blocks: list[Block], opts: ConversionOptions
) -> list[Block]:
    prefix = opts.table_caption_prefix
    out: list[Block] = []
    for blk in blocks:
        if isinstance(blk, (Table, CsvFileEmbed, CsvInlineEmbed)) and out:
            cap = _extract_table_caption(out[-1], prefix)
            if cap is not None:
                out.pop()
                blk.caption = cap
        if isinstance(blk, BlockQuote):
            blk.blocks = _apply_table_captions(blk.blocks, opts)
        elif isinstance(blk, (BulletList, OrderedList)):
            for item in blk.items:
                item.blocks = _apply_table_captions(item.blocks, opts)
        out.append(blk)
    return out


def _extract_table_caption(block: Block, prefix: str) -> list[Inline] | None:
    if not isinstance(block, Paragraph) or not block.children:
        return None
    first = block.children[0]
    if not isinstance(first, Text):
        return None
    head = first.text.lstrip()
    expected = f"{prefix}:"
    if not head.startswith(expected):
        return None
    remainder = head[len(expected) :].lstrip()
    new_children: list[Inline] = list(block.children[1:])
    if remainder:
        new_children.insert(0, Text(remainder))
    return new_children


def _warn_or_raise(msg: str, opts: ConversionOptions) -> None:
    if opts.strict_mode:
        raise ParseError(msg)
    warnings.warn(msg, stacklevel=2)
