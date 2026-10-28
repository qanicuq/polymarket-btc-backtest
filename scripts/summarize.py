"""Pool hour_*.json files from scripts/backtest.py into SUMMARY.md + pooled.json.

Usage: python scripts/summarize.py OUTDIR
"""
import glob
import json
import math
import os
import sys
from collections import Counter


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 2), round(100 * (c + h), 2)


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def roi(payout, cost):
    return round(100 * (payout / cost - 1), 1) if cost else None


def pool(hours):
    val, tape, grid, fee = Counter(), {}, {}, Counter()
    for h in hours:
        val.update(h.get("validation_sums", {}))
        fee.update(h.get("fee_rate_bps_on_trades", {}))
        for k, v in h.get("tape_sums", {}).items():
            tape.setdefault(k, Counter()).update(v)
        for k, v in h.get("grid_sums", {}).items():
            grid.setdefault(k, Counter()).update(v)
    out = {"hours": len(hours), "hours_with_errors": sum(bool(h.get("errors")) for h in hours),
           "windows_in_file": sum(h.get("windows_in_file", 0) for h in hours), "fee_rate_bps_on_trades": dict(fee)}
    out["validation"] = {
        "snapshot_pairs": val["snap_pairs"],
        "level_agreement_pct_unanchored": pct(val["raw_exact"], val["raw_levels"]),
        "level_agreement_pct_anchored": pct(val["rep_exact"], val["rep_levels"]),
        "phantom_levels_unanchored": val["raw_phantom"], "phantom_levels_anchored": val["rep_phantom"],
        "price_change_events": val["pc_events"], "pct_events_needing_repair": pct(val["pc_repaired"], val["pc_events"]),
        "rows_with_bad_best_ask": val["ba_missing_or_out_of_range"],
        "windows_with_snapshot_before_start": val["windows_with_snapshot_before_start"],
    }
    out["tape"] = {}
    for k, c in sorted(tape.items()):
        lo, hi = wilson(c["wins"], c["pairs"])
        out["tape"][k] = {"trades": c["trades"], "pairs": c["pairs"], "wins": c["wins"],
                          "win_rate_pct": pct(c["wins"], c["pairs"]), "win_rate_95pct_ci": [lo, hi],
                          "cost": round(c["cost"], 2), "payout": round(c["payout"], 2),
                          "roi_gross_pct": roi(c["payout"], c["cost"]),
                          "roi_with_fee_pct": roi(c["payout"], c["cost"] + c["fee_all"]),
                          "pct_shares_in_last_60s": pct(c["shares_last_60s"], c["shares"])}
    out["grid"] = {}
    for k, c in sorted(grid.items()):
        lo, hi = wilson(c["wins"], c["filled"])
        out["grid"][k] = {"entries": c["entries"], "filled": c["filled"], "unknown_size": c["unknown_size"],
                          "no_asks": c["no_asks"], "too_late": c["too_late"], "wins": c["wins"],
                          "win_rate_95pct_ci": [lo, hi], "cost": round(c["cost"], 2),
                          "payout": round(c["payout"], 2), "pnl_gross": round(c["payout"] - c["cost"], 2),
                          "pnl_with_fee": round(c["payout"] - c["cost"] - c["fee"], 2),
                          "roi_gross_pct": roi(c["payout"], c["cost"]),
                          "supported_filled": c["sup_filled"], "supported_wins": c["sup_wins"],
                          "supported_pnl_with_fee": round(c["sup_payout"] - c["sup_cost"] - c["sup_fee"], 2)}
    return out


def main():
    outdir = sys.argv[1]
    hours = []
    for f in sorted(glob.glob(os.path.join(outdir, "hour_*.json"))):
        with open(f) as fh:
            hours.append(json.load(fh))
    p = pool(hours)
    with open(os.path.join(outdir, "pooled.json"), "w") as f:
        json.dump(p, f, indent=1)
    lines = [f"# Results: {outdir}", "", f"Hours: {p['hours']} (with errors: {p['hours_with_errors']}), "
             f"windows in archive: {p['windows_in_file']}", "", "## Per hour", ""]
    for h in hours:
        lines.append(f"- {h['hour']}: windows {h.get('windows_in_file')}, rows {h.get('rows_for_tokens')}, "
                     f"{h.get('seconds_total')} s, {h.get('peak_mem_mb')} MB, errors: {len(h.get('errors', []))}")
    lines += ["", "## Validation", "", "```", json.dumps(p["validation"], indent=1), "```", "",
              "## Tape test (every real trade at <= P inside a window)", "", "```", json.dumps(p["tape"], indent=1),
              "```", "", "## Strategy grid (pooled)", "", "```", json.dumps(p["grid"], indent=1), "```", "",
              f"fee_rate_bps seen on trades: {p['fee_rate_bps_on_trades']}"]
    with open(os.path.join(outdir, "SUMMARY.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    t1 = p["tape"].get("P0.01", {})
    print(f"{p['hours']} hours, {p['windows_in_file']} windows. Tape 1c: {t1.get('pairs')} markets, "
          f"{t1.get('wins')} wins, ROI gross {t1.get('roi_gross_pct')}%. Errors in {p['hours_with_errors']} hours.")


if __name__ == "__main__":
    main()
