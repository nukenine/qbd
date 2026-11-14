"""
Fetch & cache waveforms from events at the nearest stations
"""

import time

import pandas as pd
from obspy import Stream, UTCDateTime, read, read_inventory
from obspy.clients.fdsn import Client

from qvb.paths import DATA, WAVES
from qvb.stations import nearest_stations

CLIENTS = {"iris": Client("IRIS"), "raspberry_shake": Client("RASPISHAKE")}


def fetch_event(event, stations, inv, pre=30, post=150):

    path = WAVES / f"{event.id}.mseed"
    if path.exists(): #if event already exists: simple read it in
        return read(str(path))

    t0 = UTCDateTime(event.time.timestamp()) #event time!
    st = Stream() #empty Stream() obj for building in loop

    for _, s in nearest_stations(stations, event.latitude, event.longitude).iterrows():
        try:
            got = CLIENTS[s.source].get_waveforms(s.network, s.station, "*", "HHZ,BHZ,EHZ",t0-pre,t0+post)
            got.merge(fill_value=0) #in case dropped data and gaps present
            tr = got[0] #pulls first trace
            tr.taper(0.05) #5% taper
            tr.remove_response(inventory=inv, output="VEL") #convert counts-->velocity
            st += tr #add to initial Stream() object
        except Exception as err:
            print(f" skip {s.network}.{s.station}: {err}")
        time.sleep(2.1) #to stay under 30 reqs/min for raspberry shake throttle

    if len(st):
        WAVES.mkdir(parents=True, exist_ok=True)
        st.write(str(path), format="MSEED")

    return st


def load_inputs():
    cat = pd.read_parquet(DATA / "catalog.parquet")
    stations = pd.read_parquet(DATA / "stations.parquet")
    inv = read_inventory(DATA / "inventory.xml")

    return cat, stations, inv