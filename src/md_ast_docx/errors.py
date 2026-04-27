"""Exception types raised by md_ast_docx."""

from __future__ import annotations


class MdAstDocxError(Exception):
    """Base class for all md_ast_docx exceptions."""


class TemplateError(MdAstDocxError):
    """Raised for template loading or style validation failures."""


class ParseError(MdAstDocxError):
    """Raised when markdown cannot be parsed into the internal model."""


class RenderError(MdAstDocxError):
    """Raised when rendering the model to DOCX fails."""


class ValidationError(MdAstDocxError):
    """Raised when input arguments fail validation."""
