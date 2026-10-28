# Conclusion (Oct 16, 2026): shelve the 1¢ strategy

**Short version:** buying the ~1–2¢ side of Polymarket's "Bitcoin Up or Down" 5-minute markets made money in the
archive only because of one unusual two-week stretch, **April 21 – May 4, 2026**. On every other day from mid-April
to early August it lost money at every realistic order delay. No edge has shown up since early May.

## What was tested
- 2,222 archive hours (Apr 13 – Aug 9, 2026; the archive has almost nothing after that), 26,501 five-minute windows,
  0 errors. Code: `scripts/backtest.py`; pooled results: `results/full/SUMMARY.md`.
- Strategy: when the best ask on a side falls to ≤ P (1¢ or 2¢), buy up to $S ($25 or $100) at ≤ P after a delay of
  L = 0 / 0.25 / 0.5 / 1 / 3 seconds, using a rebuilt order book. Results are reported gross and with Polymarket's
  documented crypto taker fee (shares × 0.07 × p × (1−p)).
- Stability check (this file): `python scripts/stability.py` → `results/STABILITY.txt`.

## The pooled result looked good, but it isn't steady
Pooled over everything, buying at 2¢ with $100 bets after a 0.5 s delay showed **+24% after fees**. Split by month, the
picture is different:

| Month | 2¢, $100, 0.5 s, all trigger times | Same, last 15 s of the window only |
|---|---|---|
| April | +156% | +320% |
| May | +24% | +240% |
| June | −32% | −86% |
| July | −50% | −63% |
| August | −33% | −59% |

Removing April 21 – May 4 turns every realistic setup into a loser:

| Setup (P&L with fee) | Apr 21 – May 4 | All other days |
|---|---|---|
| 2¢, $100, 0.25 s | +901% | −30% |
| 2¢, $100, 0.5 s | +456% | −42% |
| 2¢, $100, 0.5 s, last 15 s | +949% | −62% |
| 2¢, $25, 0.5 s, last 15 s | +840% | −56% |
| 1¢, $100, 0.25 s, last 15 s | +595% | −71% |

Only 1–4 of 16 weeks were profitable for any setup. The 0-second rows ("instant" fills) look great but are not
achievable and are not used for this conclusion.

## What happened in those two weeks
Real trades at ≤1¢ (the "tape", which doesn't depend on the rebuilt book) won far more often than they should have. The
normal rate is about 1.2–1.8%. In the week of Apr 27 it was 16.8%, and on May 2 and May 3 it was over 30%. After May 5
it went back to roughly 1–2% and stayed there through August.

It isn't a labeling error in our data. Polymarket's recorded winners were checked against Binance BTC/USDT 1-minute
prices for 34,007 windows (Binance data lives in a private repo, not here). They agree in 96.3% of windows, and the
mismatches are almost all tiny moves where Polymarket's price source and Binance can differ (1 clear-move mismatch in
total). So during those two weeks Polymarket's 5-minute prices really were badly wrong near the end of windows. The
viral "1¢ wallet" story most likely comes from a short-lived situation like that. **That last point is a guess, not
something this data proves.**

## Caveats
- The fee question is still open (`fee_rate_bps` on trades was 1000 in April and 0 afterward). It doesn't change the
  conclusion: the losing months lose with or without the fee.
- The backtest can't model other traders reacting to our orders. That would only make results worse.
- No data after ~Aug 9, 2026, so current conditions are untested. By then the edge had been gone for about 3 months.

## Decision
Shelved. No paper bot or live trading. Worth revisiting only if Polymarket's 5-minute prices start mispricing again
the way they did in late April. That would show up as cheap-side trades winning far above ~2%.
