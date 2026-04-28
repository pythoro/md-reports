"""Render the internal model to a python-docx document."""

from __future__ import annotations

import re
import warnings
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx.document import Document as DocxDoc
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph as DocxParagraph

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
    Text,
)
from md_reports.options import ConversionOptions
from md_reports.renderers.base import BaseRenderer, RenderContext
from md_reports.renderers.docx.template import (
    load_docx_template,
    style_exists,
)

_HYPERLINK_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/"
    "relationships/hyperlink"
)
_VALID_LINK_SCHEMES = ("http://", "https://", "mailto:")

_BOOKMARK_SAFE = re.compile(r"[^A-Za-z0-9_]")

# Map user-facing keys to the python-docx ``CoreProperties`` attribute
# they target. Includes the OOXML-canonical names plus a few aliases
# matching Word's UI labels (Tags = keywords, Categories = category)
# and Dublin Core synonyms (creator = author, description = comments).
_PROPERTY_ALIASES: dict[str, str] = {
    "title": "title",
    "author": "author",
    "creator": "author",
    "subject": "subject",
    "keywords": "keywords",
    "tags": "keywords",
    "comments": "comments",
    "description": "comments",
    "category": "category",
    "categories": "category",
    "content_status": "content_status",
    "identifier": "identifier",
    "language": "language",
    "version": "version",
    "last_modified_by": "last_modified_by",
}


def _bookmark_name(label: str) -> str:
    """Build a Word-safe bookmark name from a user label.

    Word bookmark names must start with a letter or underscore and may
    contain only letters, digits, and underscores. Prefix with ``_Ref``
    (Word's own convention) and sanitise other characters.
    """
    safe = _BOOKMARK_SAFE.sub("_", label)
    return f"_Ref_{safe}"


@dataclass
class _RunFormat:
    bold: bool = False
    italic: bool = False
    code: bool = False


@dataclass
class _RunSegment:
    text: str
    fmt: _RunFormat = field(default_factory=_RunFormat)
    line_break_after: bool = False


@dataclass(kw_only=True)
class _DocxContext(RenderContext):
    """RenderContext extended with the DOCX document handle."""

    doc: DocxDoc
    bookmark_id_counter: int = 0


