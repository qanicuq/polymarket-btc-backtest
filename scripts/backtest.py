"""Backtest one PMXT archive hour: buy the ~1c side of Polymarket BTC 5-minute windows.

Usage: python scripts/backtest.py HOUR OUTDIR        e.g. 2026-04-14T14 results/validate
Writes OUTDIR/hour_HOUR.json (additive sums + any error trace) and OUTDIR/entries_HOUR.csv (one row per simulated
order). Pool hours with scripts/summarize.py.

Per token (each window has an Up and a Down token):
- Rows are ordered by (exchange timestamp, file position). The book is rebuilt from `book` snapshots plus
  `price_change` rows (size = new total at that price; BUY = bids) and then ANCHORED to the exchange's own
  best_bid / best_ask on each row: stale levels beyond them are deleted and a missing best level is added with
  unknown size. Unknown-size levels are never bought from.
- Trigger: first price_change row inside the window whose exchange best_ask <= P.
- Fill: the anchored book AS OF trigger + L seconds (after every row with timestamp <= that time), taking asks <= P
  level by level up to $S. Orders whose fill time is at/after the window end are "too_late".
- Tape test (no book needed): every last_trade_price row inside the window with price <= P is a purchase at that
  price; its payout is $1 per share if that token won.
"""
import bisect
import csv
import datetime as dt
import json
import os
import resource
import sys
import time
import traceback
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

PS = (0.01, 0.02)
SS = (25.0, 100.0)
LS = (0, 0.25, 0.5, 1, 3)   # seconds between seeing the 1c ask and the order reaching the book
FEE_RATE = 0.07          # docs.polymarket.com/trading/fees, Crypto taker: fee = shares x 0.07 x p x (1-p)
SUPPORT_MS = 10_000      # a consumed level is "supported" if a row set its size within the previous 10 s
EPS = 1e-9
UA = {"User-Agent": "polymarket-btc-backtest/1.0 (research; github.com/qanicuq/polymarket-btc-backtest)"}
ENTRY_FIELDS = ["hour", "slug", "outcome", "won", "P", "S", "L", "trig_ms", "sec_into_window", "fill_ms", "status",
                "shares", "cost",
                "fee", "payout", "supported", "unknown_levels", "levels"]


def docs_fee(shares, p):
    return round(shares * FEE_RATE * p * (1 - p), 5)


def snap_compare(mine, snap, v, tag):
    for p, s in snap.items():
        v[tag + "levels"] += 1
        if p not in mine:
            v[tag + "missing"] += 1
        elif mine[p] is not None and abs(mine[p] - s) < 1e-6:
            v[tag + "exact"] += 1
        else:
            v[tag + "sizediff"] += 1
    v[tag + "phantom"] += sum(1 for p in mine if p not in snap)


def _set(d, keys, p, s):
    if p not in d:
        bisect.insort(keys, p)
    d[p] = s


def _del(d, keys, p):
    if p in d:
        del d[p]
        del keys[bisect.bisect_left(keys, p)]


