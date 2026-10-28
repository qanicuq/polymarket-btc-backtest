"""Coverage scan: which PMXT archive hours contain Polymarket BTC 5-minute windows? Every hour, START..END (UTC).

Usage: python scripts/coverage.py START_DATE END_DATE NAME      e.g. 2026-04-01 2026-05-06 01
Writes coverage/coverage_NAME.csv (one row per hour) and coverage/windows_NAME.jsonl (one line per 5-minute window:
slug, tokens, outcomes, outcome prices, and whether it appears in that hour's file). Both are updated after every
hour, and hours already finished are skipped, so a re-run resumes where it stopped.
"""
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

START, END, NAME = sys.argv[1], sys.argv[2], sys.argv[3]
TMP = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), f"pmxt_{NAME}.parquet")
os.makedirs("coverage", exist_ok=True)
CSV_PATH = f"coverage/coverage_{NAME}.csv"
WIN_PATH = f"coverage/windows_{NAME}.jsonl"
UA = {"User-Agent": "polymarket-btc-backtest/1.0 (research; github.com/qanicuq/polymarket-btc-backtest)"}
FIELDS = ["hour", "file", "mb", "windows_on_gamma", "windows_in_file", "distinct_assets", "seconds", "note"]


def get_json(url, tries=4):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            retry = not isinstance(e, urllib.error.HTTPError) or e.code in (429, 500, 502, 503, 504)
            if retry and i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise


def window_info(ts):
    slug = f"btc-updown-5m-{ts}"
    try:
        ev = get_json(f"https://gamma-api.polymarket.com/events?slug={slug}")
        if not ev:
            return {"slug": slug, "start": ts, "gamma": "missing"}
        m = ev[0]["markets"][0]
        return {"slug": slug, "start": ts, "gamma": "ok", "condition_id": m.get("conditionId"),
                "tokens": json.loads(m["clobTokenIds"]), "outcomes": json.loads(m["outcomes"]),
                "outcome_prices": json.loads(m.get("outcomePrices") or "[]"), "closed": m.get("closed")}
    except Exception as e:  # noqa: BLE001
        return {"slug": slug, "start": ts, "gamma": "error", "error": str(e)[:120]}


def download(hour):
    from pmxt_fetch import NotInArchive, fetch      # stall-proof download with byte-range resume
    try:
        n, reconnects = fetch(f"https://r2v2.pmxt.dev/polymarket_orderbook_{hour}.parquet", TMP)
        return round(n / 1e6, 1), (f"{reconnects} reconnects" if reconnects else "")
    except NotInArchive:
        return None, "HTTP 404"
    except Exception as e:  # noqa: BLE001
        return None, "download error: " + str(e)[:80]


# resume: keep finished hours, redo hours that ended in an error
rows = []
if os.path.exists(CSV_PATH):
    with open(CSV_PATH, newline="") as f:
        rows = [r for r in csv.DictReader(f) if not r["note"].startswith(("ERR", "download error"))]
done = {r["hour"] for r in rows}
seen_slugs = set()
if os.path.exists(WIN_PATH):
    with open(WIN_PATH) as f:
        seen_slugs = {json.loads(line)["slug"] for line in f if line.strip()}

day, end = dt.date.fromisoformat(START), dt.date.fromisoformat(END)
while day <= end:
    for hh in range(24):
        hour = f"{day.isoformat()}T{hh:02d}"
        if hour in done:
            continue
        t0 = time.time()
        row = {k: "" for k in FIELDS}
        row["hour"] = hour
        mb, note = download(hour)
        row.update(file="yes" if mb else "no", mb=mb or "", note=note)
        if mb:
            try:
                start_ts = int(dt.datetime.strptime(hour, "%Y-%m-%dT%H").replace(tzinfo=dt.timezone.utc).timestamp())
                with ThreadPoolExecutor(6) as ex:
                    wins = list(ex.map(window_info, [start_ts + k * 300 for k in range(12)]))
                tok_set = pa.array([t for w in wins for t in w.get("tokens", [])], type=pa.string())
                present, assets = set(), set()
                for b in pq.ParquetFile(TMP).iter_batches(batch_size=2_000_000, columns=["asset_id"]):
                    col = b["asset_id"]
                    assets.update(pc.unique(col).to_pylist())
                    present.update(pc.unique(col.filter(pc.is_in(col, value_set=tok_set))).to_pylist())
                for w in wins:
                    w["hour_file"] = hour
                    w["in_file"] = any(t in present for t in w.get("tokens", []))
                row["windows_on_gamma"] = sum(1 for w in wins if w["gamma"] == "ok")
                row["windows_in_file"] = sum(1 for w in wins if w["in_file"])
                row["distinct_assets"] = len(assets)
                with open(WIN_PATH, "a") as f:
                    for w in wins:
                        if w["slug"] not in seen_slugs:
                            f.write(json.dumps(w) + "\n")
                            seen_slugs.add(w["slug"])
            except Exception as e:  # noqa: BLE001
                row["note"] = ("ERR " + str(e))[:120]
            finally:
                if os.path.exists(TMP):
                    os.remove(TMP)
        row["seconds"] = round(time.time() - t0, 1)
        rows.append(row)
        with open(CSV_PATH, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: r["hour"]))
        print(row, flush=True)
    day += dt.timedelta(days=1)