class DocxRenderer(BaseRenderer):
    """Render a parsed :class:`Document` into a DOCX file.

    A template DOCX is loaded fresh on each ``render()`` call, so a
    single ``DocxRenderer`` instance can be reused for multiple
    conversions.
    """

    def __init__(
        self,
        template_path: str | Path | None = None,
        options: ConversionOptions | None = None,
    ) -> None:
        super().__init__(options)
        self.template_path = template_path

    def render(
        self,
        document: Document,
        output_path: Path,
        *,
        markdown_dir: Path | None = None,
        properties: dict[str, str] | None = None,
    ) -> Path:
        docx_doc = load_docx_template(self.template_path)
        ctx = _DocxContext(markdown_dir=markdown_dir, doc=docx_doc)
        if properties:
            self._apply_properties(ctx, properties)
        self._collect_labels(ctx, document.blocks)
        for block in document.blocks:
            self._render_block(ctx, block)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        docx_doc.save(str(output_path))
        return output_path

    # --- block dispatch -----------------------------------------------

    def _render_block(self, ctx: _DocxContext, block: Block) -> None:
        if isinstance(block, Heading):
            self._render_heading(ctx, block)
        elif isinstance(block, Paragraph):
            self._render_paragraph(ctx, block)
        elif isinstance(block, CodeBlock):
            self._render_code_block(ctx, block)
        elif isinstance(block, BlockQuote):
            self._render_blockquote(ctx, block)
        elif isinstance(block, BulletList):
            self._render_list(ctx, block, ordered=False, level=1)
        elif isinstance(block, OrderedList):
            self._render_list(ctx, block, ordered=True, level=1)
        elif isinstance(block, Table):
            self._render_table(ctx, block)
        elif isinstance(block, ImageBlock):
            self._render_image_block(ctx, block)
        elif isinstance(block, CsvFileEmbed):
            self._render_csv_file(ctx, block)
        elif isinstance(block, CsvInlineEmbed):
            self._render_csv_inline(ctx, block)
        else:
            self._warn_or_raise(
                f"Unsupported block type: {type(block).__name__}"
            )

    # --- headings -----------------------------------------------------

    def _render_heading(self, ctx: _DocxContext, h: Heading) -> None:
        style = self._heading_style(ctx, h.level)
        para = ctx.doc.add_paragraph(style=style)
        self._render_inlines(ctx, para, h.children)

    def _heading_style(self, ctx: _DocxContext, level: int) -> str:
        for lvl in range(level, 0, -1):
            name = f"Heading {lvl}"
            if style_exists(ctx.doc, name):
                return name
        if level > 1:
            warnings.warn(
                f"No Heading style available for level {level}; "
                f"falling back to Normal",
                stacklevel=3,
            )
        return "Normal"

    # --- paragraph ----------------------------------------------------

    def _render_paragraph(self, ctx: _DocxContext, p: Paragraph) -> None:
        para = ctx.doc.add_paragraph()
        deferred: list[InlineImage] = []
        self._render_inlines(ctx, para, p.children, deferred_images=deferred)
        for img in deferred:
            self._emit_figure(
                ctx,
                img.src,
                img.alt,
                after_paragraph=True,
                label=img.label,
            )

    # --- code block ---------------------------------------------------

    def _render_code_block(self, ctx: _DocxContext, cb: CodeBlock) -> None:
        if style_exists(ctx.doc, "Code"):
            para = ctx.doc.add_paragraph(style="Code")
            para.add_run(cb.text.rstrip("\n"))
        else:
            para = ctx.doc.add_paragraph()
            run = para.add_run(cb.text.rstrip("\n"))
            run.font.name = "Consolas"
            run.font.size = Pt(10)

    # --- blockquote ---------------------------------------------------

    def _render_blockquote(self, ctx: _DocxContext, bq: BlockQuote) -> None:
        quote_style = "Quote" if style_exists(ctx.doc, "Quote") else "Normal"
        for inner in bq.blocks:
            if isinstance(inner, Paragraph):
                para = ctx.doc.add_paragraph(style=quote_style)
                self._render_inlines(ctx, para, inner.children)
            else:
                self._render_block(ctx, inner)

    # --- lists --------------------------------------------------------

    def _render_list(
        self,
        ctx: _DocxContext,
        lst: BulletList | OrderedList,
        ordered: bool,
        level: int,
    ) -> None:
        if ordered and isinstance(lst, OrderedList) and lst.start != 1:
            warnings.warn(
                "Ordered list start value is not honored in v1 "
                "(Word numbering uses template defaults)",
                stacklevel=3,
            )
        for item in lst.items:
            self._render_list_item(ctx, item, ordered, level)

    def _render_list_item(
        self,
        ctx: _DocxContext,
        item: ListItem,
        ordered: bool,
        level: int,
    ) -> None:
        style = self._list_style(ctx, ordered, level)
        first_para_emitted = False
        for blk in item.blocks:
            if isinstance(blk, Paragraph) and not first_para_emitted:
                para = ctx.doc.add_paragraph(style=style)
                self._render_inlines(ctx, para, blk.children)
                first_para_emitted = True
            elif isinstance(blk, (BulletList, OrderedList)):
                self._render_list(
                    ctx,
                    blk,
                    ordered=isinstance(blk, OrderedList),
                    level=level + 1,
                )
            else:
                self._render_block(ctx, blk)

    def _list_style(self, ctx: _DocxContext, ordered: bool, level: int) -> str:
        base = "List Number" if ordered else "List Bullet"
        candidates = []
        if level > 1:
            candidates.append(f"{base} {level}")
        candidates.append(base)
        candidates.append("List Paragraph")
        candidates.append("Normal")
        for name in candidates:
            if style_exists(ctx.doc, name):
                return name
        return "Normal"

    # --- tables -------------------------------------------------------

    def _render_table(self, ctx: _DocxContext, t: Table) -> None:
        n_cols = max(
            len(t.header.cells),
            *(len(r.cells) for r in t.body),
            1,
        )
        if t.caption is not None:
            ctx.table_counter += 1
            self._emit_caption(
                ctx,
                self.options.table_caption_prefix,
                ctx.table_counter,
                t.caption,
                label=t.label,
            )
        table_style = (
            "Table Grid" if style_exists(ctx.doc, "Table Grid") else None
        )
        n_rows = 1 + len(t.body)
        table = ctx.doc.add_table(rows=n_rows, cols=n_cols)
        if table_style:
            table.style = table_style
        self._fill_row(
            ctx,
            table.rows[0].cells,
            t.header.cells,
            t.alignments,
            bold=True,
        )
        for i, row in enumerate(t.body, start=1):
            self._fill_row(
                ctx,
                table.rows[i].cells,
                row.cells,
                t.alignments,
                bold=False,
            )

    def _fill_row(
        self,
        ctx: _DocxContext,
        docx_cells,
        model_cells: list[TableCell],
        alignments: list[str | None],
        bold: bool,
    ) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        align_map = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
        }
        for i, dcell in enumerate(docx_cells):
            mcell = model_cells[i] if i < len(model_cells) else TableCell()
            para = dcell.paragraphs[0]
            self._render_inlines(ctx, para, mcell.children)
            if bold:
                for run in para.runs:
                    run.bold = True
            align = alignments[i] if i < len(alignments) else None
            if align in align_map:
                para.alignment = align_map[align]

    # --- images / figure captions -------------------------------------

    def _render_image_block(self, ctx: _DocxContext, ib: ImageBlock) -> None:
        self._emit_figure(
            ctx,
            ib.src,
            ib.alt,
            after_paragraph=False,
            label=ib.label,
        )

    def _emit_figure(
        self,
        ctx: _DocxContext,
        src: str,
        alt: str,
        after_paragraph: bool,
        label: str | None = None,
    ) -> None:
        path = self._resolve_asset_path(ctx, src, kind="image")
        if path is None:
            return
        if not after_paragraph:
            para = ctx.doc.add_paragraph()
            run = para.add_run()
            try:
                run.add_picture(str(path))
            except Exception as exc:  # noqa: BLE001
                self._warn_or_raise(f"Failed to embed image {path}: {exc}")
                return
        # else: image was rendered inline already
        ctx.figure_counter += 1
        cap_inlines: list[Inline] = []
        if alt:
            cap_inlines.append(Text(alt))
        self._emit_caption(
            ctx,
            self.options.figure_caption_prefix,
            ctx.figure_counter,
            cap_inlines,
            label=label,
        )

    # --- CSV embedding -----------------------------------------------

    def _render_csv_file(self, ctx: _DocxContext, c: CsvFileEmbed) -> None:
        path = self._resolve_asset_path(ctx, c.path, kind="CSV file")
        if path is None:
            return
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            self._warn_or_raise(f"Failed to read CSV {path}: {exc}")
            return
        rows = self._parse_csv_text(text)
        if not rows:
            self._warn_or_raise(f"CSV is empty: {path}")
            return
        self._emit_csv_table(ctx, rows, c.has_header, c.caption, c.label)

    def _render_csv_inline(self, ctx: _DocxContext, c: CsvInlineEmbed) -> None:
        rows = self._parse_csv_text(c.data)
        if not rows:
            self._warn_or_raise("Inline CSV block is empty")
            return
        self._emit_csv_table(ctx, rows, c.has_header, c.caption, c.label)

    def _emit_csv_table(
        self,
        ctx: _DocxContext,
        rows: list[list[str]],
        has_header: bool,
        caption: list[Inline] | None,
        label: str | None = None,
    ) -> None:
        header = rows[0] if has_header else None
        body = rows[1:] if has_header else rows
        n_cols = max(
            len(header or []),
            *(len(r) for r in body),
            1,
        )
        if caption is not None:
            ctx.table_counter += 1
            self._emit_caption(
                ctx,
                self.options.table_caption_prefix,
                ctx.table_counter,
                caption,
                label=label,
            )
        n_rows = (1 if header is not None else 0) + len(body)
        if n_rows == 0:
            return
        table = ctx.doc.add_table(rows=n_rows, cols=n_cols)
        if style_exists(ctx.doc, "Table Grid"):
            table.style = "Table Grid"
        row_idx = 0
        if header is not None:
            for i, dcell in enumerate(table.rows[0].cells):
                cell_text = header[i] if i < len(header) else ""
                run = dcell.paragraphs[0].add_run(cell_text)
                run.bold = True
            row_idx = 1
        for body_row in body:
            for i, dcell in enumerate(table.rows[row_idx].cells):
                cell_text = body_row[i] if i < len(body_row) else ""
                dcell.paragraphs[0].add_run(cell_text)
            row_idx += 1

    # --- captions -----------------------------------------------------

    def _emit_caption(
        self,
        ctx: _DocxContext,
        prefix: str,
        number: int,
        text_inlines: list[Inline],
        label: str | None = None,
    ) -> None:
        has_caption_style = style_exists(ctx.doc, "Caption")
        style = "Caption" if has_caption_style else "Normal"
        para = ctx.doc.add_paragraph(style=style)
        bookmark_id: int | None = None
        if label:
            bookmark_id = self._open_bookmark(ctx, para, _bookmark_name(label))
        prefix_run = para.add_run(f"{prefix} ")
        if not has_caption_style:
            prefix_run.italic = True
        self._append_seq_field(para, prefix, str(number))
        if bookmark_id is not None:
            self._close_bookmark(para, bookmark_id)
        if text_inlines:
            sep_run = para.add_run(": ")
            if not has_caption_style:
                sep_run.italic = True
            self._render_inlines(
                ctx,
                para,
                text_inlines,
                force_italic=not has_caption_style,
            )

    # --- document properties ------------------------------------------

    def _apply_properties(
        self, ctx: _DocxContext, properties: dict[str, str]
    ) -> None:
        """Apply user-supplied metadata to ``doc.core_properties``.

        Keys are matched case-insensitively against
        :data:`_PROPERTY_ALIASES`. Unknown keys warn (or raise in
        ``strict_mode``). Empty-string values clear the corresponding
        property.
        """
        cp = ctx.doc.core_properties
        for raw_key, value in properties.items():
            key = raw_key.strip().lower()
            attr = _PROPERTY_ALIASES.get(key)
            if attr is None:
                self._warn_or_raise(
                    f"Unknown document property {raw_key!r}; "
                    f"expected one of: {sorted(_PROPERTY_ALIASES)}"
                )
                continue
            if value is None:
                continue
            setattr(cp, attr, str(value))

    # --- cross-references ---------------------------------------------

    def _collect_labels(
        self, ctx: _DocxContext, blocks: list[Block]
    ) -> None:
        """Pre-walk blocks to register ``{#label}`` -> (prefix, number).

        Mirrors the figure/table counter logic so cross-references can
        resolve to the same number the caption will eventually display,
        including forward references.
        """
        fig_n = 0
        tab_n = 0

        def walk(items: list[Block]) -> None:
            nonlocal fig_n, tab_n
            for blk in items:
                if isinstance(blk, ImageBlock):
                    fig_n += 1
                    if blk.label:
                        self._register_label(
                            ctx,
                            blk.label,
                            self.options.figure_caption_prefix,
                            fig_n,
                        )
                elif isinstance(blk, Paragraph):
                    for child in blk.children:
                        if isinstance(child, InlineImage):
                            fig_n += 1
                            if child.label:
                                self._register_label(
                                    ctx,
                                    child.label,
                                    self.options.figure_caption_prefix,
                                    fig_n,
                                )
                elif isinstance(blk, Table):
                    if blk.caption is not None:
                        tab_n += 1
                        if blk.label:
                            self._register_label(
                                ctx,
                                blk.label,
                                self.options.table_caption_prefix,
                                tab_n,
                            )
                elif isinstance(blk, (CsvFileEmbed, CsvInlineEmbed)):
                    if blk.caption is not None:
                        tab_n += 1
                        if blk.label:
                            self._register_label(
                                ctx,
                                blk.label,
                                self.options.table_caption_prefix,
                                tab_n,
                            )
                elif isinstance(blk, BlockQuote):
                    walk(blk.blocks)
                elif isinstance(blk, (BulletList, OrderedList)):
                    for item in blk.items:
                        walk(item.blocks)

        walk(blocks)

    def _register_label(
        self,
        ctx: _DocxContext,
        label: str,
        prefix: str,
        number: int,
    ) -> None:
        if label in ctx.label_registry:
            self._warn_or_raise(
                f"Duplicate cross-reference label {label!r}; "
                "keeping the first occurrence"
            )
            return
        ctx.label_registry[label] = (prefix, number)

    def _open_bookmark(
        self, ctx: _DocxContext, para: DocxParagraph, name: str
    ) -> int:
        bid = ctx.bookmark_id_counter
        ctx.bookmark_id_counter += 1
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), str(bid))
        start.set(qn("w:name"), name)
        para._p.append(start)
        return bid

    def _close_bookmark(self, para: DocxParagraph, bid: int) -> None:
        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(bid))
        para._p.append(end)

    def _append_ref_field(
        self,
        para: DocxParagraph,
        bookmark_name: str,
        displayed: str,
        fmt: _RunFormat,
    ) -> None:
        """Append a Word REF field referencing ``bookmark_name``.

        Emitted as a complex field with a cached display run so the
        document looks right before fields are first updated.
        """
        instr = f" REF {bookmark_name} \\h "
        p = para._p

        begin_run = OxmlElement("w:r")
        begin = OxmlElement("w:fldChar")
        begin.set(qn("w:fldCharType"), "begin")
        begin_run.append(begin)
        p.append(begin_run)

        instr_run = OxmlElement("w:r")
        instr_el = OxmlElement("w:instrText")
        instr_el.set(qn("xml:space"), "preserve")
        instr_el.text = instr
        instr_run.append(instr_el)
        p.append(instr_run)

        sep_run = OxmlElement("w:r")
        sep = OxmlElement("w:fldChar")
        sep.set(qn("w:fldCharType"), "separate")
        sep_run.append(sep)
        p.append(sep_run)

        disp_run = self._build_run(displayed, fmt)
        p.append(disp_run)

        end_run = OxmlElement("w:r")
        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")
        end_run.append(end)
        p.append(end_run)

    def _build_run(self, text: str, fmt: _RunFormat) -> Any:
        """Build a standalone ``w:r`` element honouring ``fmt``."""
        run = OxmlElement("w:r")
        if fmt.bold or fmt.italic or fmt.code:
            rpr = OxmlElement("w:rPr")
            if fmt.bold:
                rpr.append(OxmlElement("w:b"))
            if fmt.italic:
                rpr.append(OxmlElement("w:i"))
            if fmt.code:
                rfonts = OxmlElement("w:rFonts")
                rfonts.set(qn("w:ascii"), "Consolas")
                rfonts.set(qn("w:hAnsi"), "Consolas")
                rpr.append(rfonts)
            run.append(rpr)
        t = OxmlElement("w:t")
        t.set(qn("xml:space"), "preserve")
        t.text = text
        run.append(t)
        return run

    def _append_seq_field(
        self, para: DocxParagraph, name: str, displayed: str
    ) -> None:
        """Append a Word SEQ field producing an arabic counter.

        Emitted as a complex field (``w:fldChar`` begin / ``w:instrText``
        / ``w:fldChar`` separate / cached display run / ``w:fldChar``
        end). Word recomputes the number on field update; the cached
        value keeps first-open rendering correct in viewers that do
        not auto-update fields.
        """
        instr = f" SEQ {name} \\* ARABIC "
        p = para._p

        begin_run = OxmlElement("w:r")
        begin = OxmlElement("w:fldChar")
        begin.set(qn("w:fldCharType"), "begin")
        begin_run.append(begin)
        p.append(begin_run)

        instr_run = OxmlElement("w:r")
        instr_el = OxmlElement("w:instrText")
        instr_el.set(qn("xml:space"), "preserve")
        instr_el.text = instr
        instr_run.append(instr_el)
        p.append(instr_run)

        sep_run = OxmlElement("w:r")
        sep = OxmlElement("w:fldChar")
        sep.set(qn("w:fldCharType"), "separate")
        sep_run.append(sep)
        p.append(sep_run)

        disp_run = OxmlElement("w:r")
        disp_t = OxmlElement("w:t")
        disp_t.text = displayed
        disp_run.append(disp_t)
        p.append(disp_run)

        end_run = OxmlElement("w:r")
        end = OxmlElement("w:fldChar")
        end.set(qn("w:fldCharType"), "end")
        end_run.append(end)
        p.append(end_run)

    # --- inlines ------------------------------------------------------

    def _render_inlines(
        self,
        ctx: _DocxContext,
        para: DocxParagraph,
        inlines: list[Inline],
        deferred_images: list[InlineImage] | None = None,
        force_italic: bool = False,
    ) -> None:
        for inline in inlines:
            self._render_inline(
                ctx,
                para,
                inline,
                _RunFormat(italic=force_italic),
                deferred_images,
            )

    def _render_inline(
        self,
        ctx: _DocxContext,
        para: DocxParagraph,
        inline: Inline,
        fmt: _RunFormat,
        deferred_images: list[InlineImage] | None,
    ) -> None:
        if isinstance(inline, Text):
            self._add_run(para, inline.text, fmt)
        elif isinstance(inline, LineBreak):
            run = para.add_run()
            run.add_break()
        elif isinstance(inline, InlineCode):
            new_fmt = _RunFormat(bold=fmt.bold, italic=fmt.italic, code=True)
            self._add_run(para, inline.text, new_fmt)
        elif isinstance(inline, Strong):
            new_fmt = _RunFormat(bold=True, italic=fmt.italic, code=fmt.code)
            for child in inline.children:
                self._render_inline(ctx, para, child, new_fmt, deferred_images)
        elif isinstance(inline, Emphasis):
            new_fmt = _RunFormat(bold=fmt.bold, italic=True, code=fmt.code)
            for child in inline.children:
                self._render_inline(ctx, para, child, new_fmt, deferred_images)
        elif isinstance(inline, Link):
            self._render_link(ctx, para, inline, fmt)
        elif isinstance(inline, InlineImage):
            self._render_inline_image(ctx, para, inline, deferred_images)
        else:
            self._warn_or_raise(f"Unsupported inline: {type(inline).__name__}")

    def _add_run(
        self, para: DocxParagraph, text: str, fmt: _RunFormat
    ) -> None:
        if not text:
            return
        run = para.add_run(text)
        if fmt.bold:
            run.bold = True
        if fmt.italic:
            run.italic = True
        if fmt.code:
            run.font.name = "Consolas"

    def _render_inline_image(
        self,
        ctx: _DocxContext,
        para: DocxParagraph,
        img: InlineImage,
        deferred_images: list[InlineImage] | None,
    ) -> None:
        path = self._resolve_asset_path(ctx, img.src, kind="image")
        if path is None:
            return
        try:
            para.add_run().add_picture(str(path))
        except Exception as exc:  # noqa: BLE001
            self._warn_or_raise(f"Failed to embed image {path}: {exc}")
            return
        if deferred_images is not None:
            deferred_images.append(img)

    # --- hyperlinks ---------------------------------------------------

    def _render_link(
        self,
        ctx: _DocxContext,
        para: DocxParagraph,
        link: Link,
        fmt: _RunFormat,
    ) -> None:
        href = link.href.strip()
        if href.startswith("#"):
            self._render_cross_reference(ctx, para, link, fmt, href[1:])
            return
        if not href.lower().startswith(_VALID_LINK_SCHEMES):
            # render as plain text
            warnings.warn(
                f"Skipping hyperlink with unsupported scheme: {href}",
                stacklevel=3,
            )
            for child in link.children:
                self._render_inline(ctx, para, child, fmt, None)
            return
        try:
            r_id = para.part.relate_to(href, _HYPERLINK_REL, is_external=True)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Hyperlink relationship failed for {href}: {exc}",
                stacklevel=3,
            )
            for child in link.children:
                self._render_inline(ctx, para, child, fmt, None)
            return
        hyperlink = OxmlElement("w:hyperlink")
        hyperlink.set(qn("r:id"), r_id)
        segments = self._collect_link_segments(link.children, fmt)
        for seg in segments:
            hyperlink.append(self._build_hyperlink_run(seg))
        para._p.append(hyperlink)

    def _render_cross_reference(
        self,
        ctx: _DocxContext,
        para: DocxParagraph,
        link: Link,
        fmt: _RunFormat,
        label: str,
    ) -> None:
        """Render ``[text](#label)`` as a Word REF cross-reference.

        Falls back to plain text (with a warning) when ``label`` is not
        registered. Empty link text is auto-filled with ``"<prefix>
        <number>"`` from the registry.
        """
        target = ctx.label_registry.get(label)
        if target is None:
            self._warn_or_raise(
                f"Unknown cross-reference label {label!r}; "
                "rendering link text as plain text"
            )
            for child in link.children:
                self._render_inline(ctx, para, child, fmt, None)
            return
        prefix, number = target
        segments = self._collect_link_segments(link.children, fmt)
        if not segments:
            displayed = f"{prefix} {number}"
        else:
            displayed = "".join(seg.text for seg in segments)
        self._append_ref_field(para, _bookmark_name(label), displayed, fmt)

    def _collect_link_segments(
        self, inlines: list[Inline], base: _RunFormat
    ) -> list[_RunSegment]:
        segments: list[_RunSegment] = []
        self._walk_link_inlines(inlines, base, segments)
        return segments

    def _walk_link_inlines(
        self,
        inlines: list[Inline],
        fmt: _RunFormat,
        out: list[_RunSegment],
    ) -> None:
        for node in inlines:
            if isinstance(node, Text):
                if node.text:
                    out.append(_RunSegment(text=node.text, fmt=deepcopy(fmt)))
            elif isinstance(node, InlineCode):
                out.append(
                    _RunSegment(
                        text=node.text,
                        fmt=_RunFormat(
                            bold=fmt.bold,
                            italic=fmt.italic,
                            code=True,
                        ),
                    )
                )
            elif isinstance(node, Strong):
                self._walk_link_inlines(
                    node.children,
                    _RunFormat(
                        bold=True,
                        italic=fmt.italic,
                        code=fmt.code,
                    ),
                    out,
                )
            elif isinstance(node, Emphasis):
                self._walk_link_inlines(
                    node.children,
                    _RunFormat(
                        bold=fmt.bold,
                        italic=True,
                        code=fmt.code,
                    ),
                    out,
                )
            elif isinstance(node, LineBreak):
                if out:
                    out[-1].line_break_after = True

    def _build_hyperlink_run(self, seg: _RunSegment):
        run = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        rStyle = OxmlElement("w:rStyle")
        rStyle.set(qn("w:val"), "Hyperlink")
        rPr.append(rStyle)
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "0563C1")
        rPr.append(color)
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single")
        rPr.append(u)
        if seg.fmt.bold:
            rPr.append(OxmlElement("w:b"))
        if seg.fmt.italic:
            rPr.append(OxmlElement("w:i"))
        if seg.fmt.code:
            rFonts = OxmlElement("w:rFonts")
            rFonts.set(qn("w:ascii"), "Consolas")
            rFonts.set(qn("w:hAnsi"), "Consolas")
            rPr.append(rFonts)
        run.append(rPr)
        t = OxmlElement("w:t")
        t.text = seg.text
        t.set(qn("xml:space"), "preserve")
        run.append(t)
        if seg.line_break_after:
            run.append(OxmlElement("w:br"))
        return run