def run_token(r, T, won, deadline=None):
    """r: dict of equal-length lists sorted by (ts, file position): ts, et, side, price, size, bb, ba, bids, asks.
    Returns (validation Counter, list of order cells, {P: tape Counter})."""
    v, cells, tape = Counter(), [], {P: Counter() for P in PS}
    raw_b, raw_a = {}, {}                       # unanchored book (validation only)
    bids, asks, bt, at = {}, {}, {}, {}         # anchored book: price -> size (None = unknown), last-set times
    bk, ak = [], []                             # anchored book prices, kept sorted ascending
    seen, since, started = False, 0, False
    w0, w1 = T * 1000, (T + 300) * 1000
    trig, pend = {}, []                         # pend: sorted (fill_ms, P, L, trig_ms)

    def resolve(fill_ms, P, L, trig_ms):
        levels = [(q, asks[q]) for q in ak[:bisect.bisect_right(ak, P + EPS)]]
        for S in SS:
            spend, sh, cost, fee, unknown, supported, used = S, 0.0, 0.0, 0.0, 0, True, []
            for q, s in levels:
                if s is None:
                    unknown += 1
                    continue
                if spend <= 1e-9:
                    break
                take = min(s, spend / q)
                cost += take * q
                sh += take
                spend -= take * q
                fee += docs_fee(take, q)
                used.append([q, round(take, 4)])
                if fill_ms - at.get(q, -10 ** 18) > SUPPORT_MS:
                    supported = False
            status = "filled" if sh > 1e-9 else ("unknown_size" if unknown else "no_asks")
            cells.append({"P": P, "S": S, "L": L, "trig_ms": trig_ms, "sec_into_window": (trig_ms - w0) / 1000,
                          "fill_ms": fill_ms, "status": status,
                          "shares": round(sh, 4), "cost": round(cost, 4), "fee": round(fee, 5),
                          "payout": round(sh, 4) if (won and status == "filled") else 0.0,
                          "supported": bool(supported and status == "filled"), "unknown_levels": unknown,
                          "levels": used})

    n = len(r["ts"])
    for i in range(n):
        if deadline and i % 100_000 == 0 and time.time() > deadline:
            raise RuntimeError(f"processing time limit hit inside a token at row {i} of {n}")
        t = r["ts"][i]
        while pend and pend[0][0] < t:
            resolve(*pend.pop(0))
        if not started and t >= w0:
            started = True
            v["windows_with_snapshot_before_start"] += seen
        e = r["et"][i]
        if e == "book":
            try:
                nb = {float(p): float(s) for p, s in json.loads(r["bids"][i]) if float(s) > 0}
                na = {float(p): float(s) for p, s in json.loads(r["asks"][i]) if float(s) > 0}
            except Exception:  # noqa: BLE001
                v["bad_book_rows"] += 1
                continue
            if seen and since > 0:
                v["snap_pairs"] += 1
                snap_compare(raw_b, nb, v, "raw_")
                snap_compare(raw_a, na, v, "raw_")
                snap_compare(bids, nb, v, "rep_")
                snap_compare(asks, na, v, "rep_")
            raw_b, raw_a, bids, asks = dict(nb), dict(na), dict(nb), dict(na)
            bk, ak = sorted(bids), sorted(asks)
            bt, at = {p: t for p in bids}, {p: t for p in asks}
            seen, since = True, 0
        elif e == "price_change":
            p, s = r["price"][i], r["size"][i]
            if p is None or s is None:
                v["pc_missing_fields"] += 1
                continue
            since += 1
            v["pc_events"] += 1
            is_bid = r["side"][i] == "BUY"
            rb = raw_b if is_bid else raw_a
            book, keys, tm = (bids, bk, bt) if is_bid else (asks, ak, at)
            if s <= 0:
                rb.pop(p, None)
                _del(book, keys, p)
                tm.pop(p, None)
            else:
                rb[p] = s
                _set(book, keys, p, s)
                tm[p] = t
            fixed = False
            x, y = r["ba"][i], r["bb"][i]
            if x is not None and 0 < x < 1:
                j = bisect.bisect_left(ak, x - EPS)        # asks priced below the exchange's best ask are stale
                if j:
                    for q in ak[:j]:
                        del asks[q]
                        at.pop(q, None)
                    del ak[:j]
                    fixed = True
                if x not in asks:
                    _set(asks, ak, x, None)
                    fixed = True
            else:
                v["ba_missing_or_out_of_range"] += 1
            if y is not None and 0 < y < 1:
                j = bisect.bisect_right(bk, y + EPS)       # bids priced above the exchange's best bid are stale
                if j < len(bk):
                    for q in bk[j:]:
                        del bids[q]
                        bt.pop(q, None)
                    del bk[j:]
                    fixed = True
                if y not in bids:
                    _set(bids, bk, y, None)
                    fixed = True
            v["pc_repaired"] += fixed
            if w0 <= t < w1 and x is not None and 0 < x < 1:
                for P in PS:
                    if P not in trig and x <= P + EPS:
                        trig[P] = t
                        for L in LS:
                            f = t + L * 1000
                            if f >= w1:
                                for S in SS:
                                    cells.append({"P": P, "S": S, "L": L, "trig_ms": t,
                                                  "sec_into_window": (t - w0) / 1000, "fill_ms": f,
                                                  "status": "too_late", "shares": 0.0, "cost": 0.0, "fee": 0.0,
                                                  "payout": 0.0, "supported": False, "unknown_levels": 0,
                                                  "levels": []})
                            else:
                                bisect.insort(pend, (f, P, L, t))
        elif e == "last_trade_price" and w0 <= t < w1:
            p, s = r["price"][i], r["size"][i]
            if p is not None and s is not None and s > 0:
                for P in PS:
                    if p <= P + EPS:
                        c = tape[P]
                        c["trades"] += 1
                        c["shares"] += s
                        c["cost"] += s * p
                        c["fee_all"] += docs_fee(s, p)
                        c["payout"] += s if won else 0.0
                        if t >= w1 - 60_000:
                            c["shares_last_60s"] += s
    for item in pend:
        resolve(*item)
    for P in PS:
        if tape[P]["trades"]:
            tape[P]["pairs"] += 1
            tape[P]["wins"] += 1 if won else 0
    return v, cells, tape


