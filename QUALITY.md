# Data quality report

Built 2026-10-13 · window 2001-09 – 2026-08 (300 months) · all returns monthly, total return, EUR, unhedged · FX: USD: Fed H.10 noon NY (FRED DEXUSEU), month-end; CZK: Czech National Bank fixing, month-end

| Asset | Months | First | Last | μ (arith.) | σ | CAGR | Max DD | Worst 12m | Default | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| US equities (MSCI USA) | 300 | 2001-09 | 2026-08 | 9.1% | 14.6% | 8.3% | -51.3% | -40.5% | on | MSCI index 984000, net return, EUR (MSCI end-of-month data) |
| European equities (MSCI Europe) | 300 | 2001-09 | 2026-08 | 6.7% | 14.7% | 5.8% | -54.1% | -43.8% | on | MSCI index 990500, net return, EUR (MSCI end-of-month data) |
| Emerging-market equities (MSCI EM) | 300 | 2001-09 | 2026-08 | 10.1% | 18.0% | 8.8% | -56.3% | -50.9% | on | MSCI index 891800, net return, EUR (MSCI end-of-month data) |
| World equities (MSCI World) | 300 | 2001-09 | 2026-08 | 8.1% | 13.7% | 7.4% | -49.0% | -39.4% | optional | MSCI index 990100, net return, EUR (MSCI end-of-month data) |
| German equities (MSCI Germany) | 300 | 2001-09 | 2026-08 | 7.4% | 19.5% | 5.7% | -55.0% | -54.1% | optional | MSCI index 928000, net return, EUR (MSCI end-of-month data) |
| Gold | 300 | 2001-09 | 2026-08 | 11.1% | 13.7% | 10.7% | -34.7% | -30.6% | on | World Bank Pink Sheet, monthly AVERAGE USD price, EUR at month-end FX |
| US Treasury 10Y | 300 | 2001-09 | 2026-08 | 2.7% | 10.1% | 2.2% | -24.1% | -16.3% | on | OECD 10Y govt yield via FRED IRLTLT01USM156N (monthly average); synthetic constant-maturity total return; USD->EUR at month-end FX |
| German Bund 10Y | 300 | 2001-09 | 2026-08 | 2.7% | 5.1% | 2.6% | -26.7% | -20.4% | on | OECD 10Y govt yield via FRED IRLTLT01DEM156N (monthly average); synthetic constant-maturity total return |
| Czech govt 10Y | 300 | 2001-09 | 2026-08 | 5.4% | 7.9% | 5.2% | -24.0% | -20.7% | on | OECD 10Y govt yield via FRED IRLTLT01CZM156N (monthly average); synthetic constant-maturity total return; CZK->EUR at month-end FX |
| EUR cash | 300 | 2001-09 | 2026-08 | 1.3% | 0.5% | 1.3% | -3.0% | -0.6% | on | Euro-area call money rate (OECD via FRED IRSTCI01EZM156N); 2026-02..2026-09 from ESTR (ECB via FRED) |

## Correlation matrix

| | EQ_US | EQ_EU | EQ_EM | EQ_WLD | EQ_DE | GOLD | BD_US10 | BD_DE10 | BD_CZ10 | CASH_EUR |
|---|---|---|---|---|---|---|---|---|---|---|
| EQ_US | 1.00 | 0.79 | 0.66 | 0.97 | 0.74 | -0.08 | 0.10 | -0.05 | 0.06 | -0.16 |
| EQ_EU | 0.79 | 1.00 | 0.75 | 0.90 | 0.93 | -0.21 | -0.22 | -0.12 | 0.21 | -0.11 |
| EQ_EM | 0.66 | 0.75 | 1.00 | 0.75 | 0.72 | -0.04 | -0.13 | -0.04 | 0.19 | -0.04 |
| EQ_WLD | 0.97 | 0.90 | 0.75 | 1.00 | 0.83 | -0.11 | -0.00 | -0.07 | 0.12 | -0.14 |
| EQ_DE | 0.74 | 0.93 | 0.72 | 0.83 | 1.00 | -0.22 | -0.26 | -0.12 | 0.18 | -0.05 |
| GOLD | -0.08 | -0.21 | -0.04 | -0.11 | -0.22 | 1.00 | 0.44 | 0.16 | 0.01 | 0.08 |
| BD_US10 | 0.10 | -0.22 | -0.13 | -0.00 | -0.26 | 0.44 | 1.00 | 0.49 | 0.02 | -0.00 |
| BD_DE10 | -0.05 | -0.12 | -0.04 | -0.07 | -0.12 | 0.16 | 0.49 | 1.00 | 0.42 | 0.11 |
| BD_CZ10 | 0.06 | 0.21 | 0.19 | 0.12 | 0.18 | 0.01 | 0.02 | 0.42 | 1.00 | 0.13 |
| CASH_EUR | -0.16 | -0.11 | -0.04 | -0.14 | -0.05 | 0.08 | -0.00 | 0.11 | 0.13 | 1.00 |

