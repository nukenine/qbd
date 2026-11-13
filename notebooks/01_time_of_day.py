"""
Group event types by local hour and calculate %'s of share of respective events in each hour bucket.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

catalog = pd.read_parquet(ROOT / "data" / "catalog.parquet")

counts = (
    catalog.groupby(["local_hour", "type"])
    .size()
    .unstack(fill_value=0)
    .reindex(range(24), fill_value=0)
)

share = counts / counts.sum()

# plotting
ax = share.plot(kind="bar",
                figsize=(12,4),
                width=0.8,
                zorder=2,
                color={"earthquake": "#2b6cb0", "quarry blast": "#c53030"},
                edgecolor="white",
                alpha=0.8)
ax.set_xlabel("Local Hour [EST]", fontsize=14)
ax.set_ylabel("% Respective Event Type", fontsize=14)
ax.tick_params(axis="both", labelsize=16)
ax.tick_params(axis="x", labelrotation=0)
ax.grid(alpha=0.75, zorder=1)
ax.legend(title=None, frameon=False, fontsize=16)

plt.tight_layout()
plt.savefig(ROOT / "docs" / "img" / "percent_share.png")