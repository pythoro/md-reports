---
name: md-reports
description: Generate Word (.docx) reports from Markdown in Python using the md-reports library. Use when writing or editing code that calls md_reports (convert_markdown_text, convert_markdown_file, MarkdownConverter, DocxRenderer, ConversionOptions), when producing a DOCX report from a Python script, when creating or updating a report under a project's reports/ folder, or when authoring Markdown meant to be rendered by md-reports (figures, table captions, cross-references, CSV/DataFrame tables, LaTeX math, Jinja2 placeholders, document properties, custom templates).
---

# Using md-reports

md-reports turns Markdown into a styled `.docx` through a Python API.
It has no CLI. Styling comes from a DOCX template: the packaged
default, or one you supply. The pipeline is:

```
markdown text -> Jinja2 substitution (only if context given)
             -> markdown-it parse -> internal model -> DocxRenderer
```

Install: `uv add md-reports` (import name `md_reports`, Python >= 3.10).

## Pick the right entry point

| Situation | Use |
|---|---|
| Markdown built in Python | `convert_markdown_text(md, out_path, ...)` |
| Markdown lives in a `.md` file | `convert_markdown_file(md_path, out_path, ...)` |
| Many reports, same template/defaults | `MarkdownConverter(...)` then `.convert_text` / `.convert_file` |
| Custom house style | `DocxRenderer(template_path="style.docx", options=...)` |
| Save the Jinja2-rendered markdown | `render_markdown_template(md, context, options=...)` returns `str` |

All of them return the output `Path`. Keyword-only arguments shared by
both functions:

- `context: dict` renders the markdown as a Jinja2 template first.
- `properties: dict[str, str]` sets DOCX core properties (title,
  author, and so on).
- `base_dir` sets the directory that relative image and CSV paths
  resolve against.
- `options: ConversionOptions` is used when you don't pass a renderer.
- `renderer: BaseRenderer` defaults to `DocxRenderer()`.

**Do not pass both `renderer=` and `options=`.** That raises
`ValidationError`. When you need a custom template, put the options on
the renderer:

```python
from md_reports import (
    ConversionOptions, DocxRenderer, convert_markdown_text,
)

renderer = DocxRenderer(
    template_path="house_style.docx",
    options=ConversionOptions(strict_mode=True),
)
convert_markdown_text(md, "out.docx", renderer=renderer)
```

`MarkdownConverter(renderer=None, options=None, default_context=None,
default_properties=None)` follows the same rule. Its per-call
`context=` and `properties=` merge over the defaults, and the call's
keys win.

## Recommended script pattern

Keep the prose in a `report.md` file next to the script. Render it in
two steps: write the Jinja2-rendered markdown to disk, then build the
DOCX **from that file**. The two deliverables always match, and the
rendered markdown is a readable preview of the report.

```python
from pathlib import Path
from md_reports import (
    ConversionOptions, convert_markdown_file, render_markdown_template,
)

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
OPTIONS = ConversionOptions(strict_mode=True)

(BUILD / "figures").mkdir(parents=True, exist_ok=True)
# ... compute values, save charts to BUILD / "figures" ...

source = (HERE / "report.md").read_text(encoding="utf-8")
built_md = BUILD / "report.md"
built_md.write_text(
    render_markdown_template(
        source, {"title": "Q4 Report", "pct": 14.5, "df": df},
        options=OPTIONS,
    ),
    encoding="utf-8",
)
convert_markdown_file(                   # assets resolve against build/
    built_md,
    BUILD / "report.docx",
    options=OPTIONS,
    properties={"title": "Q4 Report", "author": "Finance"},
)
```

Here `report.md` contains, for example:

````markdown
# {{ title }}

