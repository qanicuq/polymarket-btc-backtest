"""Favorites backtest, step 2: "buy the obvious side at 70-90c and hold to the end" on resolved Polymarket markets.

Usage: python scripts/favorites_backtest.py      (reads favorites/markets_*.csv, writes favorites/RESULTS.md)
Each bet is $100 bought at the historical price plus a cost (0c, 1c or 2c per share for spread + taker fee).
- Post rule: favorite priced 70-90c, 24 hours before the end. Fixed in advance (from the viral post), not tuned.
- Baseline: buy EVERY side priced 10-90c at the same moment (no skill at all).
- Tuned rule: best price band x entry time picked on TRAIN months only (ended before 2026-07-01), judged on TEST.
Prices come from Polymarket's price-history (not the real ask), so the cost columns stand in for the spread.
"""
import csv
import gzip
import datetime as dt
import glob
import math
import sys

SPLIT = "2026-07"                      # months before this = train, from this on = test
COSTS = [0.0, 0.01, 0.02]
OFFSETS = ["p_1h", "p_24h", "p_7d"]
BANDS = [(0.50, 0.60), (0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 0.95), (0.95, 0.99)]
STAKE = 100.0


def load(pattern="favorites/markets_*.csv.gz"):
    rows = []
    for path in sorted(glob.glob(pattern)):
        with gzip.open(path, "rt") as f:
            rows += [r for r in csv.DictReader(f) if r["note"] == "ok"]
    return rows


def sides(row, key):
    """(price, payout) for both outcomes at this entry time; outcome 1's price is taken as 1 - outcome 0's."""
    if not row.get(key):
        return []
    p0 = float(row[key])
    return [(p0, float(row["pay0"])), (round(1 - p0, 4), float(row["pay1"]))]


def profit(price, pay, cost):
    return STAKE * pay / (price + cost) - STAKE


def month(row):
    return dt.datetime.fromtimestamp(int(row["end"]), dt.timezone.utc).strftime("%Y-%m")


def bets(rows, key, lo, hi, favorite_only=True):
    """List of (month, event, price, pay) for every side whose price is in [lo, hi)."""
    out = []
    for r in rows:
        for price, pay in sides(r, key):
            if lo <= price < hi and (not favorite_only or price > 0.5):
                out.append((month(r), r["event_slug"], price, pay))
    return out


def stats(bl, cost):
    n = len(bl)
    if not n:
        return {"n": 0, "pl": 0.0, "roi": float("nan"), "win": float("nan"), "avg": float("nan")}
    pl = sum(profit(p, pay, cost) for _, _, p, pay in bl)
    return {"n": n, "pl": pl, "roi": pl / (n * STAKE), "win": sum(pay for *_, pay in bl) / n,
            "avg": sum(p for _, _, p, _ in bl) / n}


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def pct(x):
    return "n/a" if x != x else f"{x * 100:+.1f}%"


def monthly_table(bl, title):
    lines = [f"### {title}", "", "| Month | Bets | Win rate | Avg price | P/L gross | P/L 1c cost | P/L 2c cost | ROI 2c |",
             "|---|---|---|---|---|---|---|---|"]
    for m in sorted({b[0] for b in bl}):
        mb = [b for b in bl if b[0] == m]
        s0, s1, s2 = (stats(mb, c) for c in COSTS)
        tag = " (test)" if m >= SPLIT else ""
        lines.append(f"| {m}{tag} | {s0['n']} | {s0['win'] * 100:.1f}% | {s0['avg'] * 100:.1f}c | ${s0['pl']:,.0f} | "
                     f"${s1['pl']:,.0f} | ${s2['pl']:,.0f} | {pct(s2['roi'])} |")
    for label, part in (("TRAIN total", [b for b in bl if b[0] < SPLIT]), ("TEST total", [b for b in bl if b[0] >= SPLIT])):
        s0, s1, s2 = (stats(part, c) for c in COSTS)
        if s0["n"]:
            lines.append(f"| **{label}** | {s0['n']} | {s0['win'] * 100:.1f}% | {s0['avg'] * 100:.1f}c | ${s0['pl']:,.0f} | "
                         f"${s1['pl']:,.0f} | ${s2['pl']:,.0f} | {pct(s2['roi'])} |")
    return lines + [""]


