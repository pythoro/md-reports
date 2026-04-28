# md-reports Implementation Plan (API-first)

Date: 2026-04-27

## Confirmed Scope Decisions

1. No CLI. This package is embedded in Python scripts.
2. Include basic table support in v1.
3. Markdown links rendered as clickable DOCX hyperlinks. Inline HTML
   `<a href="...">text</a>` supported minimally; other inline HTML passes
   through as visible text with a warning.
4. Include a default DOCX template in the package.
5. Target Python `>= 3.10`.
6. Embed images as figures with auto-numbered captions (`Figure N: ...`).
   Image source must be a local path relative to the markdown file or an
   absolute path. Remote (http/https) images warn or fail based on
   `strict_mode`.
7. Tables support auto-numbered captions (`Table N: ...`) placed above
   the table, sourced from a preceding paragraph beginning with
   `Table:`.
8. Embed CSV data as DOCX tables via two fenced-block variants:
   ` ```csv-file ` (body is a path) and ` ```csv ` (body is literal CSV
   data). CSV-derived tables share the same `Table N` counter as
   markdown tables and accept the same preceding-`Table:` caption.
9. Markdown text is rendered as a Jinja2 template against a per-call
   ``context`` dict before parsing. Full Jinja2 (variables, filters,
   conditionals, loops) is supported. Missing variables warn and emit
   a literal ``{{ name }}`` breadcrumb in non-strict mode; strict mode
   raises ``ValidationError``.

## Low-Level XML Areas

Three v1 features require dropping below `python-docx`'s high-level API
and writing OOXML directly. They are isolated to renderer helpers.

### Hyperlinks

1. Relationship entries in the DOCX package (`rId` targets for external
   URLs).
2. `w:hyperlink` XML elements with nested runs.
3. Correct handling of mixed formatting inside links (bold/italic/code
   spans).
4. URL sanitation/validation and safe fallback behavior for invalid
   links.

v1: implement a focused hyperlink helper supporting external
HTTP/HTTPS/mailto links; degrade to plain text on failure.

### Auto-numbered captions (Figure N / Table N)

DOCX produces auto-incrementing numbers via Word `SEQ` fields, e.g.
`{ SEQ Figure \* ARABIC }` and `{ SEQ Table \* ARABIC }`. `python-docx`
does not expose these directly, so the renderer emits a complex field
(`w:fldChar` begin / `w:instrText` / `w:fldChar` separate / cached
display / `w:fldChar` end) inside a Caption-styled paragraph. Numbering
restarts per document and is independent for figures vs tables.

### Cross-references

Users attach a label by appending `{#label}` to an image alt text or a
`Table:` caption. The parser strips the marker and stores it on the
model node (`ImageBlock.label`, `Table.label`,
`CsvFileEmbed.label`, `CsvInlineEmbed.label`,
`InlineImage.label`). References are written as ordinary markdown links
with `#label` hrefs.

Table and CSV captions also accept a preview-invisible HTML-comment
form, e.g. `Table: caption <!-- {#label} -->`. The parser's inline-HTML
hook recognises `<!--\s*\{#label\}\s*-->` tokens and re-emits them as
the bare `{#label}` form, so the rest of the extraction pipeline is
unchanged. Image alt text is already invisible in previews so the
HTML-comment variant is unnecessary there.

The renderer does a pre-walk over the document to build a label
registry mapping `label -> (prefix, number)` so forward references
resolve. Each labelled caption gets a `w:bookmarkStart` /
`w:bookmarkEnd` pair around the SEQ field run, named `_Ref_<label>`
(non-alphanumeric characters in the user label are sanitised to
underscores). Each `[text](#label)` becomes a Word `REF` complex field
referencing the bookmark; empty link text auto-fills with
`"<Prefix> <Number>"` from the registry. Unknown labels degrade to
plain text with a warning (or raise under `strict_mode`).

### Image embedding

Use `python-docx`'s `add_picture` for the image part/relationship, then
emit the caption paragraph adjacent to the image. Resolve image paths
relative to the markdown file (when known) or to the current working
directory; warn or fail on missing/unreadable images per
`strict_mode`.

## Target API (No CLI)

Primary API functions:

1. `convert_markdown_text(markdown_text: str, output_path: str | Path, *, template_path: str | Path | None = None, options: ConversionOptions | None = None) -> Path`
2. `convert_markdown_file(markdown_path: str | Path, output_path: str | Path, *, template_path: str | Path | None = None, options: ConversionOptions | None = None) -> Path`

