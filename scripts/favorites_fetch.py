"""Favorites backtest, step 1: collect resolved Polymarket markets for one month and their prices before the end.

Usage: python scripts/favorites_fetch.py YYYY-MM [LIMIT]
Writes favorites/markets_YYYY-MM.csv.gz: one row per resolved two-outcome market (volume >= $10k) scheduled to end that
month, with outcome 0's price 1 hour, 24 hours and 7 days before the SCHEDULED end, and what each outcome paid.
Entry times are measured from the scheduled end (endDate), never from when the market actually closed: deadline
markets close early exactly when the surprise happens, so timing entries off the real close would peek at the result.
A price is left blank if the market was not open yet, or had already closed, at that entry time.
Markets already in the file are skipped, so a re-run resumes. LIMIT (optional) stops after that many markets (probe).
Public data only (Gamma API + CLOB prices-history). No accounts, no keys.
"""
import calendar
import csv
import gzip
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MONTH = sys.argv[1]
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else None
MIN_VOLUME = 10_000           # skip thin markets where a $100 bet could not really be filled
MIN_LIFE_DAYS = 2             # skip short-lived markets (5-min/hourly/daily crypto); they were tested separately
OFFSETS = {"p_1h": 3600, "p_24h": 86400, "p_7d": 7 * 86400}
MAX_GAP = 6 * 3600            # a price point must be within 6 hours before the entry time, else "missing"
UA = {"User-Agent": "polymarket-btc-backtest/1.0 (research; github.com/qanicuq/polymarket-btc-backtest)"}
FIELDS = ["id", "slug", "event_slug", "end", "closed", "start", "volume", "outcome0", "outcome1", "pay0", "pay1",
          "p_1h", "p_24h", "p_7d", "points", "note"]
os.makedirs("favorites", exist_ok=True)
PATH = f"favorites/markets_{MONTH}.csv.gz"


def get_json(url, tries=6):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            retry = not isinstance(e, urllib.error.HTTPError) or e.code in (429, 500, 502, 503, 504)
            if retry and i < tries - 1:
                time.sleep(min(60, 3 * 2 ** i))
                continue
            raise


def ts(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00").replace(" ", "T")
    if "+" not in s[10:] and "-" not in s[10:]:
        s += "+00:00"
    return int(dt.datetime.fromisoformat(s).timestamp())


def list_markets():
    y, m = map(int, MONTH.split("-"))
    lo = f"{MONTH}-01T00:00:00Z"
    hi = f"{MONTH}-{calendar.monthrange(y, m)[1]:02d}T23:59:59Z"
    cursor, out = None, []
    while True:
        q = {"closed": "true", "limit": 100, "volume_num_min": MIN_VOLUME, "end_date_min": lo, "end_date_max": hi}
        if cursor:
            q["after_cursor"] = cursor
        page = get_json("https://gamma-api.polymarket.com/markets/keyset?" + urllib.parse.urlencode(q))
        out += page.get("markets") or []
        cursor = page.get("next_cursor")
        if not cursor or (LIMIT and len(out) >= 5 * LIMIT):
            return out


def price_before(history, t):
    """Last price at or before time t, if it is no older than MAX_GAP; else None."""
    best = None
    for pt in history:
        if pt["t"] <= t and (best is None or pt["t"] > best["t"]):
            best = pt
    return round(float(best["p"]), 4) if best and t - best["t"] <= MAX_GAP else None


def one(m):
    row = {"id": m.get("id"), "slug": m.get("slug"), "volume": round(float(m.get("volumeNum") or 0)),
           "event_slug": ((m.get("events") or [{}])[0] or {}).get("slug", "")}
    try:
        outcomes = json.loads(m.get("outcomes") or "[]")
        pays = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        tokens = json.loads(m.get("clobTokenIds") or "[]")
    except (ValueError, TypeError):
        return {**row, "note": "bad json"}
    if len(outcomes) != 2 or len(pays) != 2 or len(tokens) != 2:
        return {**row, "note": "not two outcomes"}
    if sorted(pays) not in ([0.0, 1.0], [0.5, 0.5]):
        return {**row, "note": f"unresolved {pays}"}
    end = ts(m.get("endDate"))                     # scheduled end; entry times are measured from this
    closed = ts(m.get("closedTime")) or end
    start = ts(m.get("startDate")) or ts(m.get("createdAt"))
    if not end or not start:
        return {**row, "note": "no dates"}
    row.update(end=end, closed=closed, start=start, outcome0=outcomes[0], outcome1=outcomes[1], pay0=pays[0], pay1=pays[1])
    if end - start < MIN_LIFE_DAYS * 86400:
        return {**row, "note": "short-lived"}
    if closed < end - max(OFFSETS.values()):
        return {**row, "note": "closed before every entry time"}
    q = {"market": tokens[0], "startTs": end - 8 * 86400, "endTs": min(end, closed), "fidelity": 60}
    try:
        hist = get_json("https://clob.polymarket.com/prices-history?" + urllib.parse.urlencode(q)).get("history") or []
    except Exception as e:  # noqa: BLE001
        return {**row, "note": f"history error {str(e)[:60]}"}
    row["points"] = len(hist)
    for k, off in OFFSETS.items():
        row[k] = price_before(hist, end - off) if start <= end - off <= closed else None
    row["note"] = "ok" if hist else "no history"
    return row


def main():
    done = set()
    if os.path.exists(PATH):
        with gzip.open(PATH, "rt") as f:
            done = {r["id"] for r in csv.DictReader(f)}
    markets = [m for m in list_markets() if str(m.get("id")) not in done]
    if LIMIT:
        markets = markets[:LIMIT]
    print(f"{MONTH}: {len(markets)} markets to fetch ({len(done)} already done)", flush=True)
    new = not os.path.exists(PATH)
    with gzip.open(PATH, "at", newline="") as f, ThreadPoolExecutor(6) as pool:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        for i, row in enumerate(pool.map(one, markets), 1):
            w.writerow(row)
            if i % 200 == 0:
                f.flush()
                print(f"  {i}/{len(markets)}", flush=True)
    with gzip.open(PATH, "rt") as f:
        rows = list(csv.DictReader(f))
    notes = {}
    for r in rows:
        key = r["note"].split(" ")[0] if r["note"] else "?"
        notes[key] = notes.get(key, 0) + 1
    print(f"{MONTH}: {len(rows)} rows; notes: {notes}")


if __name__ == "__main__":
    main()