def main():
    rows = load()
    if not rows:
        sys.exit("no data in favorites/")
    months = sorted({month(r) for r in rows})
    out = ["# Favorites backtest: buy the obvious side, hold to the end", "",
           f"Data: {len(rows):,} resolved two-outcome Polymarket markets with >= $10k volume, ended {months[0]} to "
           f"{months[-1]}, from {len({r['event_slug'] for r in rows}):,} events. $100 per bet. "
           f"Train = before {SPLIT}, test = {SPLIT} on. Fees began on most categories in March 2026, so the "
           "2c-cost column is the realistic one for recent months.", ""]

    post = bets(rows, "p_24h", 0.70, 0.90)
    base = bets(rows, "p_24h", 0.10, 0.90, favorite_only=False)
    out += monthly_table(post, "Post rule: favorite at 70-90c, 24 hours before the end")
    out += monthly_table(base, "Baseline: every side priced 10-90c, 24 hours before the end (no skill)")

    out += ["### Is the price honest? (all months, 24h before end, favorites only)", "",
            "| Price band | Bets | Avg price | Actual win rate (95% range) | Edge before costs |", "|---|---|---|---|---|"]
    for lo, hi in BANDS:
        bl = bets(rows, "p_24h", lo, hi)
        s = stats(bl, 0.0)
        if s["n"]:
            a, b = wilson(round(s["win"] * s["n"]), s["n"])
            out.append(f"| {lo * 100:.0f}-{hi * 100:.0f}c | {s['n']} | {s['avg'] * 100:.1f}c | {s['win'] * 100:.1f}% "
                       f"({a * 100:.1f}-{b * 100:.1f}%) | {(s['win'] - s['avg']) * 100:+.1f} pts |")
    out.append("")

    best = None
    out += ["### Tuning on TRAIN months only (ROI with 2c cost; needs >= 200 bets)", "",
            "| Entry | Band | Train bets | Train ROI 2c | Test bets | Test ROI 2c |", "|---|---|---|---|---|---|"]
    for key in OFFSETS:
        for lo, hi in BANDS:
            bl = bets(rows, key, lo, hi)
            tr = stats([b for b in bl if b[0] < SPLIT], 0.02)
            te = stats([b for b in bl if b[0] >= SPLIT], 0.02)
            out.append(f"| {key[2:]} | {lo * 100:.0f}-{hi * 100:.0f}c | {tr['n']} | {pct(tr['roi'])} | {te['n']} | {pct(te['roi'])} |")
            if tr["n"] >= 200 and (best is None or tr["roi"] > best[0]):
                best = (tr["roi"], key, lo, hi)
    out.append("")
    if best:
        _, key, lo, hi = best
        out.append(f"Best on TRAIN: {key[2:]} before end, {lo * 100:.0f}-{hi * 100:.0f}c. Judge it only on the TEST rows below.")
        out.append("")
        out += monthly_table(bets(rows, key, lo, hi), f"Tuned rule: {key[2:]} before end, favorite at {lo * 100:.0f}-{hi * 100:.0f}c")

    p_te = stats([b for b in post if b[0] >= SPLIT], 0.02)
    b_te = stats([b for b in base if b[0] >= SPLIT], 0.02)
    line = (f"TEST ({SPLIT} on), 2c cost: post rule {p_te['n']} bets ROI {pct(p_te['roi'])}; "
            f"baseline {b_te['n']} bets ROI {pct(b_te['roi'])}")
    if best:
        t_te = stats([b for b in bets(rows, best[1], best[2], best[3]) if b[0] >= SPLIT], 0.02)
        line += f"; tuned ({best[1][2:]}, {best[2] * 100:.0f}-{best[3] * 100:.0f}c) ROI {pct(t_te['roi'])}"
    out += ["## Bottom line", "", line, ""]
    with open("favorites/RESULTS.md", "w") as f:
        f.write("\n".join(out))
    print(line)


if __name__ == "__main__":
    main()