Optional reusable object:

1. `MarkdownDocxConverter(template_path: str | Path | None = None, options: ConversionOptions | None = None)`
2. `.convert_text(...)`
3. `.convert_file(...)`

Public helper:

1. `get_default_template_path() -> Path`

## ConversionOptions (v1 fields)

A frozen dataclass exposing only the knobs we need for v1. Add fields
later as concrete needs appear; do not pre-populate.

1. `strict_mode: bool = False` — when `True`, raise on unsupported
   constructs, missing images, and link/caption failures instead of
   warning.
2. `figure_caption_prefix: str = "Figure"` — label used in the SEQ
   caption paragraph.
3. `table_caption_prefix: str = "Table"` — label used in the SEQ
   caption paragraph.
4. `project_root: str | Path | None = None` — root for resolving
   relative paths to external assets (images and CSV files). When
   `None`, resolve relative to the markdown file's directory (for
   `convert_markdown_file`) or the current working directory (for
   `convert_markdown_text`).

## Project Structure

- `src/md_reports/api.py` (public conversion entry points)
- `src/md_reports/options.py` (typed config/dataclass)
- `src/md_reports/model.py` (normalized document model)
- `src/md_reports/parser.py` (markdown-it-py parsing and normalization)
- `src/md_reports/renderer.py` (model to python-docx rendering)
- `src/md_reports/template.py` (template loading, default template resolution)
- `src/md_reports/errors.py` (custom exception types)
- `src/md_reports/resources/default_template.docx` (packaged default template)
- `tests/` (unit + integration tests)

## Dependencies

Runtime:

1. `markdown-it-py`
2. `mdit-py-plugins` (enable GitHub-style tables)
3. `python-docx`

Development:

1. `pytest`
2. `ruff`

Python: `requires-python = ">=3.10"`.

Environment management: `uv`.

## Rendering Rules for v1

### Blocks

1. Headings: `#` -> Heading 1 through `######` -> Heading 6. If the
   template lacks a level, fall back to the next-lower available
   heading style, then Normal. Fallbacks log a warning unless
   `strict_mode`.
2. Paragraphs -> Normal style.
3. Bullet and numbered lists (basic nesting).
4. Block quotes -> Quote style (or configurable fallback).
5. Fenced code blocks -> Code style fallback strategy.
6. Tables -> basic markdown tables only, optional preceding
   `Table:`-prefixed paragraph consumed as caption.
7. Images (`![alt](path)`) -> embedded picture followed by a
   `Figure N: alt` caption paragraph (Caption style). Empty alt
   produces `Figure N` only.

### Inlines

1. Strong/bold.
2. Emphasis/italic.
3. Inline code.
4. Markdown links -> clickable DOCX hyperlinks.
5. Inline HTML `<a href="...">text</a>` -> clickable hyperlink. Other
   inline HTML emits visible text and warns; on `strict_mode` it
   raises.

## Table Support (Basic v1)

Supported:

1. Standard markdown tables with header row and body rows.
2. Left/default alignment initially.
3. Simple cell content as plain text with basic inline formatting where practical.
4. Optional caption sourced from the paragraph immediately preceding
   the table when it begins with the configured `table_caption_prefix`
   followed by `:` (default `Table:`). The caption paragraph is removed
   from the body flow and re-emitted above the table as
   `Table N: <caption text>` styled with Caption.

Deferred:

1. Cell merge (`rowspan`/`colspan`), nested tables.
2. Advanced width control/autofit tuning.
3. Rich content inside cells beyond core inline elements.

## Images and Figures (Basic v1)

Supported:

1. Markdown image syntax `![alt](path "optional title")`.
2. Local relative paths (resolved per `project_root` rules) and
   absolute paths.
3. Embedded picture followed immediately by a Caption-styled paragraph
   `Figure N: <alt>` using a `SEQ Figure` field.
4. Block-level images become a paragraph of their own; inline images
   inside a paragraph render in place but still emit a caption
   paragraph below the containing paragraph.

Deferred / non-goals for v1:

1. Remote (`http(s)://`) image fetching — warn or raise per
   `strict_mode`.
2. Sizing controls beyond the image's intrinsic DPI/size.
3. Floating/anchored images and text wrapping.
4. SVG and other formats unsupported by `python-docx.add_picture`.

