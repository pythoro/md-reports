"""Normalized document model produced by the parser.

The model is intentionally small and rendering-agnostic. The parser
produces it from markdown-it tokens; the renderer consumes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --- Inline nodes -----------------------------------------------------


@dataclass
class Text:
    text: str


@dataclass
class Strong:
    children: list[Inline] = field(default_factory=list)


@dataclass
class Emphasis:
    children: list[Inline] = field(default_factory=list)


@dataclass
class InlineCode:
    text: str


@dataclass
class Link:
    href: str
    title: str | None = None
    children: list[Inline] = field(default_factory=list)


@dataclass
class InlineImage:
    """An image appearing inside an inline run.

    Block-level images (sole content of a paragraph) are lifted to
    :class:`ImageBlock` during parsing.
    """

    src: str
    alt: str = ""
    title: str | None = None


@dataclass
class LineBreak:
    """Hard line break."""


Inline = Text | Strong | Emphasis | InlineCode | Link | InlineImage | LineBreak


# --- Block nodes ------------------------------------------------------


@dataclass
class Heading:
    level: int
    children: list[Inline] = field(default_factory=list)


@dataclass
class Paragraph:
    children: list[Inline] = field(default_factory=list)


@dataclass
class CodeBlock:
    text: str
    language: str | None = None


@dataclass
class BlockQuote:
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ListItem:
    blocks: list[Block] = field(default_factory=list)


@dataclass
class BulletList:
    items: list[ListItem] = field(default_factory=list)


@dataclass
class OrderedList:
    items: list[ListItem] = field(default_factory=list)
    start: int = 1


@dataclass
class TableCell:
    children: list[Inline] = field(default_factory=list)


@dataclass
class TableRow:
    cells: list[TableCell] = field(default_factory=list)


@dataclass
class Table:
    header: TableRow
    body: list[TableRow] = field(default_factory=list)
    alignments: list[str | None] = field(default_factory=list)
    caption: list[Inline] | None = None


@dataclass
class ImageBlock:
    """Block-level figure: image followed by an auto-numbered caption.

    ``alt`` becomes the caption text. Empty alt suppresses the trailing
    colon in the rendered caption.
    """

    src: str
    alt: str = ""
    title: str | None = None


Block = (
    Heading
    | Paragraph
    | CodeBlock
    | BlockQuote
    | BulletList
    | OrderedList
    | Table
    | ImageBlock
)


@dataclass
class Document:
    blocks: list[Block] = field(default_factory=list)
