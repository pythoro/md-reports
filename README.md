# md-ast-docx

Convert Markdown to DOCX using a configurable Word template. Designed
for embedding in Python scripts (no CLI).

## Install

```bash
uv add md-ast-docx
```

## Quick start

```python
from md_ast_docx import convert_markdown_text, convert_markdown_file

# from a string
convert_markdown_text(
    "# Title\n\nHello **world**.",
    "out.docx",
)

# from a file (relative image paths resolve against the markdown file)
convert_markdown_file("doc.md", "doc.docx")
```

Reusable converter (avoids reloading the template each call):

```python
from md_ast_docx import MarkdownDocxConverter, ConversionOptions

conv = MarkdownDocxConverter(
    template_path="house_style.docx",
    options=ConversionOptions(strict_mode=True),
)
conv.convert_file("a.md", "a.docx")
conv.convert_file("b.md", "b.docx")
```

## What's supported

Block elements:

- Headings `#` to `######` (mapped to `Heading 1` … `Heading 6` with
  cascading fallback)
- Paragraphs, block quotes, fenced code blocks
- Bullet and ordered lists (with nesting)
- Standard markdown tables (header + body rows, alignment markers)
- CSV embedding via fenced blocks — both file-backed and inline
  literal data
- Embedded images (`![alt](path)`) as figures with auto-numbered
  captions

Inline elements: bold, italic, inline code, markdown links, and minimal
inline `<a href="...">…</a>` HTML.

### Figures

Block-level images become a figure with an auto-numbered caption
sourced from the alt text:

```markdown
![Quarterly revenue chart](charts/revenue.png)
```

renders the image followed by a Caption-styled paragraph
`Figure 1: Quarterly revenue chart`. The number is a Word `SEQ` field,
so it stays correct after copy/paste or reordering (Word updates fields
on print or `F9`).

### Table captions

Markdown has no native table caption syntax. `md-ast-docx` consumes the
paragraph immediately preceding a table when it begins with `Table:`:

```markdown
Table: Quarterly revenue by region.

| Region | Q1 | Q2 |
|--------|----|----|
| EMEA   | 1  | 2  |
```

The caption is emitted above the table as
`Table 1: Quarterly revenue by region.` styled with Caption. Figure and
table counters are independent. The prefix is configurable via
`ConversionOptions.table_caption_prefix`.

### CSV embedding

Two fenced-block variants render CSV data as a DOCX table.

**From a file** — the body is a single path resolved against
`project_root` (or the markdown file's directory):

````markdown
Table: Quarterly revenue.

```csv-file
data/quarterly.csv
```
````

**Inline** — the body is the CSV literal itself:

````markdown
```csv
region,q1,q2
EMEA,1,2
APAC,3,4
```
````

Either form accepts a `no-header` flag on the info string to suppress
header-row treatment (no row gets bolded; all rows are body):

````markdown
```csv-file no-header
data/raw.csv
```
````

CSV-derived tables share the same `Table N` counter as native markdown
tables, accept the same preceding-`Table:` caption, and use the
`Table Grid` style. The delimiter is auto-detected via `csv.Sniffer`
(falls back to comma); encoding is UTF-8.

## Options

```python
from md_ast_docx import ConversionOptions

ConversionOptions(
    strict_mode=False,          # raise instead of warn on issues
    figure_caption_prefix="Figure",
    table_caption_prefix="Table",
    project_root=None,          # root for resolving relative paths
                                # to images and CSV files
)
```

## Templates

If `template_path` is omitted, a packaged default template is used. To
inspect or copy the default:

```python
from md_ast_docx import get_default_template_path

print(get_default_template_path())
```

The template should provide these styles (fallbacks apply when
missing):

- `Normal`, `Heading 1` … `Heading 6`
- `List Bullet`, `List Number` (and their `2`/`3` variants for nesting)
- `Quote`, `Caption`
- `Table Grid`
- `Code` (optional; falls back to monospace runs in `Normal`)

## Limitations (v1)

- No CLI.
- Remote (`http(s)://`) image fetching is not supported — use local
  files.
- Cell merges (`rowspan`/`colspan`) and nested tables are not
  supported.
- CSV embedding has no per-fence delimiter/encoding overrides yet
  (UTF-8 + `csv.Sniffer` only).
- `SEQ` field numbers display correctly in Word once fields update
  (typically on print or pressing `F9`); the file is written with a
  pre-computed display value so first-open looks right too.
- No footnotes, math, definition lists, or task lists.

## Errors

All exceptions inherit from `MdAstDocxError`. Specific types:

- `TemplateError` — template missing/unreadable
- `ParseError` — markdown could not be parsed
- `RenderError` — DOCX rendering failed
- `ValidationError` — bad input arguments

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```