## CSV Embedding

Two fenced-block variants drop CSV data into the document as a DOCX
table.

### Syntax

File-backed embed:

````markdown
```csv-file
data/quarterly.csv
```
````

Inline CSV literal:

````markdown
```csv
region,q1,q2
EMEA,1,2
APAC,3,4
```
````

Either form accepts a `no-header` flag on the info string to suppress
header-row treatment:

````markdown
```csv-file no-header
data/raw.csv
```
````

### Behavior

1. Parser intercepts `fence` tokens whose info string starts with
   `csv-file` or `csv` and emits `CsvFileEmbed` / `CsvInlineEmbed`
   model nodes (in place of `CodeBlock`).
2. CSV-derived tables share the same `Table N` counter as native
   markdown tables.
3. A preceding paragraph beginning with `Table:` attaches as a caption
   to the next CSV embed, identical to native tables.
4. CSV cells render as plain text; no markdown is parsed inside them.
5. Default delimiter detection uses `csv.Sniffer`; encoding is UTF-8.
   Per-fence overrides are deferred.
6. File path is resolved per `project_root` rules. Missing files warn
   in normal mode, raise `RenderError` in `strict_mode`. Decode
   failures behave the same.
7. With `no-header`, the table has no header row (no bolded first
   row); all rows go to the body.
8. Empty CSVs produce no output (warn).

### Deferred

1. Per-fence `delimiter=` / `encoding=` overrides.
2. Numeric formatting / locale-aware number rendering.
3. Cell-level styling sourced from CSV (e.g., colored cells).
4. Streaming/very-large CSVs — v1 reads the whole file.

## Jinja2 Context Substitution

A per-call ``context: dict`` is rendered against the raw markdown text
*before* tokenization, so values flow into every textual position
(body, headings, table cells, image paths, CSV paths, inline CSV
data, captions, link URLs).

### API

* ``convert_markdown_text(... , context=None)``
* ``convert_markdown_file(... , context=None)``
* ``MarkdownDocxConverter(template_path, options, default_context=None)``
  with per-call ``context=`` that merges over the default.
* ``parse(text, options, context=None)`` for direct users.

### Behavior

1. Full Jinja2 syntax: variables, filters, conditionals, loops, etc.
2. Accepted value types: ``str``, ``int``, ``float``, ``bool``,
   ``None``, ``list``/``tuple`` of those, and ``dict`` (for
   ``{{ user.name }}`` attribute access).
3. Substitution runs once, before markdown-it tokenization.
4. Undefined variable, non-strict: ``{{ name }}`` is preserved as a
   literal breadcrumb in the output and a warning is emitted via the
   custom ``_KeepUndefined`` class.
5. Undefined variable, strict: raises ``ValidationError``.
6. Other Jinja2 errors (template syntax, iteration over undefined,
   etc.), non-strict: the markdown is left unchanged with a warning.
7. Other Jinja2 errors, strict: raises ``ValidationError``.

### Implementation

* New module ``md_reports.context`` holding ``apply_context()`` and
  ``_KeepUndefined``.
* ``parser.parse()`` calls ``apply_context()`` when a context is
  provided.
* No new public exception classes; ``ValidationError`` is reused.

### Built-in filters

* ``to_csv``: convert a DataFrame-like object (anything with a
  ``.to_csv()`` method) to CSV text suitable for dropping into a
  ``csv`` fence. Defaults to ``index=False`` when the underlying
  method accepts that kwarg; passes through other kwargs (``sep=``,
  ``na_rep=``, etc.); strips the trailing newline. Pandas is **not**
  a dependency — duck-typing only.

  Usage:

  ````markdown
  Table: Quarterly figures.

  ```csv
  {{ df | to_csv }}
  ```
  ````

### Deferred

