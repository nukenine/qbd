"""
Import these paths as modules in src .py files so that user
gets relative imports without anything breaking!
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # to repo root
DATA = ROOT / "data"
WAVES = DATA / "waveforms"
DOCS_IMG = ROOT / "docs" / "img"

