"""
catalog.py: Download labeled earthquakes & quarry blasts from USGS for northeast USA
"""

import io
from pathlib import Path

import pandas as pd
import requests

from qvb.paths import DATA, WAVES

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
NORTHEAST = dict(minlatitude=40.0, maxlatitude=47.5,  # TODO: search bounds; needs to be flexible user-input later
                 minlongitude=-80.0, maxlongitude=-66.5)
TIME_ZONE = "America/New_York"  # TODO: TZ, needs to default to this and perhaps be flexible user-input later

# TODO: end should be like a dt.now() or something as latest default
def fetch(eventtype, start="2010-01-01", end="2026-11-21", minmag=1.0):
    """Query USGS database for single "eventtype" (e.g. quarry blast); return as pandas DataFrame."""
    params = dict(format="csv",
                  eventtype=eventtype, #key names/format from USGS database
                  starttime=start,
                  endtime=end,
                  minmagnitude=minmag,
                  orderby="time",
                  limit=20_000,
                  **NORTHEAST)

    resp = requests.get(USGS_URL, params=params, timeout=60) #dictionary to query string at end of URL
    resp.raise_for_status() #since failed request above wouldnt error out

    return pd.read_csv(io.StringIO(resp.text))


def build_catalog():
    df = pd.concat([fetch("earthquake"), fetch("quarry blast")], ignore_index=True) #stack vertically, renumber index
    df["time"] = pd.to_datetime(df["time"], utc=True) #to UTC for math later

    local = df["time"].dt.tz_convert(TIME_ZONE) #quarries blast during day so need local time for analysis

    df["local_hour"] = local.dt.hour
    df["is_weekend"] = (local.dt.day_of_week >= 5).astype(int) #sat/sun==5/6; returns True==1, False==0
    df["label"] = (df["type"] == "quarry blast").astype(int) #returns True==1, False==0
    df["region"] = df["place"].str.split(", ").str[-1] #split to get US State.

    keep = ["id", "time", "latitude", "longitude", "depth", "mag", "type", "label", "local_hour", "is_weekend", "place", "region"]

    return df[keep]


def main():
    DATA.mkdir(exist_ok=True)
    cat = build_catalog()
    cat.to_parquet(DATA / "catalog.parquet", index=False)  # for compression vs. csv

    print(f"\nNo. of Events: {len(cat)}\n") #TODO: need logging module implemented instead of print()
    print(cat["type"].value_counts())


if __name__ == "__main__":
    main()