# mpt-data

Monthly data feed for the MPT portfolio simulator: all available months since Jan 2001 (expanding window, minimum 25 years) of monthly **total returns in EUR** for equities, gold, government bonds and EUR cash.

**Fully automatic.** On the 3rd of every month GitHub runs `update_data.py`, which downloads every series from the original source, rebuilds the returns and runs quality checks. Results are committed here only if every check passes; otherwise last month's data stays and GitHub e-mails the repo owner.

| File | What it is |
|---|---|
| `PROBE.md` | One-off check of how far back each source goes (MSCI net returns: Dec 2000 floor) |
| `QUALITY.md` | Human-readable data-quality table, correlations, checks |
| `data/latest.json` | Everything the simulator needs (stats, correlation matrix, monthly series, sources) |
| `data/monthly_returns_eur.csv` | Monthly EUR returns, one column per asset (opens in Excel) |
| `data/monthly_returns_eur_long.csv` | Optional long window from Feb 1991 (7 assets), if its checks passed |
| `data/status.json` | Result of the latest run, pass or fail, with log |
| `raw/` | Unmodified downloads from each source (audit trail) |

## Sources

| Asset | Source |
|---|---|
| US, Europe, EM, World, Germany equities | MSCI end-of-month index levels, net return, EUR |
| Gold | LBMA Gold Price PM in EUR, month-end (fallback: World Bank monthly average) |
| US / German / Czech 10Y government bonds | OECD 10Y yields via FRED → synthetic constant-maturity total return |
| EUR cash | Euro-area call money rate (OECD via FRED), extended with €STR (ECB via FRED) |
| FX (USD, CZK → EUR) | USD: Fed H.10 noon NY (FRED DEXUSEU); CZK: Czech National Bank fixing; month-end |
| Long window before 2001 | Kenneth French market returns (US, Europe, EM); synthetic EUR from CNB D-Mark rates × 1.95583; German call money before 1994. Soft checks: a failure only drops the long window |

To run it by hand: **Actions → Update data → Run workflow**.
