"""Smoke test for the report-project scaffold shipped with the skill.

The scaffold lives in ``.claude/skills/md-reports/scaffold`` and a
runnable copy lives in ``examples/reports/demo-report``. The copy must
stay identical to the scaffold, and building it must produce both the
rendered markdown and the DOCX.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from docx import Document as DocxDocument

ROOT = Path(__file__).resolve().parents[1]
SCAFFOLD = ROOT / ".claude" / "skills" / "md-reports" / "scaffold"
DEMO = ROOT / "examples" / "reports" / "demo-report"
SOURCE_FILES = ["build.py", "report.md", "data/sales.csv"]


@pytest.mark.parametrize("rel", SOURCE_FILES)
def test_demo_matches_scaffold(rel: str) -> None:
    scaffold = (SCAFFOLD / rel).read_bytes().replace(b"\r\n", b"\n")
    demo = (DEMO / rel).read_bytes().replace(b"\r\n", b"\n")
    assert demo == scaffold, f"{rel} drifted from the skill scaffold"


def test_scaffold_builds_md_and_docx(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    report = tmp_path / "demo-report"
    shutil.copytree(SCAFFOLD, report, ignore=shutil.ignore_patterns("build"))
    subprocess.run(
        [sys.executable, "-W", "error", str(report / "build.py")],
        check=True,
        cwd=tmp_path,
    )
    built_md = report / "build" / "report.md"
    built_docx = report / "build" / "report.docx"
    assert (report / "build" / "figures" / "revenue.png").is_file()

    md = built_md.read_text(encoding="utf-8")
    assert "{{" not in md and "{%" not in md
    assert "](figures/revenue.png)" in md

    doc = DocxDocument(str(built_docx))
    captions = [p.text for p in doc.paragraphs if p.style.name == "Caption"]
    assert captions == [
        "Figure 1: Revenue by quarter",
        "Table 1: Quarterly sales",
    ]
    assert len(doc.tables) == 1
    assert len(doc.inline_shapes) == 1
    assert doc.core_properties.title == "Quarterly Sales Report"