1. A literal-``{{`` escape — only add when a real use case appears.
2. Additional custom Jinja2 filters/globals beyond ``to_csv``.
3. Type-validation of context values beyond what Jinja2 itself
   tolerates at render time.

## Default Template Strategy

1. Ship `resources/default_template.docx` inside the package.
2. If `template_path` is omitted, use packaged default template.
3. Expose helper: `get_default_template_path()`.
4. Validate required styles at load time with clear errors/fallback policy.

Required style names (initial target):

1. Normal
2. Heading 1 .. Heading 6 (with cascading fallback to next-lower
   heading, then Normal)
3. List Paragraph (or fallback)
4. Quote (or fallback)
5. Code (or fallback to Normal + monospace run formatting)
6. Table Grid (or fallback)
7. Caption (or fallback to Normal with italic + smaller size)

## Error Handling

Custom exceptions:

1. `TemplateError`
2. `ParseError`
3. `RenderError`
4. `ValidationError`

Behavior:

1. Fail fast on unreadable template or output path issues.
2. For unsupported markdown constructs, either warn or raise based on `strict_mode`.
3. For link creation failures, log warning and emit plain link text.

## Phased Execution Plan

### Phase 1: Foundation

1. Update `pyproject.toml`: set `requires-python = ">=3.10"`, add
   runtime/dev dependencies, **remove the `[project.scripts]` entry
   and any `main` symbol** (no CLI in v1).
2. Add module skeleton files and public exports in `__init__.py`
   (`convert_markdown_text`, `convert_markdown_file`,
   `MarkdownDocxConverter`, `ConversionOptions`, exception types,
   `get_default_template_path`).
3. Add `ConversionOptions` dataclass and exception classes.
4. Configure `ruff` with line length 79.

### Phase 2: Parse + Model

1. Implement markdown parsing with markdown-it-py + table plugin.
2. Normalize parser tokens into internal block/inline model.
3. Add tests for headings, lists, code, blockquotes, and tables.

### Phase 3: Template + Renderer

1. Implement template loader and style validation (including Caption
   style).
2. Add default packaged template and resolver helper.
3. Implement renderer for block/inline model.
4. Add hyperlink helper for clickable links (markdown links + minimal
   inline `<a>`).
5. Add basic table rendering to DOCX tables, with caption consumption
   from preceding `Table:` paragraph.
6. Add image embedding helper with caption emission.
7. Add SEQ-field caption helper (`Figure`/`Table` counters).

### Phase 4: API + Quality

1. Implement `convert_markdown_text` and `convert_markdown_file`.
2. Add integration tests for end-to-end conversion.
3. Document embedding usage in README.
4. Run `ruff` and `pytest` and stabilize error messages.

## Testing Plan

Unit tests:

1. Parser token-to-model mapping.
2. Table parsing edge cases (missing separator, uneven rows).
3. Hyperlink generation behavior and fallback path.
4. Template style validation and fallback policy (including Heading
   1..6 cascade and Caption fallback).
5. Image path resolution (relative, absolute, missing, remote URL).
6. Caption SEQ field XML structure for Figure and Table.
7. Table caption consumption from preceding `Table:` paragraph.
8. Inline `<a>` HTML link recognition; other inline HTML warns or
   raises per `strict_mode`.

Integration tests:

1. Markdown fixture -> DOCX output exists and readable.
2. Verify expected paragraph/table counts and representative text.
3. Verify links are present as hyperlinks when valid.
4. Verify default template path works when no template provided.
5. Verify embedded images and `Figure N: ...` captions in order.
6. Verify `Table N: ...` captions positioned above each table and
   numbered independently from figures.

## Success Criteria

1. Embedded script API converts markdown to DOCX without CLI.
2. Basic tables render reliably for standard markdown table syntax.
3. Links are clickable in DOCX for valid external URLs (markdown and
   minimal inline `<a>`).
4. Images embed with auto-numbered figure captions; tables get
   auto-numbered captions above them; counters are independent.
5. Package works with a built-in default template when user does not
   provide one.
6. Tests pass for core parsing, rendering, template handling, and
   end-to-end flow.

## Engineering Conventions

1. `src` layout under `src/md_reports/`.
2. Strong type hints across the public API and core modules.
3. `ruff` line length 79, used for linting and formatting.
4. Keep modules small; document XML concerns isolated to renderer
   helpers.
5. Prefer pure functions for parsing and token-to-model mapping.

## Out of Scope for v1

1. CLI entry point or scripts.
2. Advanced page layout (sections, columns, headers/footers beyond
   what the template provides).
3. Merged cells, nested tables, advanced table geometry.
4. Remote image fetching, SVG, floating/anchored images.
5. Cross-reference fields beyond `SEQ Figure` / `SEQ Table` (no
   STYLEREF, no auto-generated TOC, no bibliography).
6. Math/LaTeX, footnotes, definition lists, task lists.
7. Equation rendering or OMML emission.