def grid_sums(cells):
    """Additive per-cell sums (ratios are computed after pooling, in summarize.py)."""
    g = {}
    for c in cells:
        k = f"P{c['P']}_S{int(c['S'])}_L{c['L']}"
        sec = c.get("sec_into_window", 0)
        when = "early(<240s)" if sec < 240 else ("late(240-285s)" if sec < 285 else "last15s")
        for a in (g.setdefault(k, Counter()), g.setdefault(k + "|" + when, Counter())):
            _add(a, c)
    return {k: dict(v) for k, v in g.items()}


def _add(a, c):
    a["entries"] += 1
    a[c["status"]] += 1
    if c["status"] == "filled":
        won = c["payout"] > 0
        a["shares"] += c["shares"]
        a["cost"] += c["cost"]
        a["fee"] += c["fee"]
        a["payout"] += c["payout"]
        a["wins"] += won
        if c["supported"]:
            a["sup_filled"] += 1
            a["sup_cost"] += c["cost"]
            a["sup_fee"] += c["fee"]
            a["sup_payout"] += c["payout"]
            a["sup_wins"] += won


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
        return {"slug": slug, "start": ts, "gamma": "ok", "tokens": json.loads(m["clobTokenIds"]),
                "outcomes": json.loads(m["outcomes"]), "outcome_prices": json.loads(m.get("outcomePrices") or "[]"),
                "closed": m.get("closed")}
    except Exception as e:  # noqa: BLE001
        return {"slug": slug, "start": ts, "gamma": "error", "error": str(e)[:120]}


def download(hour, path, progress=None):
    from pmxt_fetch import NotInArchive, fetch      # stall-proof download with byte-range resume
    try:
        n, reconnects = fetch(f"https://r2v2.pmxt.dev/polymarket_orderbook_{hour}.parquet", path, progress)
    except NotInArchive:
        raise RuntimeError(f"no archive file for {hour} (HTTP 404)") from None
    return round(n / 1e6, 1), reconnects


