# Results: results/validation

Hours: 8 (with errors: 1), windows in archive: 84

## Per hour

- 2026-04-14T14: windows 12, rows 4593079, 29.9 s, 2236.4 MB, errors: 0
- 2026-04-26T14: windows 12, rows 2624590, 22.8 s, 1863.5 MB, errors: 0
- 2026-05-08T14: windows 12, rows 3207241, 17.3 s, 1931.3 MB, errors: 0
- 2026-05-29T14: windows 12, rows 3048241, 47.9 s, 2256.9 MB, errors: 0
- 2026-06-07T14: windows None, rows None, 930.7 s, 32.8 MB, errors: 1
- 2026-07-19T14: windows 12, rows 2971433, 70.2 s, 2029.1 MB, errors: 0
- 2026-07-31T14: windows 12, rows 5258550, 52.5 s, 2778.6 MB, errors: 0
- 2026-08-09T14: windows 12, rows 1908124, 25.4 s, 1964.9 MB, errors: 0

## Validation

```
{
 "snapshot_pairs": 269152,
 "level_agreement_pct_unanchored": 94.1,
 "level_agreement_pct_anchored": 94.1,
 "phantom_levels_unanchored": 1397493,
 "phantom_levels_anchored": 1409638,
 "price_change_events": 23061402,
 "pct_events_needing_repair": 0.8,
 "rows_with_bad_best_ask": 460109,
 "windows_with_snapshot_before_start": 101
}
```

## Tape test (every real trade at <= P inside a window)

```
{
 "P0.01": {
  "trades": 2468,
  "pairs": 85,
  "wins": 3,
  "win_rate_pct": 3.5,
  "win_rate_95pct_ci": [
   1.21,
   9.87
  ],
  "cost": 5034.75,
  "payout": 10445.34,
  "roi_gross_pct": 107.5,
  "roi_with_fee_pct": 94.0,
  "pct_shares_in_last_60s": 72.4
 },
 "P0.02": {
  "trades": 4082,
  "pairs": 86,
  "wins": 3,
  "win_rate_pct": 3.5,
  "win_rate_95pct_ci": [
   1.19,
   9.76
  ],
  "cost": 8184.04,
  "payout": 18600.1,
  "roi_gross_pct": 127.3,
  "roi_with_fee_pct": 112.6,
  "pct_shares_in_last_60s": 66.4
 }
}
```

## Strategy grid (pooled)

