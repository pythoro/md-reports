"""DOCX template loading and style helpers.

These are DOCX-specific concerns and live alongside the DOCX renderer.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from docx import Document as DocxDocument
from docx.document import Document as DocxDoc

from md_reports.errors import TemplateError


def get_default_template_path() -> Path:
    """Return the filesystem path of the packaged default DOCX template."""
    ref = resources.files("md_reports.renderers.docx.resources").joinpath(
        "default_template.docx"
    )
    return Path(str(ref))


def load_docx_template(path: str | Path | None) -> DocxDoc:
    """Load a DOCX template, falling back to the packaged default.

    Raises:
        TemplateError: If ``path`` is given but cannot be opened.
    """
    if path is None:
        default = get_default_template_path()
        if default.exists():
            return DocxDocument(str(default))
        return DocxDocument()
    p = Path(path)
    if not p.exists():
        raise TemplateError(f"Template not found: {p}")
    try:
        return DocxDocument(str(p))
    except Exception as exc:  # noqa: BLE001
        raise TemplateError(f"Failed to load template {p}: {exc}") from exc


def style_exists(doc: DocxDoc, name: str) -> bool:
    """Return True if ``name`` is a concretely-defined style in ``doc``.

    python-docx's ``doc.styles[name]`` only resolves entries with a real
    ``<w:style>`` element — not latent-style placeholders — so a True
    result means Word has actual formatting to apply.
    """
    try:
        doc.styles[name]
        return True
    except KeyError:
        return False