## Near-duplicates (corr > 0.95)

- EQ_US / EQ_WLD: 0.973

## Bias from monthly-average yields (US 10Y test)

- σ with monthly-average yields: 10.1%; with month-end yields: 10.9%
- corr with US equities: 0.10 (avg) vs 0.04 (month-end)

## Checks

- ✅ **FX: Fed EUR/USD vs CNB cross-rate** — max month-end gap 1.67% over 321 months
- ✅ **EQ_US: index code sanity (2008 USD return)** — MSCI 984000 2008 = -37.6%, expected about -37.6%
- ✅ **EQ_US: MSCI EUR vs MSCI USD converted at our FX** — mean abs monthly gap 0.17pp over 309 months
- ✅ **EQ_EU: index code sanity (2008 USD return)** — MSCI 990500 2008 = -46.4%, expected about -46.4%
- ✅ **EQ_EU: MSCI EUR vs MSCI USD converted at our FX** — mean abs monthly gap 0.17pp over 309 months
- ✅ **EQ_EM: index code sanity (2008 USD return)** — MSCI 891800 2008 = -53.3%, expected about -53.3%
- ✅ **EQ_EM: MSCI EUR vs MSCI USD converted at our FX** — mean abs monthly gap 0.17pp over 309 months
- ✅ **EQ_WLD: index code sanity (2008 USD return)** — MSCI 990100 2008 = -40.7%, expected about -40.7%
- ✅ **EQ_WLD: MSCI EUR vs MSCI USD converted at our FX** — mean abs monthly gap 0.17pp over 309 months
- ✅ **EQ_DE: index code sanity (2008 USD return)** — MSCI 928000 2008 = -45.9%, expected about -45.9%
- ✅ **EQ_DE: MSCI EUR vs MSCI USD converted at our FX** — mean abs monthly gap 0.17pp over 309 months
- ⚠️ **GOLD: month-end price available** — no month-end source reachable - fallback uses monthly averages (vol understated)
- ✅ **BD_US10: yields in plausible range** — 320 months, out-of-range: []
- ✅ **BD_DE10: yields in plausible range** — 320 months, out-of-range: []
- ✅ **BD_CZ10: yields in plausible range** — 317 months, out-of-range: []
- ✅ **CASH: call-money vs ESTR overlap** — mean abs gap 0.012pp over 76 months
- ✅ **EQ_US: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **EQ_US: no implausible monthly moves (>35%)** — flagged []
- ✅ **EQ_EU: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **EQ_EU: no implausible monthly moves (>35%)** — flagged []
- ✅ **EQ_EM: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **EQ_EM: no implausible monthly moves (>35%)** — flagged []
- ✅ **EQ_WLD: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **EQ_WLD: no implausible monthly moves (>35%)** — flagged []
- ✅ **EQ_DE: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **EQ_DE: no implausible monthly moves (>35%)** — flagged []
- ✅ **GOLD: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **GOLD: no implausible monthly moves (>25%)** — flagged []
- ✅ **BD_US10: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **BD_US10: no implausible monthly moves (>18%)** — flagged []
- ✅ **BD_DE10: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **BD_DE10: no implausible monthly moves (>18%)** — flagged []
- ✅ **BD_CZ10: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **BD_CZ10: no implausible monthly moves (>18%)** — flagged []
- ✅ **CASH_EUR: full 300-month coverage** — 2001-09..2026-08, missing 0 []
- ✅ **CASH_EUR: no implausible monthly moves (>1%)** — flagged []
- ✅ **window is current** — window ends 2026-08, 2 months before today