```
{
 "P0.01_S100_L0": {
  "entries": 85,
  "filled": 84,
  "unknown_size": 0,
  "no_asks": 1,
  "too_late": 0,
  "wins": 2,
  "win_rate_95pct_ci": [
   0.66,
   8.27
  ],
  "cost": 1001.15,
  "payout": 4176.49,
  "pnl_gross": 3175.34,
  "pnl_with_fee": 3105.96,
  "roi_gross_pct": 317.2,
  "supported_filled": 84,
  "supported_wins": 2,
  "supported_pnl_with_fee": 3105.96
 },
 "P0.01_S100_L1": {
  "entries": 85,
  "filled": 72,
  "unknown_size": 0,
  "no_asks": 8,
  "too_late": 5,
  "wins": 0,
  "win_rate_95pct_ci": [
   0.0,
   5.07
  ],
  "cost": 3720.02,
  "payout": 0.0,
  "pnl_gross": -3720.02,
  "pnl_with_fee": -3977.82,
  "roi_gross_pct": -100.0,
  "supported_filled": 72,
  "supported_wins": 0,
  "supported_pnl_with_fee": -3977.82
 },
 "P0.01_S100_L3": {
  "entries": 85,
  "filled": 64,
  "unknown_size": 0,
  "no_asks": 13,
  "too_late": 8,
  "wins": 0,
  "win_rate_95pct_ci": [
   0.0,
   5.66
  ],
  "cost": 3738.0,
  "payout": 0.0,
  "pnl_gross": -3738.0,
  "pnl_with_fee": -3997.05,
  "roi_gross_pct": -100.0,
  "supported_filled": 64,
  "supported_wins": 0,
  "supported_pnl_with_fee": -3997.05
 },
 "P0.01_S25_L0": {
  "entries": 85,
  "filled": 84,
  "unknown_size": 0,
  "no_asks": 1,
  "too_late": 0,
  "wins": 2,
  "win_rate_95pct_ci": [
   0.66,
   8.27
  ],
  "cost": 735.51,
  "payout": 2507.12,
  "pnl_gross": 1771.61,
  "pnl_with_fee": 1720.64,
  "roi_gross_pct": 240.9,
  "supported_filled": 84,
  "supported_wins": 2,
  "supported_pnl_with_fee": 1720.64
 },
 "P0.01_S25_L1": {
  "entries": 85,
  "filled": 72,
  "unknown_size": 0,
  "no_asks": 8,
  "too_late": 5,
  "wins": 0,
  "win_rate_95pct_ci": [
   0.0,
   5.07
  ],
  "cost": 1470.38,
  "payout": 0.0,
  "pnl_gross": -1470.38,
  "pnl_with_fee": -1572.28,
  "roi_gross_pct": -100.0,
  "supported_filled": 72,
  "supported_wins": 0,
  "supported_pnl_with_fee": -1572.28
 },
 "P0.01_S25_L3": {
  "entries": 85,
  "filled": 64,
  "unknown_size": 0,
  "no_asks": 13,
  "too_late": 8,
  "wins": 0,
  "win_rate_95pct_ci": [
   0.0,
   5.66
  ],
  "cost": 1315.17,
  "payout": 0.0,
  "pnl_gross": -1315.17,
  "pnl_with_fee": -1406.31,
  "roi_gross_pct": -100.0,
  "supported_filled": 64,
  "supported_wins": 0,
  "supported_pnl_with_fee": -1406.31
 },
 "P0.02_S100_L0": {
  "entries": 86,
  "filled": 85,
  "unknown_size": 0,
  "no_asks": 1,
  "too_late": 0,
  "wins": 3,
  "win_rate_95pct_ci": [
   1.21,
   9.87
  ],
  "cost": 393.52,
  "payout": 4398.17,
  "pnl_gross": 4004.65,
  "pnl_with_fee": 3977.54,
  "roi_gross_pct": 1017.7,
  "supported_filled": 85,
  "supported_wins": 3,
  "supported_pnl_with_fee": 3977.54
 },
 "P0.02_S100_L1": {
  "entries": 86,
  "filled": 74,
  "unknown_size": 0,
  "no_asks": 9,
  "too_late": 3,
  "wins": 1,
  "win_rate_95pct_ci": [
   0.24,
   7.27
  ],
  "cost": 1365.55,
  "payout": 2122.42,
  "pnl_gross": 756.87,
  "pnl_with_fee": 663.07,
  "roi_gross_pct": 55.4,
  "supported_filled": 74,
  "supported_wins": 1,
  "supported_pnl_with_fee": 663.07
 },
 "P0.02_S100_L3": {
  "entries": 86,
  "filled": 66,
  "unknown_size": 0,
  "no_asks": 16,
  "too_late": 4,
  "wins": 1,
  "win_rate_95pct_ci": [
   0.27,
   8.1
  ],
  "cost": 2191.22,
  "payout": 1975.94,
  "pnl_gross": -215.28,
  "pnl_with_fee": -366.35,
  "roi_gross_pct": -9.8,
  "supported_filled": 66,
  "supported_wins": 1,
  "supported_pnl_with_fee": -366.35
 },
 "P0.02_S25_L0": {
  "entries": 86,
  "filled": 85,
  "unknown_size": 0,
  "no_asks": 1,
  "too_late": 0,
  "wins": 3,
  "win_rate_95pct_ci": [
   1.21,
   9.87
  ],
  "cost": 279.41,
  "payout": 2728.8,
  "pnl_gross": 2449.39,
  "pnl_with_fee": 2430.17,
  "roi_gross_pct": 876.6,
  "supported_filled": 85,
  "supported_wins": 3,
  "supported_pnl_with_fee": 2430.17
 },
 "P0.02_S25_L1": {
  "entries": 86,
  "filled": 74,
  "unknown_size": 0,
  "no_asks": 9,
  "too_late": 3,
  "wins": 1,
  "win_rate_95pct_ci": [
   0.24,
   7.27
  ],
  "cost": 991.33,
  "payout": 1250.0,
  "pnl_gross": 258.67,
  "pnl_with_fee": 190.61,
  "roi_gross_pct": 26.1,
  "supported_filled": 74,
  "supported_wins": 1,
  "supported_pnl_with_fee": 190.61
 },
 "P0.02_S25_L3": {
  "entries": 86,
  "filled": 66,
  "unknown_size": 0,
  "no_asks": 16,
  "too_late": 4,
  "wins": 1,
  "win_rate_95pct_ci": [
   0.27,
   8.1
  ],
  "cost": 1143.13,
  "payout": 1250.0,
  "pnl_gross": 106.87,
  "pnl_with_fee": 28.21,
  "roi_gross_pct": 9.3,
  "supported_filled": 66,
  "supported_wins": 1,
  "supported_pnl_with_fee": 28.21
 }
}
```

fee_rate_bps seen on trades: {'1000': 107775, '0': 172302}
