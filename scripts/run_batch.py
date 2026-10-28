"""Run scripts/backtest.py over every hour in [START, END] that the coverage scan found BTC 5-minute windows in.

Usage: python scripts/run_batch.py START_DATE END_DATE OUTDIR
- Hours already finished without errors are skipped (backtest.py does this), so re-running resumes.
- Commits + pushes OUTDIR every 20 hours and before the time budget runs out (Actions jobs stop at 6 h).
"""
import csv
import glob
import subprocess
import sys
import time

START, END, OUTDIR = sys.argv[1], sys.argv[2], sys.argv[3]
BUDGET_S = 5 * 3600 + 15 * 60      # stop starting new hours after 5h15m; the job limit is 6 h
t0 = time.time()


def hours_to_run():
    out = []
    for f in sorted(glob.glob("coverage/coverage_*.csv")):
        with open(f, newline="") as fh:
            for r in csv.DictReader(fh):
                day = r["hour"][:10]
                if START <= day <= END and r["file"] == "yes" and r["windows_in_file"] not in ("", "0"):
                    out.append(r["hour"])
    return sorted(set(out))


def push(msg):
    subprocess.run(["git", "add", OUTDIR], check=False)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return
    subprocess.run(["git", "commit", "-q", "-m", msg], check=False)
    for i in range(6):
        if subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"]).returncode == 0 and \
                subprocess.run(["git", "push", "-q"]).returncode == 0:
            return
        time.sleep(10 + 5 * i)
    print("WARNING: push failed; results stay in this job's commit only", flush=True)


hours = hours_to_run()
print(f"{len(hours)} hours with BTC 5-minute windows between {START} and {END}", flush=True)
done = 0
for k, h in enumerate(hours):
    if time.time() - t0 > BUDGET_S:
        print(f"time budget reached after {done} hours; re-run to continue", flush=True)
        break
    try:
        subprocess.run([sys.executable, "scripts/backtest.py", h, OUTDIR], timeout=40 * 60, check=False)
    except subprocess.TimeoutExpired:
        print(f"{h}: hard timeout", flush=True)
    done += 1
    if done % 20 == 0:
        push(f"Full backtest progress {START}..{END}: {done}/{len(hours)} hours")
push(f"Full backtest {START}..{END}: {done}/{len(hours)} hours")
