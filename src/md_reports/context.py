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

import inspect
import warnings
from typing import Any

from jinja2 import (
    Environment,
    StrictUndefined,
    TemplateError,
    Undefined,
)
from jinja2.sandbox import SandboxedEnvironment

from md_reports.errors import ValidationError


def _to_csv_filter(value: Any, **kwargs: Any) -> str:
    """Jinja2 filter that converts a DataFrame-like to CSV text.

    Duck-typed: any object with a ``.to_csv()`` method that returns a
    string is accepted (pandas DataFrames are the typical case).

    By default ``index=False`` is passed so the DataFrame index is
    dropped. Other kwargs pass through to the underlying ``to_csv()``
    call (e.g., ``sep=";"``, ``na_rep="—"``). The trailing newline
    pandas appends is stripped so the rendered text drops cleanly into
    a ``csv`` fence without producing a phantom empty row.
    """
    if not hasattr(value, "to_csv"):
        raise TypeError(
            f"to_csv filter requires an object with a .to_csv() "
            f"method (e.g., a pandas DataFrame); got "
            f"{type(value).__name__}"
        )
    method = value.to_csv
    if "index" not in kwargs:
        try:
            if "index" in inspect.signature(method).parameters:
                kwargs["index"] = False
        except (TypeError, ValueError):
            pass
    result = method(**kwargs)
    if result is None:
        raise TypeError(
            "to_csv filter expected a string return value but got "
            "None — the underlying .to_csv() likely wrote to a file "
            "or buffer rather than returning text"
        )
    return str(result).strip()


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
    sandboxed: bool = False,
) -> str:
    """Render ``text`` as a Jinja2 template against ``context``.

    Returns the rendered text. If ``context`` is None or empty, returns
    the input unchanged. See module docstring for error behavior.

    When ``sandboxed`` is True, a ``SandboxedEnvironment`` is used to
    block access to most attributes/built-ins on context values. Enable
    this when the markdown source is not fully trusted.
    """
    if not context:
        return text
    env_cls = SandboxedEnvironment if sandboxed else Environment
    env = env_cls(
        undefined=StrictUndefined if strict else _KeepUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    env.filters["to_csv"] = _to_csv_filter
    try:
        template = env.from_string(text)
        return template.render(**context)
    except (TemplateError, TypeError, ValueError) as exc:
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
