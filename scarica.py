"""Download Dukascopy Nasdaq 100 CFD 1-minute bid candles (close, volume) for a date range into duka/YYYYMMDD.parquet.
Same file format as data/duka/ of the graficonn project. Usage: python scarica.py 2021-01-01 2021-06-30"""
import lzma, sys, time, urllib.error, urllib.request
from pathlib import Path
import numpy as np, pandas as pd

OUT = Path("duka")
DUKA = np.dtype([("s", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"), ("h", ">i4"), ("v", ">f4")])


def day_file(day):
    url = (f"https://datafeed.dukascopy.com/datafeed/USATECHIDXUSD/{day.year}/{day.month - 1:02d}/{day.day:02d}"
           "/BID_candles_min_1.bi5")
    for k in range(9):                                   # Dukascopy blocks bursts: back off up to ~20 min
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return b""
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass
        time.sleep(min(5 * 2 ** k, 600))
    raise RuntimeError(url)


def main(start, end):
    OUT.mkdir(exist_ok=True)
    end = min(pd.Timestamp(end, tz="UTC"), pd.Timestamp.now(tz="UTC").normalize() - pd.Timedelta(days=1))
    failed = []
    for day in pd.date_range(pd.Timestamp(start, tz="UTC"), end, freq="D"):
        if day.weekday() == 5:                           # Saturday: market closed
            continue
        try:
            raw = day_file(day)
        except Exception as e:
            print(day.date(), "fallito:", e, flush=True)
            failed.append(str(day.date()))
            continue
        a = np.frombuffer(lzma.decompress(raw), DUKA) if raw else np.zeros(0, DUKA)
        a = a[a["v"] > 0]
        pd.DataFrame({"dclose": a["c"] / 1000.0, "dvol": a["v"].astype(float)},
                     index=day + pd.to_timedelta(a["s"].astype(np.int64), unit="s")).to_parquet(OUT / f"{day:%Y%m%d}.parquet")
        print(day.date(), len(a), "minuti", flush=True)
        time.sleep(1.0)
    print("giorni falliti:", failed or "nessuno")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
