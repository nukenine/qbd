"""
Import these paths as modules in src .py files so that user
gets relative imports without anything breaking!
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # to repo root
DATA = ROOT / "data"  # holds .parquet catalog/stations, as well as waveforms dir (with .mseed files)
WAVES = DATA / "waveforms"  # holds the .mseed files (miniSEED)
DOCS_IMG = ROOT / "docs" / "img"  # helpful images of analysis along the way