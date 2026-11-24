"""
Fetch & cache waveforms from closest existing stations.
"""

import time
import traceback
from functools import cache

import numpy as np
import pandas as pd
from obspy import Stream, UTCDateTime, read, read_inventory
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.header import FDSNException

from qvb.dsp import bandpass
from qvb.paths import DATA, WAVES
from qvb.stations import nearest_stations

SOURCES = {"iris": "EARTHSCOPE", "shake": "RASPISHAKE"}

_unavailable = set()       # sources that failed to connect during this run

def get_client(source):
    """One FDSN client per source; after a failed connection, skip that source for the rest of the run."""
    if source in _unavailable:
        raise FDSNNoServiceException(f"{source} unavailable earlier in this run")
    try:
        return _make_client(source)
    except FDSNNoServiceException:
        _unavailable.add(source)
        raise


@cache
def _make_client(source):
    return Client(SOURCES[source], timeout=30, _discover_services=False)


def qc_raw(tr, gap_s, window_s):
    """
    Quality control checking on raw counts before signal processing occurs.
    :param tr: Obspy.Trace() object
    :param gap_s: output in seconds from Stream().get_gaps(), which is the gap of missing data
    :param window_s: pre-event (s) + post-event (s), i.e. the entirety of the cut record
    :return: None (if successfully passed quality control test) | error message (if failed qc test)
    """
    # TODO: these kinds of hardwired threshold values should all be set in an importable param file
    if len(np.unique(tr.data)) < 10:  # dead channels tend to have exceedingly few unique data points when in units of counts!
        return f"FLAT/DEAD CHANNEL:\n{tr.stats.network}\n{tr.stats.station}\n{tr.stats.location}\n{tr.stats.channel}"
    if gap_s / window_s > 0.05:
        return f"gaps ({gap_s:.0f}sec missing)"

    return None


def snr(x, fs, dist_km, pre=30, win=2.0):
    # TODO: MOST of these hardwired params should be in importable param file!
    y = bandpass(x, fs, 2.0, min(10.0, 0.45 * fs))
    i0 = int(pre * fs)  # approx event time
    noise = y[int(10 * fs): i0 - int(2 * fs)]  # noise starts ~10sec in and ~2sec before event time; obv an approximation
    start = i0 + int((dist_km / 6.1 - 2) * fs)  # using standard wavespeeds, P-arrival, minus 2 seconds
    end = i0 + int((dist_km / 3.5 + 10) * fs)  # using standard wavespeeds, S-arrival, add 10 seconds for coda
    sig = y[start:end]  # signal window using above wavespeed windows

    n = int(win * fs)  # window length in units of samples
    moving_rms = np.sqrt(np.convolve(sig ** 2, np.ones(n) / n, mode="valid"))  # moving avg w/ window; then sqrt(energy) goes back to amplitude, mode="valid" cuts off <len(n) windows
    noise_level = 1.4826 * np.median(np.abs(noise))  # 1.4826 noise RMS constant for gaussian normal noise; noise_level equals sigma, mediant to rule out spikes, etc.

    return float(moving_rms.max() / noise_level)


def fetch_event(event, stations, inv, pre=30, post=150, min_snr=3.0, refresh=False):
    path = WAVES / f"{event.id}.mseed"
    if path.exists() and not refresh:
        return read(str(path))  # if exists, just read mseed into a new Stream() object

    t0 = UTCDateTime(event.time.timestamp())  # convert from POSIX timestamp
    st, dropped = Stream(), []
    for _, s in nearest_stations(stations, event.latitude, event.longitude).iterrows():
        name = f"{s.network}.{s.station}"
        qc_fail_reason = None  # initialize cleanly w/ None so no leakage from a past station!
        try:
            stream_ = get_client(s.source).get_waveforms(network=s.network,
                                                      station=s.station,
                                                      location="*",
                                                      channel="HHZ,BHZ,EHZ",
                                                      starttime=t0 - pre,
                                                      endtime=t0 + post)

            gap_s = sum(g[6] for g in stream_.get_gaps() if g[6] > 0)  # pos [6] is gap length in sec from .get_gaps()
            stream_.merge(fill_value=0)
            tr = stream_[0]  # TODO: not sure if should be hardwired for 0th channel?

            qc_fail_reason = qc_raw(tr, gap_s, pre + post)  # returns None if no failure and quality good.
            if qc_fail_reason is None:
                nyq = tr.stats.sampling_rate / 2  # nyquist/folding frequency
                tr.detrend("demean")  # TODO: all should be in param file
                tr.taper(0.05)
                tr.remove_response(inventory=inv, output="VEL", pre_filt=(0.5, 1.0, 0.8 * nyq, 0.9 * nyq))  # adding prefilter to attempt to remove extra noise, based on stations nyquist
                r = snr(tr.data, tr.stats.sampling_rate, s.dist_km, pre)
                if r < min_snr:  # now check SNR
                    qc_fail_reason = f"low SNR ({r:.1f} < {min_snr})"
        except FDSNException as err:
            first_line = str(err).splitlines()[0]
            qc_fail_reason = f"No data ({type(err).__name__}: {first_line})"
        except Exception as err:
            #traceback.print_exc()
            qc_fail_reason = f"ERROR {type(err).__name__}: {err}"
        time.sleep(2.1)  # RASPISHAKE network requires under 30 requests/min!

        if qc_fail_reason:
            dropped.append((name, qc_fail_reason))  # add network.station to list of failures
        else: #if not a failure
            st += tr  # add it to Stream() object

    print(f"{event.id}: kept {len(st)}, dropped {len(dropped)} stations")
    for name, reason in dropped:
        print(f"   - {name}: {reason}")
    if len(st):  # if any traces in stream
        WAVES.mkdir(parents=True, exist_ok=True)
        st.write(str(path), format="MSEED", encoding="FLOAT64")
    return st


def load_inputs():
    cat = pd.read_parquet(DATA / "catalog.parquet")
    stations = pd.read_parquet(DATA / "stations.parquet")
    inv = read_inventory(str(DATA / "inventory.xml"))

    return cat, stations, inv


def main(ids=None, n_per_type=2, refresh=False):
    cat, stations, inv = load_inputs()  # read in existing catalog/stations.parquet and response file

    #TEMP bc raspberry shake server sucks.
    stations=stations[stations.source=="iris"]

    if ids:
        events = cat[cat.id.isin(ids)]
    else:  # if no explicit events passed as arg by user
        big = cat[(cat.time >= pd.Timestamp("2023-01-01", tz="UTC")) & (cat.mag >= 2.0)]  # TODO: definitely not hardwire this
        events = big.sort_values("time", ascending=False).groupby("type").head(n_per_type) #take the top N largest of each event type

    for i, (_, ev) in enumerate(events.iterrows(), 1):
        print(f"[{i}/{len(events)} events]: {ev.type}", end=" ")
        fetch_event(ev, stations, inv, refresh=refresh)


if __name__ == "__main__":
    main()