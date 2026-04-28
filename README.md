# md-reports

Convert Markdown to DOCX using a configurable Word template. Designed for
embedding in Python scripts (no CLI). Extensible to other output formats.

## Install

```bash
uv add md-reports
```

## Quick start

```python
from md_reports import convert_markdown_text, convert_markdown_file

# from a string
convert_markdown_text(
    "# Title\n\nHello **world**.",
    "out.docx",
)

# from a file (relative image paths resolve against the markdown file)
convert_markdown_file("doc.md", "doc.docx")

# inject script values via Jinja2 substitution
convert_markdown_text(
    "# Q{{ q }} report\n\nRevenue grew by **{{ pct }}%**.",
    "report.docx",
    context={"q": 2, "pct": 14.5},
)
```

Reusable converter (avoids reloading the template each call; supports
a `default_context` shared across all conversions):

```python
from md_reports import (
    ConversionOptions, DocxRenderer, MarkdownConverter,
)

conv = MarkdownConverter(
    renderer=DocxRenderer(
        template_path="house_style.docx",
        options=ConversionOptions(strict_mode=True),
    ),
    default_context={"site": "Acme"},
)
conv.convert_file("a.md", "a.docx", context={"doc": "Q1"})
conv.convert_file("b.md", "b.docx", context={"doc": "Q2"})
```

The `renderer` argument selects the output format. `DocxRenderer` is
the only built-in renderer today; the abstraction is in place for
additional renderers (e.g. HTML) to be added without changes to
`parse`, the model, options, or `MarkdownConverter`.

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

Markdown has no native table caption syntax. `md-reports` consumes the
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

### Cross-references

Attach a label to a figure or table by appending `{#label}` to its alt
text or caption, then refer to it from anywhere in the document with a
markdown link whose target is `#label`:

```markdown
![Quarterly revenue {#fig-revenue}](charts/revenue.png)

Table: Sales by region {#tab-sales}

| Region | Total |
|--------|------:|
| EMEA   | 100   |

See [Figure 1](#fig-revenue) and [](#tab-sales) for details.
```

Each labelled caption is wrapped in a Word bookmark; each `#label` link
becomes a Word `REF` field pointing at that bookmark. The link text
becomes the cached display value; an empty link text auto-fills as
`"<Prefix> <Number>"` (e.g. `Table 1`). Forward references work — the
parser resolves all labels before rendering. After F9 (or print), Word
recomputes both the SEQ counters and the REF fields so reordering or
inserting figures keeps numbering and cross-references in sync.

Unknown `#label` targets degrade to plain text with a warning (or raise
in `strict_mode`).

#### Preview-friendly label form

The bare `{#label}` marker shows up as literal text when the markdown
is viewed in a plain markdown previewer (GitHub, VS Code, etc.). For
table and CSV captions you can wrap the marker in an HTML comment so
the marker is invisible in previews while still being picked up by
md-reports:

```markdown
Table: Sales by region <!-- {#tab-sales} -->

| Region | Total |
|--------|------:|
| EMEA   | 100   |
```

Both forms are supported and behave identically; pick whichever you
prefer. The comment must come at the end of the caption. Image alt
text is already invisible in previews, so the bare form is fine there
and no comment variant is needed.

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

#### Embedding a pandas DataFrame

Pass a DataFrame in the context and pipe it through the built-in
`to_csv` Jinja2 filter inside a `csv` fence:

````markdown
Table: Quarterly figures.

```csv
{{ df | to_csv }}
```
````

```python
import pandas as pd

df = pd.DataFrame(
    {"region": ["EMEA", "APAC"], "q1": [1, 3], "q2": [2, 4]}
)
convert_markdown_text(markdown_text, "out.docx", context={"df": df})
```

The filter calls `value.to_csv(index=False)` and strips the trailing
newline. Captions, the shared `Table N` counter, and the `no-header`
flag all work the same as for any `csv` fence.

The filter is duck-typed on `.to_csv()` — pandas is **not** a
dependency of `md-reports`. Any object with a compatible `.to_csv()`
method works (your script provides it). Pass any kwargs supported by
the underlying method, e.g.:

````markdown
```csv
{{ df | to_csv(sep=';', na_rep='—', index=True) }}
```
````

## Jinja2 context

Pass a `context` dict to inject script-side values into the markdown
before parsing. Substitution runs once on the raw markdown text, so
values flow into every textual position — body, headings, table cells,
image paths, CSV file paths, inline CSV data, captions:

```python
convert_markdown_text(
    "# {{ title | upper }}\n\nGrowth: **{{ pct }}%**",
    "out.docx",
    context={"title": "q1 results", "pct": 14.5},
)
```

The full Jinja2 syntax is available — variables, filters, conditionals,
loops:

```markdown
# {{ report_title }}

{% for finding in findings %}
- {{ finding }}
{% endfor %}

{% if show_appendix %}
## Appendix

See [details]({{ appendix_url }}).
{% endif %}
```

Supported value types include `str`, `int`, `float`, `bool`, `None`,
`list`/`tuple` of those, and `dict` (for attribute access via
`{{ user.name }}`).

**Missing-variable behavior**:

- Default mode: a simple `{{ name }}` whose key is missing renders as
  the literal `{{ name }}` and emits a warning — visible breadcrumb,
  no silent data loss. More complex Jinja2 errors (syntax errors,
  iteration over an undefined sequence, etc.) cause the markdown to
  be left unchanged with a warning.
