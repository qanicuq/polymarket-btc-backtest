"""Where did one public Polymarket trader's profit come from? Public data-api only.

Usage: python scripts/trader_profile.py WALLET     (writes trader/REPORT.md and trader/closed_positions.csv.gz)
- Every closed position (realized P/L per market), split by buy price, Yes/No, and month.
- Every activity type (trades, redeems, merges, splits, conversions, rewards, rebates), with counts and dollars.
"""
import collections
import csv
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

WALLET = sys.argv[1]
API = "https://data-api.polymarket.com"
UA = {"User-Agent": "polymarket-btc-backtest/1.0 (research; github.com/qanicuq/polymarket-btc-backtest)"}
os.makedirs("trader", exist_ok=True)


def get_json(path, q, tries=6):
    url = f"{API}/{path}?" + urllib.parse.urlencode(q)
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            if isinstance(e, urllib.error.HTTPError) and e.code == 400:
                return None                                 # past the paging limit
            if i < tries - 1:
                time.sleep(min(60, 3 * 2 ** i))
                continue
            raise


def closed_positions():
    out, offset = [], 0
    while True:
        page = get_json("closed-positions", {"user": WALLET, "limit": 50, "offset": offset,
                                             "sortBy": "TIMESTAMP", "sortDirection": "ASC"})
        if not page:
            return out
        out += page
        offset += len(page)


def activity_window(kind, start, end):
    """All activity of one type in [start, end); splits the window in half if it hits the paging cap (offset 5000)."""
    rows, offset = [], 0
    while True:
        page = get_json("activity", {"user": WALLET, "type": kind, "limit": 500, "offset": offset,
                                     "start": start, "end": end - 1, "sortBy": "TIMESTAMP", "sortDirection": "ASC",
                                     "excludeDepositsWithdrawals": "false"})
        if page is None:                                   # paging cap hit: split the window
            if end - start <= 60:
                print(f"  cap hit in a 1-minute window for {kind} at {start}; some rows may be missing", flush=True)
                return rows
            mid = (start + end) // 2
            return activity_window(kind, start, mid) + activity_window(kind, mid, end)
        rows += page
        if len(page) < 500:
            return rows
        offset += 500


def band(p):
    for lo, hi in ((0, .05), (.05, .2), (.2, .5), (.5, .7), (.7, .9), (.9, .97), (.97, 1.01)):
        if lo <= p < hi:
            return f"{lo * 100:.0f}-{min(hi, 1) * 100:.0f}c"
    return "?"


def main():
    cps = closed_positions()
    print(f"closed positions: {len(cps)}", flush=True)
    with gzip.open("trader/closed_positions.csv.gz", "wt", newline="") as f:
        keys = ["timestamp", "endDate", "eventSlug", "slug", "outcome", "avgPrice", "totalBought", "realizedPnl", "curPrice"]
        w = csv.DictWriter(f, keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(cps)

    start = int(dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc).timestamp())   # profile says joined May 2026
    now = int(time.time()) + 3600
    acts = {}
    for kind in ["DEPOSIT", "WITHDRAWAL", "TRADE", "REDEEM", "MERGE", "SPLIT", "CONVERSION", "REWARD", "MAKER_REBATE",
                 "TAKER_REBATE", "REFERRAL_REWARD", "YIELD"]:
        acts[kind] = activity_window(kind, start, now)
        print(f"{kind}: {len(acts[kind])}", flush=True)

    total = sum(c["realizedPnl"] for c in cps)
    out = [f"# Where the profit came from: {WALLET}", "",
           f"Closed positions: {len(cps):,} in {len({c['eventSlug'] for c in cps}):,} events. "
           f"Total realized P/L on them: ${total:,.0f}.", ""]

    out += ["## Activity by type", "", "| Type | Count | Dollars |", "|---|---|---|"]
    for kind, rows in acts.items():
        if kind == "TRADE":
            for side in ("BUY", "SELL"):
                r = [x for x in rows if x.get("side") == side]
                out.append(f"| TRADE {side} | {len(r):,} | ${sum(float(x.get('usdcSize') or 0) for x in r):,.0f} |")
        else:
            out.append(f"| {kind} | {len(rows):,} | ${sum(float(x.get('usdcSize') or 0) for x in rows):,.0f} |")
    out.append("")

    trades = acts["TRADE"]
    if trades:
        sizes = sorted(float(x.get("usdcSize") or 0) for x in trades)
        days = (trades[-1]["timestamp"] - trades[0]["timestamp"]) / 86400 or 1
        gaps = sorted(b["timestamp"] - a["timestamp"] for a, b in zip(trades, trades[1:]))
        out += ["## Trading style", "",
                f"- {len(trades):,} trades over {days:.0f} days = {len(trades) / days:,.0f} per day.",
                f"- Typical (median) trade: ${sizes[len(sizes) // 2]:,.2f}; 90th percentile: ${sizes[int(len(sizes) * .9)]:,.2f}.",
                f"- Median time between trades: {gaps[len(gaps) // 2] if gaps else 0} seconds.",
                f"- Buy prices: " + ", ".join(f"{k} {v:,}" for k, v in sorted(collections.Counter(
                    band(float(x['price'])) for x in trades if x.get('side') == 'BUY').items())), ""]

    def table(title, keyf):
        groups = collections.defaultdict(list)
        for c in cps:
            groups[keyf(c)].append(c)
        lines = [f"## {title}", "", "| Group | Positions | Won (P/L > 0) | Realized P/L | Share of total |", "|---|---|---|---|---|"]
        for k in sorted(groups):
            g = groups[k]
            pl = sum(c["realizedPnl"] for c in g)
            lines.append(f"| {k} | {len(g):,} | {sum(c['realizedPnl'] > 0 for c in g) / len(g) * 100:.0f}% | ${pl:,.0f} | "
                         f"{pl / total * 100 if total else 0:.0f}% |")
        return lines + [""]

    out += table("By average buy price", lambda c: band(c["avgPrice"]))
    out += table("By side bought", lambda c: c["outcome"] if c["outcome"] in ("Yes", "No") else "named outcome")
    out += table("By month closed", lambda c: dt.datetime.fromtimestamp(c["timestamp"], dt.timezone.utc).strftime("%Y-%m"))

    top = sorted(cps, key=lambda c: -c["realizedPnl"])
    out += ["## Concentration", "",
            f"- Top 10 positions: ${sum(c['realizedPnl'] for c in top[:10]):,.0f}. Top 100: ${sum(c['realizedPnl'] for c in top[:100]):,.0f}.",
            f"- All losing positions together: ${sum(c['realizedPnl'] for c in cps if c['realizedPnl'] < 0):,.0f}.", ""]
    with open("trader/REPORT.md", "w") as f:
        f.write("\n".join(out))
    print(f"total realized {total:,.0f} over {len(cps)} closed positions")


if __name__ == "__main__":
    main()
