"""Jinja2-based context substitution applied before markdown parsing.

The substitution runs once on the raw markdown text. Values flow into
every place text appears: body, headings, table cells, image paths,
CSV file paths, inline CSV data, link URLs, captions, etc.

Behavior on undefined variables and Jinja2 errors depends on
``strict_mode``:

* strict: any undefined variable or template error raises
  :class:`ValidationError`.
* non-strict: a simple ``{{ name }}`` whose key is missing renders as
  the literal ``{{ name }}`` and emits a warning. Other Jinja2 errors
  (syntax errors, iteration over undefined, etc.) cause the markdown
  to be left unchanged with a warning.
"""

from __future__ import annotations

import warnings
from typing import Any

from jinja2 import (
    Environment,
    StrictUndefined,
    TemplateSyntaxError,
    Undefined,
    UndefinedError,
)

from md_ast_docx.errors import ValidationError


class _KeepUndefined(Undefined):
    """An ``Undefined`` that renders as ``{{ name }}`` and warns.

    Used in non-strict mode so that simple missing-variable references
    survive substitution as visible breadcrumbs rather than vanishing.
    """

    __slots__ = ()

    def __str__(self) -> str:  # type: ignore[override]
        name = self._undefined_name or ""
        warnings.warn(
            f"Undefined Jinja2 variable: {name!r}",
            stacklevel=4,
        )
        return "{{ " + name + " }}"


def apply_context(
    text: str,
    context: dict[str, Any] | None,
    strict: bool,
) -> str:
    """Render ``text`` as a Jinja2 template against ``context``.

    Returns the rendered text. If ``context`` is None or empty, returns
    the input unchanged. See module docstring for error behavior.
    """
    if not context:
        return text
    env = Environment(
        undefined=StrictUndefined if strict else _KeepUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    try:
        template = env.from_string(text)
        return template.render(**context)
    except (TemplateSyntaxError, UndefinedError) as exc:
        if strict:
            raise ValidationError(
                f"Jinja2 substitution failed: {exc}"
            ) from exc
        warnings.warn(
            f"Jinja2 substitution failed; leaving markdown unchanged. "
            f"Error: {exc}",
            stacklevel=3,
        )
        return text
