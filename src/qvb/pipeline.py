"""
pipeline.py: Run entire pipeline from catalog/station build through detection/characterization
"""

import argparse         # for commandline running and --flags!
import shutil           # rmtree: deletes a folder and everything in it
import subprocess       # kind of a terminal emulator for external program running, e.g. dbt
import time             # stopwatch, perf_counter

from qvb import catalog, stations, waveforms
from qvb.paths import DATA, ROOT, WAVES

# dbt
def run_dbt():
    subprocess.run(["dbt", "build"], cwd=ROOT / "qvb_dbt", check=True)

# One line per stage in order of running
STAGES = [
    ("catalog", lambda args: catalog.main(), [DATA / "catalog.parquet"]),
    ("stations", lambda args: stations.main(), [DATA / "stations.parquet", DATA / "inventory.xml"]),
    ("waveforms", lambda args: waveforms.main(ids=args.event, n_per_type=args.n, refresh=args.refresh), [WAVES]),
]

NAMES = [name for name, _, _ in STAGES]

def clean_paths(paths):
    """Clear output, e.g. files/folders, so that a stage starts from scratch"""
    for p in paths:
        if p.is_dir():
            shutil.rmtree(p)  # delete directory and contents
        elif p.exists():
            p.unlink()  # elif a file: delete it.


def choose_stages(args):
    if args.only:
        return [s for s in STAGES if s[0] in args.only]
    if args.start:
        return STAGES[NAMES.index(args.start):]

    return STAGES


def main():
    parser = argparse.ArgumentParser(description="Quake vs. Blast Pipeline")

    parser.add_argument("--only", nargs="+", choices=NAMES,
                        help="Run just these stages.")
    parser.add_argument("--from", dest="start", choices=NAMES,
                        help="Run this stage and all stages after it.")
    parser.add_argument("--clean", action="store_true",
                        help="Delete the chosen stages' outputs before running") #`store_true` default is False
    parser.add_argument("--refresh", action="store_true",
                        help="ignore cached events and re-download")

    parser.add_argument("--n", type=int, default=5,
                        help="Number of events per event type to download.")
    parser.add_argument("--event", nargs="+",
                        help="Download specific event IDs")

    args = parser.parse_args() #parse 'em

    for name, run, outputs in choose_stages(args):
        if args.clean:
            clean_paths(outputs)

        print(f"\n=== {name} ===")
        t = time.perf_counter()
        run(args)
        print(f"=== {name} done in {time.perf_counter() - t:.1f}s ===")


if __name__ == "__main__":
    main()