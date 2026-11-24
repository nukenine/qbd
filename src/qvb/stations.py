from pathlib import Path

from obspy import Inventory
from obspy.clients.fdsn import Client
from obspy.geodetics import gps2dist_azimuth
import pandas as pd

from qvb.catalog import NORTHEAST
from qvb.paths import DATA


def get_inventory() -> tuple[Inventory, Inventory]:  # shouldn't the networks be whatever is the in catalog.parquet pull? bc this wouldn't translate to other regions
    """
    Returns obspy Inventory for IRIS DMC and Raspberry Shake network
    """

    # Client("IRIS") deprecated since IRIS-->EarthScope
    iris = Client("EARTHSCOPE").get_stations(network="NE,LD,US,N4", #TODO: this shouldn't be hardwired?
                                       channel="HHZ,BHZ", #TODO: same, shouldnt be hardwired?
                                       level="response",
                                       **NORTHEAST) #TODO: def shouldn't be hardwired?

    shake = Client("RASPISHAKE", timeout=180).get_stations(network="AM",
                                              channel="EHZ",
                                              level="response",
                                              **NORTHEAST)

    return iris, shake


def to_table(inv: Inventory, source: str) -> pd.DataFrame:
    """
    Expects obspy Inventory() object and a source str like `iris` output as pandas DataFrame
    """

    rows = []
    for net in inv:
        for sta in net:
            rows.append(dict(network=net.code,
                             station=sta.code,
                             latitude=sta.latitude,
                             longitude=sta.longitude,
                             source=source))

    # drop duplicates in case changing equipment leads to dupes
    return pd.DataFrame(rows).drop_duplicates(["network", "station"])


def nearest_stations(stations, lat, lon, max_km=150, n=10):
    # axis=1 is over rows, axis=0 would be over columns; convert to km; `dist` a pd.Series!
    dist = stations.apply(lambda r: gps2dist_azimuth(lat, lon, r.latitude, r.longitude)[0] / 1000, axis=1)

    #assign giving new col on stations; filter by max_km; default keep 4 closest
    return stations.assign(dist_km=dist).query("dist_km <= @max_km").nsmallest(n, "dist_km")


def main():
    DATA.mkdir(exist_ok=True)
    iris, shake = get_inventory()
    iris_tab = to_table(iris, source="iris")  # source is labeling
    shake_tab = to_table(shake, source="shake")

    merged_tab = pd.concat([iris_tab, shake_tab])
    merged_tab.to_parquet(DATA / "stations.parquet", index=False)

    print(f"\nStations\n{merged_tab["source"].value_counts()}")

    #save as stationxml for future, using obspy inventory additive
    (iris + shake).write(str(DATA / "inventory.xml"), format="STATIONXML")


if __name__ == "__main__":
    main()