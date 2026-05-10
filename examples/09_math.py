"""Render LaTeX math as native Word equations.

Inline math (between single ``$``) and display math (between ``$$``)
are converted to OMML — the same XML Word's equation editor produces —
so they open as editable equations rather than plain text or images.

* ``$E = mc^2$`` → inline equation.
* ``$$\\int_0^1 x\\,dx = \\tfrac{1}{2}$$`` → centered display equation.

Whitespace-adjacent dollars (``$ 5 ``) are intentionally not treated as
math, so prose with currency stays untouched.

If a LaTeX expression fails to convert, the renderer warns and falls
back to the original ``$...$`` source text. In strict mode it raises
``RenderError`` instead.

Run from the repo root::

    uv run python examples/09_math.py
"""

from __future__ import annotations

from pathlib import Path

from md_reports import convert_markdown_text

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)


MARKDOWN = r"""
# Math support

The mass-energy equivalence relation is $E = mc^2$, where $m$ is the
rest mass and $c$ is the speed of light.

## Display equations

A definite integral renders centered on its own line:

$$\int_0^1 x^2 \, dx = \tfrac{1}{3}$$

The Gaussian density:

$$f(x) = \frac{1}{\sigma \sqrt{2\pi}} \exp\!\left(
    -\frac{(x - \mu)^2}{2\sigma^2}
\right)$$

## Mixed prose and math

For a right triangle with legs $a$ and $b$, the hypotenuse $c$ is
given by $c = \sqrt{a^2 + b^2}$. Costs of $5 and $10 are not parsed as
math because of the surrounding whitespace.
"""


def main() -> None:
    out = OUT / "09_math.docx"
    convert_markdown_text(MARKDOWN, out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
