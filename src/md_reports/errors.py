"""Exception types raised by md_reports."""

from __future__ import annotations


class MdAstDocxError(Exception):
    """Base class for all md_reports exceptions."""


class TemplateError(MdAstDocxError):
    """Raised for template loading or style validation failures."""


class ParseError(MdAstDocxError):
    """Raised when markdown cannot be parsed into the internal model."""


class RenderError(MdAstDocxError):
    """Raised when rendering the model to DOCX fails."""


class ValidationError(MdAstDocxError):
    """Raised when input arguments fail validation."""