def read_tokens(path, tokens):
    """Read only the needed columns, keep only rows of `tokens`, remember each row's file position."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    need = ["timestamp", "event_type", "asset_id", "price", "size", "side", "best_bid", "best_ask", "bids", "asks",
            "fee_rate_bps"]
    pf = pq.ParquetFile(path)
    missing = [c for c in need if c not in pf.schema_arrow.names]
    if missing:
        raise RuntimeError(f"file is missing columns {missing}")
    tok = pa.array(tokens, type=pa.string())
    parts, offset = [], 0
    for b in pf.iter_batches(batch_size=1_000_000, columns=need):
        m = pc.is_in(b["asset_id"], value_set=tok)
        fb = b.filter(m)
        if fb.num_rows:
            idx = pc.cast(pc.add(pc.indices_nonzero(m), offset), pa.int64())
            parts.append(pa.Table.from_batches([fb]).append_column("idx", idx))
        offset += b.num_rows
    return (pa.concat_tables(parts) if parts else None), offset


def token_rows(tbl, token):
    import pyarrow as pa
    import pyarrow.compute as pc
    t = tbl.filter(pc.equal(tbl["asset_id"], token))
    t = t.append_column("ts", pc.cast(t["timestamp"], pa.int64()))
    t = t.sort_by([("ts", "ascending"), ("idx", "ascending")])

    def fl(name):
        try:
            return pc.cast(t[name], pa.float64()).to_pylist()
        except Exception:  # noqa: BLE001
            return [None if x is None else float(x) for x in t[name].to_pylist()]

    return {"ts": t["ts"].to_pylist(), "et": t["event_type"].to_pylist(), "side": t["side"].to_pylist(),
            "price": fl("price"), "size": fl("size"), "bb": fl("best_bid"), "ba": fl("best_ask"),
            "bids": t["bids"].to_pylist(), "asks": t["asks"].to_pylist(), "fee": t["fee_rate_bps"].to_pylist()}


def main():
    hour, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    tmp = os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), f"bt_{hour}.parquet")
    out = {"hour": hour, "run_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "errors": []}
    entries, t0 = [], time.time()
    prog_path = os.path.join(outdir, f"progress_{hour}.json")
    done_path = os.path.join(outdir, f"hour_{hour}.json")
    if os.path.exists(done_path) and not os.environ.get("FORCE"):      # resume: skip hours already finished
        with open(done_path) as f:
            if not json.load(f).get("errors"):
                print(f"{hour} already done without errors; skipping")
                return

    def progress(**kw):        # survives a killed step: the workflow commits it with `if: always()`
        with open(prog_path, "w") as f:
            json.dump({"hour": hour, "elapsed_s": round(time.time() - t0, 1), **kw}, f)

    deadline = t0 + 35 * 60    # never let one hour stall a batch
    try:
        progress(stage="gamma")
        start = int(dt.datetime.strptime(hour, "%Y-%m-%dT%H").replace(tzinfo=dt.timezone.utc).timestamp())
        with ThreadPoolExecutor(6) as ex:
            wins = list(ex.map(window_info, [start + k * 300 for k in range(12)]))
        usable = []
        for w in wins:
            pr = [str(x) for x in w.get("outcome_prices", [])]
            if w["gamma"] == "ok" and "1" in pr and len(w["tokens"]) == 2:
                w["winner_index"] = pr.index("1")
                usable.append(w)
        out["windows_on_gamma"] = sum(w["gamma"] == "ok" for w in wins)
        out["windows_with_winner"] = len(usable)
        progress(stage="download")
        out["download_mb"], out["download_reconnects"] = download(hour, tmp, progress)
        out["download_seconds"] = round(time.time() - t0, 1)
        progress(stage="reading")
        tbl, out["file_rows"] = read_tokens(tmp, [t for w in usable for t in w["tokens"]])
        out["rows_for_tokens"] = 0 if tbl is None else tbl.num_rows
        out["read_done_seconds"] = round(time.time() - t0, 1)
        val, tape, fee_bps, cells_all = Counter(), {f"P{P}": Counter() for P in PS}, Counter(), []
        windows_in_file = 0
        for w in usable:
            had = False
            for k, (tok, outc) in enumerate(zip(w["tokens"], w["outcomes"])):
                if tbl is None:
                    continue
                if time.time() > deadline:
                    raise RuntimeError(f"processing time limit hit before {w['slug']} {outc}")
                r = token_rows(tbl, tok)
                if not r["ts"]:
                    continue
                had = True
                progress(stage="tokens", slug=w["slug"], outcome=outc, rows=len(r["ts"]))
                fee_bps.update(str(f) for e, f in zip(r["et"], r["fee"]) if e == "last_trade_price")
                won = k == w["winner_index"]
                v, cells, tp = run_token(r, w["start"], won, deadline)
                out.setdefault("token_rows_max", 0)
                out["token_rows_max"] = max(out["token_rows_max"], len(r["ts"]))
                val.update(v)
                for P in PS:
                    tape[f"P{P}"].update(tp[P])
                for c in cells:
                    c.update(hour=hour, slug=w["slug"], outcome=outc, won=won)
                    entries.append(c)
                cells_all.extend(cells)
            windows_in_file += had
        out["windows_in_file"] = windows_in_file
        out["validation_sums"] = dict(val)
        out["tape_sums"] = {k: dict(v) for k, v in tape.items()}
        out["grid_sums"] = grid_sums(cells_all)
        out["fee_rate_bps_on_trades"] = dict(fee_bps)
    except Exception:  # noqa: BLE001
        out["errors"].append(traceback.format_exc()[-2000:])
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if not out["errors"] and os.path.exists(prog_path):
        os.remove(prog_path)
    out["seconds_total"] = round(time.time() - t0, 1)
    out["peak_mem_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    with open(os.path.join(outdir, f"hour_{hour}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    with open(os.path.join(outdir, f"entries_{hour}.csv"), "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=ENTRY_FIELDS)
        wr.writeheader()
        for c in entries:
            wr.writerow({**{k: c.get(k) for k in ENTRY_FIELDS}, "levels": json.dumps(c["levels"])})
    print(json.dumps({k: out.get(k) for k in ("hour", "windows_in_file", "rows_for_tokens", "seconds_total",
                                               "peak_mem_mb", "errors")}, default=str))


if __name__ == "__main__":
    main()
