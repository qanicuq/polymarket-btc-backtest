"""Is the edge steady over time? Splits results/full by month, half, and week, and isolates 2026-04-21..05-04.

Usage: python scripts/stability.py [OUTDIR]   (default results/full; reads entries_*.csv and hour_*.json)
P&L "with fee" uses the fee column (docs formula: shares x 0.07 x p x (1-p)).
"""
import collections
import csv
import datetime
import glob
import json
import os
import random
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "results/full"
ODD = ("2026-04-21", "2026-05-04")
CFGS = [(0.02, 100, 0.25, False), (0.02, 100, 0.5, False), (0.02, 100, 0.5, True), (0.02, 25, 0.5, True),
        (0.02, 100, 1, True), (0.01, 100, 0.25, False), (0.01, 100, 0.25, True)]

rows = []   # (day, won, P, S, L, sec_into_window, cost, fee, payout) for filled entries
for f in sorted(glob.glob(os.path.join(OUT, "entries_*.csv"))):
    for r in csv.DictReader(open(f, newline="")):
        if r["status"] == "filled":
            rows.append((r["hour"][:10], r["won"] == "True", float(r["P"]), float(r["S"]), float(r["L"]),
                         float(r["sec_into_window"]), float(r["cost"]), float(r["fee"]), float(r["payout"])))


def line(rs):
    c = sum(r[6] for r in rs)
    if not c:
        return "no fills"
    pnl = sum(r[8] - r[6] - r[7] for r in rs)
    return f"fills {len(rs):6}  wins {sum(r[1] for r in rs):4}  cost ${c:9.0f}  P&L with fee ${pnl:9.0f} ({pnl / c * 100:+.0f}%)"


def week(day):
    d = datetime.date.fromisoformat(day)
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


random.seed(1)
print(f"# Stability check: {OUT}\n")
for P, S, L, last15 in CFGS:
    rs = [r for r in rows if r[2] == P and r[3] == S and r[4] == L and (not last15 or r[5] >= 285)]
    print(f"## {int(P * 100)}c, ${S:.0f}, delay {L}s, {'last 15 s only' if last15 else 'all trigger times'}")
    print(f"- all:         {line(rs)}")
    by_month = collections.defaultdict(list)
    for r in rs:
        by_month[r[0][:7]].append(r)
    for m in sorted(by_month):
        print(f"- {m}:     {line(by_month[m])}")
    days = sorted({r[0] for r in rs})
    mid = days[len(days) // 2]
    print(f"- 1st half:    {line([r for r in rs if r[0] < mid])}")
    print(f"- 2nd half:    {line([r for r in rs if r[0] >= mid])}")
    print(f"- {ODD[0]}..{ODD[1]}: {line([r for r in rs if ODD[0] <= r[0] <= ODD[1]])}")
    print(f"- all other days: {line([r for r in rs if not ODD[0] <= r[0] <= ODD[1]])}")
    wk = collections.defaultdict(float)
    for r in rs:
        wk[week(r[0])] += r[8] - r[6] - r[7]
    print(f"- weeks profitable with fee: {sum(v > 0 for v in wk.values())}/{len(wk)}")
    by_day = collections.defaultdict(lambda: [0.0, 0.0])
    for r in rs:
        by_day[r[0]][0] += r[6]
        by_day[r[0]][1] += r[8] - r[6] - r[7]
    D = list(by_day.values())
    boot = sorted(sum(x[1] for x in s) / sum(x[0] for x in s) * 100
                  for s in ([random.choice(D) for _ in D] for _ in range(2000)))
    print(f"- 95% range of ROI with fee, resampling days: {boot[50]:+.0f}% to {boot[1950]:+.0f}%\n")

print("## Tape (every real trade at <= 1c), win rate by week")
wk = collections.defaultdict(lambda: [0, 0])
for f in glob.glob(os.path.join(OUT, "hour_*.json")):
    d = json.load(open(f))
    t = (d.get("tape_sums") or {}).get("P0.01") or {}
    wk[week(d["hour"][:10])][0] += t.get("pairs", 0)
    wk[week(d["hour"][:10])][1] += t.get("wins", 0)
for k in sorted(wk):
    p, w = wk[k]
    print(f"- week of {k}: {p:5} token-windows, win rate {w / max(1, p) * 100:4.1f}%")
