# CLAUDE.md

## Project Overview

md-ast-docx is a Python library that converts Markdown content into DOCX
files, using a DOCX template for styling.

Primary intent:
- Embedding in Python scripts (no CLI-first design)
- Clean API surface
- Predictable styling through template-based rendering

Current phase:
- Early scaffold
- Architecture and implementation plan defined in plan.md

## Product Goals

1. Convert Markdown text or files to DOCX through Python API functions.
2. Use a provided template for style fidelity.
3. Provide a packaged default template when no template is supplied.
4. Support common Markdown blocks and inlines with robust behavior.
5. Include basic table rendering in v1.
6. Render links as clickable DOCX hyperlinks where valid.

## Confirmed Scope Decisions

1. No CLI is required for v1; API-first design.
2. Basic table support is included in v1.
3. Markdown and HTML links should be clickable in DOCX output.
4. A default DOCX template should ship with the package.

## Planned Public API

Primary functions:
- convert_markdown_text(markdown_text, output_path, template_path=None,
  options=None) -> Path
- convert_markdown_file(markdown_path, output_path, template_path=None,
  options=None) -> Path

Optional reusable object:
- MarkdownDocxConverter(template_path=None, options=None)
- converter.convert_text(...)
- converter.convert_file(...)

## Proposed Package Layout

- src/md_ast_docx/api.py
- src/md_ast_docx/options.py
- src/md_ast_docx/model.py
- src/md_ast_docx/parser.py
- src/md_ast_docx/renderer.py
- src/md_ast_docx/template.py
- src/md_ast_docx/errors.py
- src/md_ast_docx/resources/default_template.docx

## Parsing and Rendering Strategy

Parser:
- Use markdown-it-py for CommonMark tokenization.
- Use mdit-py-plugins for table support.
- Normalize tokens into an internal model before rendering.

Renderer:
- Use python-docx for document generation.
- Apply template styles (Normal, Heading styles, list/quote/code/table
  fallbacks).
- Keep rendering logic deterministic and testable.

## Table Support Policy (v1)

Supported:
- Basic Markdown tables with header and body rows.
- Standard cell text with limited inline formatting.

Deferred:
- Row or column spans.
- Nested tables.
- Advanced width and layout controls.

## Link Handling Notes

Clickable DOCX links require low-level XML and relationship handling.

Complexity points:
1. Add external URL relationship entries.
2. Build w:hyperlink elements with nested runs.
3. Preserve formatting inside linked text when possible.
4. Validate or sanitize links; degrade gracefully when invalid.

Fallback behavior:
- If link creation fails, emit plain visible text and continue.

## Error Model

Define explicit exceptions:
- TemplateError
- ParseError
- RenderError
- ValidationError

Guidelines:
- Fail fast for unreadable template, invalid output target, and hard
  conversion failures.
- Unsupported markdown can warn or raise depending on strict mode.
- Error messages should include actionable context.

## Engineering Conventions

Language and runtime:
- Python package under src layout.
- Keep strong type hints across public API and core modules.

Tooling preferences for this repo:
- uv for dependency and environment management.
- pytest for tests.
- ruff for linting and formatting.
- Ruff line length target: 79.

Code style:
- Keep modules small and focused.
- Prefer pure functions for parsing and mapping.
- Keep document XML concerns isolated to renderer helpers.

## Testing Expectations

Unit tests should cover:
1. Parser token to internal model mapping.
2. Template validation and style fallback behavior.
3. Hyperlink helper correctness and fallback path.
4. Basic table rendering behavior.

Integration tests should cover:
1. End-to-end Markdown to DOCX conversion.
2. Default template usage when no template path is given.
3. Representative style and content checks.

## Out of Scope for v1

- Advanced page layout controls.
- Complex table geometry and merged cells.
- Rich media workflows beyond basic future extension points.

## Practical Guardrails for AI Contributors

1. Do not add CLI-first workflows unless requested.
2. Preserve API-first design and backward-compatible signatures.
3. Keep dependencies minimal and justified.
4. Avoid introducing fragile behavior around template styles.
5. Prefer incremental changes with tests in the same change.
6. Do not silently drop content; warn or fail per configuration.

## Quick Start Tasks for Next Development Session

1. Update pyproject metadata and dependencies.
2. Add module skeleton and public exports.
3. Implement options and custom exceptions.
4. Implement parser normalization for core blocks and tables.
5. Implement template loader and default template resolver.
6. Implement renderer with hyperlink helper.
7. Add pytest fixtures and integration tests.
8. Document embedding usage in README.
