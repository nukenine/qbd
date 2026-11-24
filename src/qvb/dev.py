
from typing import Literal

from qvb.paths import WAVES
from qvb.waveforms import fetch_event, load_inputs


GOLDEN = {
    "eq": "us6000u274",  # earthquake: mag 4.1 north of toronto jan2026, captured on raspishake
    "qb": "us7000qrw9",  # future quarry blast
}


def load_golden(kind: Literal["eq", "qb"] = "eq", refresh=False):
    """
    Load seismogram(s) determined to be golden from database via manual analysis for testing.
    :param kind: "eq" | "qb" for earthquake or quarry blast
    :param refresh: if True, delete existing .mseed file from disk and re-pull/download
    :return: event, Stream() object of the pulled traces for the event, stations DataFrame, obspy Inventory() object (stationxml)
    """
    event_id = GOLDEN.get(kind)  # can be empty if doesn't exist in GOLDEN
    if not event_id:
        raise ValueError(f"No golden event set for type: {kind!r}. Options are {list(GOLDEN)}.")

    cat, stations, inv = load_inputs()  # load event & station catalog, and stationxml
    event_match = cat[cat.id == event_id]
    if event_match.empty:  # i.e. if for whatever reason the event id is not in the catalog
        raise LookupError(f"Golden {kind!r} event {event_id!r} is not in catalog.parquet file."
                          "Recommend: rebuild catalog with `python -m qvb.pipeline --only catalog`"
                          "Before that, check data and magnitude of event versus the catalog dates/mags")

    ev = event_match.iloc[0]  # cleaner as `ev`

    return ev, fetch_event(ev, stations, inv, refresh=refresh), stations, inv