Revenue grew **{{ pct }}%**, as shown in [](#fig-rev).

![Revenue by quarter {% raw %}{#fig-rev}{% endraw %}](figures/revenue.png)

Table: Revenue by region {% raw %}<!-- {#tab-region} -->{% endraw %}

```csv
{{ df | to_csv }}
```
````

For a quick one-off, `convert_markdown_text(md, out, context=...,
base_dir=HERE)` does both steps in one call, but no rendered markdown
is kept.

## Where reports live in a project

When you create a report inside a project (a client repo), use this
layout. A working copy is in [scaffold/](scaffold/). Copy the whole
folder to `reports/<slug>/`, then edit `report.md` and `build.py`.

```
reports/
  _shared/                 # optional: house template.docx, shared helpers
  <slug>/                  # one folder per report, kebab-case
    report.md              # SOURCE: prose + Jinja2 placeholders
    build.py               # the ONE entry point: data -> figures -> md -> docx
    scripts/               # optional helper modules, if build.py gets big
    data/                  # input data; read it, never write it
    assets/                # optional hand-made images (logos, diagrams)
    build/                 # GENERATED; gitignored; safe to delete
      report.md            #   rendered markdown, no Jinja2 left
      report.docx          #   built from build/report.md
      figures/             #   charts written by build.py
      assets/              #   copied from ../assets by build.py
```

Rules:

- **Everything outside `build/` is source. Everything inside it is
  generated.** Add `build/` (or `reports/*/build/`) to `.gitignore`.
  Never hand-edit anything in `build/`.
- **`build/` is self-contained.** Write image paths in `report.md`
  relative to `build/`: `figures/x.png`, `assets/logo.png`.
  `build.py` copies `assets/` into `build/`, so the same paths work
  in a markdown preview and in the DOCX.
- **Inline derived tables.** Pass them through the context, either
  as a pre-built pipe table string or as `{{ df | to_csv }}`, so
  that `build/report.md` stands on its own. `csv` fences show as
  code blocks in a GitHub preview, while pipe tables preview as
  tables. Avoid `csv-file`. If you must use it, the path is
  `../data/x.csv`, which `confine_assets=True` rejects.
- **`build.py`**: resolve every path from
  `HERE = Path(__file__).resolve().parent` so it runs from any
  working directory. Call `matplotlib.use("Agg")`. Use
  `strict_mode=True`. Set at least the `title` property. Write only
  inside its own `build/`. Print both output paths. Run it with
  `uv run python reports/<slug>/build.py`.
- **Shared house style.** Put it in `reports/_shared/template.docx`
  and use it with
  `DocxRenderer(template_path=HERE.parent / "_shared" / "template.docx", options=OPTIONS)`,
  passed as `renderer=` instead of `options=`.
- **Updating a report**: if `reports/<slug>/` already exists, edit it
  and re-run `build.py`. Don't create a second copy. For a new
  period, such as next quarter, create a new slug folder and copy the
  previous `report.md` and `build.py` into it.
- After building, check `build/report.md` for leftover `{{` or
  stray text, and check the DOCX as described under Verifying output.

Defaults worth following:

- **Use `strict_mode=True` in scripts and tests.** The default mode
  turns most problems into `UserWarning`s and leaves breadcrumbs in
  the document (a literal `{{ name }}`, raw `$…$` source, plain text
  where a link should be). Those are easy to ship by accident.
- **Always set `base_dir`, or `ConversionOptions(project_root=...)`,
  with `convert_markdown_text`.** Otherwise relative asset paths
  resolve against the process's current working directory.
  `convert_markdown_file` defaults to the markdown file's folder.
  `project_root` overrides `base_dir`.
- **Wrap `{#label}` markers in `{% raw %}…{% endraw %}` whenever you
  pass `context=`.** The reason is explained under Jinja2 context
  below.
- **Use raw strings (`r"""..."""`) for markdown that contains LaTeX**,
  so that `\frac` and `\int` reach the parser intact.

## Markdown features and their exact syntax

### Figures (block images)
An image that sits alone in its paragraph becomes a figure. The alt
text is the caption, rendered as `Figure N: <alt>` with a Word SEQ
field. The image is scaled down to the page content width when it is
wider. Images that sit inside a paragraph of text are inline and get
no caption. Only local files are allowed: `http(s)://` images are
rejected.

```markdown
![Quarterly revenue by region {#fig-revenue}](charts/revenue.png)
```

### Table captions
A paragraph starting with `Table:` **immediately before** a table
(markdown table, `csv`, or `csv-file`) becomes its caption, rendered
as `Table N: …` above the table. Figure and table counters are
separate. The prefixes come from `figure_caption_prefix` and
`table_caption_prefix`. If you change `table_caption_prefix`, the
caption marker in the markdown changes to match.

### Cross-references
- Add a label with `{#label}` at the end of an image's alt text or a
  table caption. For table captions, the preview-invisible form
  `<!-- {#label} -->` also works and must come at the very end.
- Refer to a label with `[](#label)`, which auto-fills `Figure 3`, or
  with `[custom text](#label)`. Forward references work.
- Unknown labels fall back to plain text with a warning, or raise
  under strict mode.
- When you also pass `context=`, wrap each label in
  `{% raw %}…{% endraw %}`. See Jinja2 context below.

### CSV and DataFrame tables
````markdown
```csv-file
data/quarterly.csv
```

```csv no-header
a,b
1,2
```

```csv
{{ df | to_csv }}
```
````

- `csv-file` holds a single path, resolved like images. `csv` holds
  literal CSV data.
- `no-header` stops the first row from being treated as a header.
- The delimiter is sniffed automatically. Files must be UTF-8.
- `to_csv` is a built-in Jinja2 filter. It calls `.to_csv(index=False)`
  on any object with that method, and pandas is not required. Keyword
  arguments pass through, for example
  `{{ df | to_csv(sep=';', na_rep='-', index=True) }}`.
- Pre-format numbers in the DataFrame, for example with rounding or
  `.map("{:,.1f}".format)`. The cells show exactly the CSV text.

### Math
Inline math is `$E = mc^2$`. Display math is `$$...$$` and becomes its
own paragraph in the `Math equation` style. Both become native,
editable Word equations. A dollar sign next to whitespace is not math,
so `$5 and $10` stays as text. `\(...\)` and `\[...\]` are **not**
supported. When a conversion fails, you get a warning and the raw
source, or a `RenderError` in strict mode.

### Links
`[text](https://...)` and `<a href="...">text</a>` become clickable
hyperlinks. Only `http`, `https`, and `mailto` are allowed. Any other
scheme becomes plain text.

### Also supported
Headings 1 to 6, paragraphs, bold, italic, inline code, fenced code
blocks, block quotes, and nested bullet or ordered lists.

## Things that do NOT work (avoid or work around)

| Construct | What happens | Do instead |
|---|---|---|
| `---` horizontal rule | **Dropped silently** | Use a heading to separate sections |
| Block HTML, including a standalone `<!-- comment -->` line | Warning, content dropped | Use Jinja2 `{# comment #}` when a context is passed |
| Other inline HTML (`<br>`, `<span>`) | Warning, raw text emitted | Use plain markdown |
| Footnotes, task lists, definition lists | Not supported | Use plain lists or a notes section |
| Merged cells, nested tables | Not supported | Flatten the data |
| Remote images | Rejected | Download to a temp dir first and point `base_dir` at it |
| Page breaks, columns, page layout | Not supported | Put them in the template |

## Jinja2 context

- Substitution runs once on the raw text, so values can appear anywhere:
  headings, table cells, image paths, URLs, captions.
- Jinja2 only runs when `context` is non-empty. Without a context,
  `{{ x }}` stays literally in the output.
- **Cross-reference labels clash with Jinja2.** `{#` opens a Jinja2
  comment, so `{#fig-x}` in alt text or a caption, including the
  `<!-- {#x} -->` form, causes a "Missing end of comment tag" error.
  In the default mode, the whole substitution is then skipped with a
  warning and **every** `{{ placeholder }}` stays literal. In strict
  mode it raises `ValidationError`. Whenever a context is passed,
  write labels as `{% raw %}{#fig-x}{% endraw %}`. The
  `[](#fig-x)` references themselves are fine. The same applies to
  any literal `{{`, `{%`, or `{#` text, such as in code blocks.
- When a variable is missing, the default mode emits the literal
  `{{ name }}` plus a warning. Strict mode raises `ValidationError`.
- Values are inserted verbatim, with no escaping. A value containing
  `*`, `_`, `|`, `#`, or `$` will be read as markdown. Escape it or
  sanitise it before passing it in, especially inside table cells.
- `{% for %}` and `{% if %}` leave blank lines behind. Markdown
  usually tolerates them, but put a blank line before and after a
  generated list or table.

## Templates and styles

- Without a template, the packaged default is used. Find it with
  `get_default_template_path()`, then copy it and edit it in Word to
  create a house style.
- Styles used: `Normal`, `Heading 1` to `Heading 6`, `List Bullet` and
  `List Number` (plus their `2` and `3` variants for nesting), `Quote`,
  `Caption`, `Table Grid`, `Code` (optional), and `Math equation`
  (created automatically when missing). Missing styles fall back
  gracefully.
- Anything already in the template body, such as a cover page, table
  of contents, or headers and footers, is kept. The markdown is
  appended after it.
- To show property values inside the document, insert Word fields in
  the template (Insert > Quick Parts > Field > Title / Author / ...).

## Document properties

The `properties=` keys are case-insensitive: `title`, `author`
(`creator`), `subject`, `keywords` (`tags`), `comments`
(`description`), `category` (`categories`), `content_status`,
`identifier`, `language`, `version`, and `last_modified_by`. Unknown
keys warn, or raise under strict mode. Company, custom properties, and
dates cannot be set.

## Untrusted markdown

By default, markdown is trusted like code: Jinja2 is not sandboxed and
asset paths can point anywhere. If the markdown comes from users,
enable both protections:

```python
ConversionOptions(
    sandboxed_context=True,
    confine_assets=True,
    project_root="/srv/work_dir",
    strict_mode=True,
)
```

## Errors

Every error inherits from `MdAstDocxError`:

- `ValidationError`: bad arguments, a missing markdown file, both
  `renderer` and `options` passed, or a Jinja2 failure under strict
  mode.
- `TemplateError`: the template is missing or unreadable.
- `ParseError`: the markdown could not be parsed.
- `RenderError`: rendering failed, for example on bad LaTeX under
  strict mode.

## Verifying output

Word only recomputes SEQ and REF fields on F9 or print. The file
stores precomputed values, so it looks right when first opened. To
check a generated file from code, use python-docx:

```python
from docx import Document
doc = Document("out.docx")
for p in doc.paragraphs:
    print(p.style.name, "|", p.text)
print(len(doc.tables), "tables;", len(doc.inline_shapes), "images")
```

During development, wrap the call in
`warnings.catch_warnings(record=True)` and assert that it produced no
warnings, or use strict mode.

## Reference examples in this repo

`examples/01_quickstart.py` to `examples/09_math.py` cover, in order:
quickstart, Jinja2 context, tables and CSV, DataFrames, the reusable
converter, strict mode, figures with cross-references, properties, and
math. Run one with `uv run python examples/NN_name.py`. Output goes to
`examples/output/`.

`examples/reports/demo-report/` is a runnable copy of [scaffold/](scaffold/).
Run it with `uv run --extra examples python examples/reports/demo-report/build.py`.