- `strict_mode=True`: any undefined variable or template error raises
  `ValidationError`.

`MarkdownConverter` accepts a `default_context` at construction
time and per-call `context=` overrides that merge over it (call-site
keys win).

## Options

```python
from md_reports import ConversionOptions

ConversionOptions(
    strict_mode=False,          # raise instead of warn on issues
    figure_caption_prefix="Figure",
    table_caption_prefix="Table",
    project_root=None,          # root for resolving relative paths
                                # to images and CSV files
)
```

## Templates

If `template_path` is omitted on `DocxRenderer` (or you don't pass a
renderer at all), a packaged default DOCX template is used. To
inspect or copy the default:

```python
from md_reports import get_default_template_path

print(get_default_template_path())
```

The template should provide these styles (fallbacks apply when
missing):

- `Normal`, `Heading 1` … `Heading 6`
- `List Bullet`, `List Number` (and their `2`/`3` variants for nesting)
- `Quote`, `Caption`
- `Table Grid`
- `Code` (optional; falls back to monospace runs in `Normal`)

### Front matter

Whatever already lives in the template (cover page, headers/footers,
title block, table of contents) is preserved — markdown content is
appended after the existing body.

## Document properties

Set DOCX core properties (the fields shown under *File > Info* in
Word) via `properties=`:

```python
convert_markdown_text(
    md,
    "report.docx",
    properties={
        "title": "Q4 Report",
        "author": "Jane Doe",
        "subject": "Quarterly review",
        "tags": "revenue, headcount",
        "comments": "Reference: REP-2026-Q4",
        "category": "Finance",
    },
)
```

To display these in the rendered document, edit the template and
insert the matching field via `Insert > Quick Parts > Field…` →
`Title` / `Author` / `Subject` / `Keywords` / `Comments` / `Category`.
You can place these in the body, header, or footer. Word recomputes
fields on F9 / print, same as `SEQ` and `REF`.

`MarkdownConverter` also accepts `default_properties=`, merged with
per-call `properties=` (call-site keys win).

Accepted keys (case-insensitive) and the core property they target:

| Key (and aliases) | Core property |
|---|---|
| `title` | `title` |
| `author`, `creator` | `author` |
| `subject` | `subject` |
| `keywords`, `tags` | `keywords` |
| `comments`, `description` | `comments` |
| `category`, `categories` | `category` |
| `content_status` | `content_status` |
| `identifier` | `identifier` |
| `language` | `language` |
| `version` | `version` |
| `last_modified_by` | `last_modified_by` |

Unknown keys warn (or raise under `strict_mode`). Datetime properties
(`created`, `modified`, `last_printed`, `revision`) are deliberately
not exposed.

`Company` lives in DOCX extended properties (`docProps/app.xml`),
not core properties, and is not currently writable via this API.
Arbitrary user-defined properties (`docProps/custom.xml`) are likewise
not yet supported — use `subject`/`keywords`/`comments` as a host for
reference strings or project codes.

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

## Security model

By default, `md-reports` treats the markdown source as **code-equivalent**
— same trust as the script that calls the library. Two consequences
follow that you should know about:

1. **Jinja2 substitution runs in a non-sandboxed environment.** Any
   `{{ ... }}` expression in the markdown can reach into context
   values' attributes (e.g. `{{ obj.__class__... }}`). Useful for
   things like `{{ df | to_csv }}`, dangerous if the markdown is
   untrusted.
2. **Asset paths are not confined.** Image and CSV references
   (`![](path)`, `csv-file` blocks) accept absolute paths and `..`
   traversals. The library will read whatever the process can read
   and embed it into the output.

This is fine for the typical use case (developer-authored markdown,
script-supplied context). If you ever pass user-controlled markdown
into the library — e.g. a CMS, a comment field, or a user-uploaded
file — turn on the two hardening flags:

```python
from md_reports import ConversionOptions, convert_markdown_text

convert_markdown_text(
    untrusted_markdown,
    "out.docx",
    context={"title": "Report"},
    options=ConversionOptions(
        sandboxed_context=True,   # use Jinja2's SandboxedEnvironment
        confine_assets=True,      # reject paths outside project_root
        project_root="/srv/uploads/work_dir",
    ),
)
```

`sandboxed_context=True` swaps the Jinja2 environment for
`jinja2.sandbox.SandboxedEnvironment`, blocking attribute and
built-in access in template expressions. Note this can break filters
that rely on duck-typed attribute access (the built-in `to_csv`
filter still works because it uses `hasattr`/`getattr`, not
expression-level attribute access). Verify your templates against the
sandboxed environment before rolling it out.

`confine_assets=True` enforces that every resolved image and CSV path
lies under the asset base — `project_root` if set, otherwise the
markdown file's directory. Absolute paths and `..` traversals that
escape the base are rejected (warned, or raised under `strict_mode`).

Also note:

- **Templates** (`template_path=`) are loaded by `python-docx` /
  `lxml` and are otherwise opaque to md-reports. Treat templates as
  trusted: don't load templates from untrusted sources without
  reviewing them first.
- **Hyperlink schemes** are limited to `http://`, `https://`, and
  `mailto:`; other schemes (including `javascript:`, `file:`,
  `data:`) fall back to plain text.
- **Remote image fetching** is not supported; `http(s)://` image
  paths are explicitly rejected.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```
