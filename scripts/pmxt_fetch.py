"""Robust download for PMXT archive files.

Archive downloads sometimes stall part-way (seen: 201 MB in 3 s, then a trickle). This reconnects whenever fewer
than `min_bytes` arrive in `stall_s` seconds and resumes from the current byte with an HTTP Range request. A file
counts as complete only when the byte count matches the size the server reported.
"""
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "polymarket-btc-backtest/1.0 (research; github.com/qanicuq/polymarket-btc-backtest)"}


class NotInArchive(Exception):
    pass


def fetch(url, path, progress=None, limit_s=900, stall_s=30, min_bytes=1 << 20, max_reconnects=25):
    """Returns (bytes, reconnects). Raises NotInArchive on 404, RuntimeError when it cannot finish in time."""
    t0, got, total, reconnects, last_err = time.time(), 0, None, 0, ""
    with open(path, "wb") as f:
        while True:
            if time.time() - t0 > limit_s:
                raise RuntimeError(f"download did not finish: {got} of {total} bytes in {limit_s} s, "
                                   f"{reconnects} reconnects, last error: {last_err}")
            hdr = dict(UA)
            if got:
                hdr["Range"] = f"bytes={got}-"
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=stall_s) as r:
                    if got and r.status != 206:
                        raise RuntimeError("server ignored the Range request; cannot resume safely")
                    if total is None:
                        cr = r.headers.get("Content-Range")
                        total = int(cr.rsplit("/", 1)[1]) if cr else int(r.headers.get("Content-Length") or -1)
                    win_t, win_b = time.time(), 0
                    while True:
                        chunk = r.read(1 << 20)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        win_b += len(chunk)
                        now = time.time()
                        if progress and got % (64 << 20) < len(chunk):
                            progress(stage="downloading", mb=round(got / 1e6), reconnects=reconnects)
                        if now - win_t >= stall_s:
                            if win_b < min_bytes:
                                raise TimeoutError(f"stalled: {win_b} bytes in {round(now - win_t)} s")
                            win_t, win_b = now, 0
                        if now - t0 > limit_s:
                            raise TimeoutError("time limit")
                if total is not None and total >= 0 and got < total:
                    raise TimeoutError(f"connection closed early at {got} of {total} bytes")
                return got, reconnects
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    raise NotInArchive(url) from None
                if e.code == 416 and total is not None and got >= total:
                    return got, reconnects
                last_err = f"HTTP {e.code}"
            except RuntimeError:
                raise
            except Exception as e:  # noqa: BLE001  (timeouts, resets, IncompleteRead, stalls)
                last_err = str(e)[:120]
            reconnects += 1
            if reconnects > max_reconnects:
                raise RuntimeError(f"too many reconnects ({reconnects}); last error: {last_err}")
            time.sleep(min(2 * reconnects, 10))
