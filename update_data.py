#!/usr/bin/env python3
"""
MPT data pipeline  -  builds 25 years of monthly EUR total returns for the MPT simulator.

Runs monthly on GitHub Actions (see .github/workflows/update.yml). Plain Python, no packages.
  1. Downloads every source series (FRED, MSCI, Czech National Bank, LBMA).
  2. Saves the raw downloads to raw/ (audit trail).
  3. Builds monthly total returns in EUR, runs quality checks.
  4. Only if every check passes: writes data/latest.json, data/monthly_returns_eur.csv, QUALITY.md.
     If a check fails: keeps last month's data, writes data/status.json, and the run fails
     (GitHub then e-mails the repo owner).
"""
import csv, io, json, math, os, sys, time, zipfile, datetime as dt, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw")
OUT = os.path.join(ROOT, "data")
MIN_MONTHS = 300                         # expanding window: all months every asset has, at least 25 years
FETCH_FROM = dt.date(2000, 1, 1)         # a little history before the window
LONG_FROM = dt.date(1990, 12, 1)         # optional long window (v0.3): Kenneth French splice before 2001
LONG_MIN_START = "1992-01"               # long window must start by this month
DEM_PER_EUR = 1.95583                    # irrevocable conversion rate, 31 Dec 1998
TODAY = dt.date.today()
CURRENT_MONTH = TODAY.strftime("%Y-%m")  # incomplete month, always excluded
UA = "Mozilla/5.0 (compatible; mpt-data/1.0; +https://github.com/ladastary/mpt-data)"

LOG, CHECKS = [], []


def log(msg):
    print(msg, flush=True)
    LOG.append(msg)


def check(name, ok, detail, hard=True):
    CHECKS.append({"check": name, "ok": bool(ok), "hard": hard, "detail": detail})
    log(f"[{'PASS' if ok else ('FAIL' if hard else 'WARN')}] {name}: {detail}")


# ---------------------------------------------------------------- helpers
def http_get(url, tries=4, timeout=90, headers=None):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:  # noqa
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"download failed: {url} ({last})")


def http_get_bytes(url, tries=4, timeout=90):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa
            last = e
            time.sleep(4 * (i + 1))
    raise RuntimeError(f"download failed: {url} ({last})")


def mkey(d):  # date or 'YYYY-MM-DD' -> 'YYYY-MM'
    return d.strftime("%Y-%m") if isinstance(d, dt.date) else d[:7]


def month_add(m, k):
    y, mo = int(m[:4]), int(m[5:7])
    t = y * 12 + (mo - 1) + k
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def months_between(a, b):  # inclusive list a..b
    out, m = [], a
    while m <= b:
        out.append(m)
        m = month_add(m, 1)
    return out


def month_end(daily):  # {date: v} -> {'YYYY-MM': last value in month}
    out = {}
    for d in sorted(daily):
        out[mkey(d)] = daily[d]
    return out


def month_mean(daily):
    acc = {}
    for d, v in daily.items():
        acc.setdefault(mkey(d), []).append(v)
    return {m: sum(v) / len(v) for m, v in acc.items()}


def complete_only(series):  # drop the running month
    return {m: v for m, v in series.items() if m < CURRENT_MONTH}


def save_raw(name, series, header=("date", "value")):
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(RAW, f"{name}.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for k in sorted(series):
            w.writerow([k if isinstance(k, str) else k.isoformat(), repr(series[k])])


def level_returns(levels):  # {'YYYY-MM': level} -> {'YYYY-MM': return}
    ks = sorted(levels)
    out = {}
    for a, b in zip(ks, ks[1:]):
        if month_add(a, 1) == b:
            out[b] = levels[b] / levels[a] - 1
    return out


def corr(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else 0.0


def stdev(x):
    m = sum(x) / len(x)
    return math.sqrt(sum((a - m) ** 2 for a in x) / (len(x) - 1))


# ---------------------------------------------------------------- sources
def fred(series_id, since=None, tag=""):
    """FRED public CSV. Returns {date: value} from `since` (default FETCH_FROM)."""
    since = since or FETCH_FROM
    txt = http_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}")
    rows = list(csv.reader(io.StringIO(txt)))
    out = {}
    for r in rows[1:]:
        if len(r) < 2 or r[1].strip() in (".", ""):
            continue
        d = dt.date.fromisoformat(r[0].strip())
        if d >= since:
            out[d] = float(r[1])
    if not out:
        raise RuntimeError(f"FRED {series_id}: no data")
    save_raw(f"fred_{series_id}{tag}", out)
    return out


CNB_URL = ("https://www.cnb.cz/en/financial-markets/foreign-exchange-market/"
           "central-bank-exchange-rate-fixing/central-bank-exchange-rate-fixing/year.txt?year={y}")


def cnb_fx():
    """Czech National Bank daily fixing. Returns ({date: CZK per EUR}, {date: CZK per USD})."""
    eur, usd = {}, {}
    for y in range(FETCH_FROM.year, TODAY.year + 1):
        hdr = None
        for line in http_get(CNB_URL.format(y=y)).splitlines():
            parts = line.strip().split("|")
            if not parts or not parts[0]:
                continue
            if parts[0] == "Date":
                hdr = parts
                continue
            d = dt.datetime.strptime(parts[0], "%d.%m.%Y").date()
            for col, val in zip(hdr[1:], parts[1:]):
                amt, code = col.split(" ")
                if code in ("EUR", "USD") and val.strip():
                    rate = float(val.replace(",", ".")) / float(amt)
                    (eur if code == "EUR" else usd)[d] = rate
    save_raw("cnb_CZK_per_EUR_daily", eur)
    save_raw("cnb_CZK_per_USD_daily", usd)
    return eur, usd


MSCI_URL = ("https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph"
            "?currency_symbol={ccy}&index_variant=NETR&start_date={s}&end_date={e}"
            "&data_frequency=END_OF_MONTH&index_codes={code}")


def msci(code, ccy):
    """MSCI end-of-month net-return index levels. Returns {'YYYY-MM': level}."""
    url = MSCI_URL.format(ccy=ccy, s=(FETCH_FROM - dt.timedelta(days=1)).strftime("%Y%m%d"),
                          e=TODAY.strftime("%Y%m%d"), code=code)
    j = json.loads(http_get(url))
    got_code = str(j.get("msci_index_code", ""))
    got_ccy = j.get("ISO_currency_symbol", "")
    got_var = j.get("index_variant_type", "")
    if got_code != code or got_ccy != ccy or got_var != "NETR":
        raise RuntimeError(f"MSCI returned {got_code}/{got_ccy}/{got_var}, asked {code}/{ccy}/NETR")
    out = {}
    for x in j["indexes"]["INDEX_LEVELS"]:
        c = str(x["calc_date"])
        out[f"{c[:4]}-{c[4:6]}"] = float(x["level_eod"])
    out = complete_only(out)
    save_raw(f"msci_{code}_{ccy}_NETR_monthly", out)
    return out


def gold_lbma():
    """LBMA Gold Price PM, daily, EUR (column 3). Returns ({'YYYY-MM': EUR month-end}, note)."""
    j = json.loads(http_get("https://prices.lbma.org.uk/json/gold_pm.json", tries=2, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/126.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
        "Origin": "https://www.lbma.org.uk"}))
    daily = {}
    for row in j:
        d = dt.date.fromisoformat(row["d"])
        v = row["v"]
        if d >= FETCH_FROM and len(v) >= 3 and v[2]:
            daily[d] = float(v[2])
    save_raw("lbma_gold_pm_EUR_daily", daily)
    return complete_only(month_end(daily))


def gold_bundesbank():
    """Deutsche Bundesbank time-series API: daily London gold fixing in USD (dataflow BBEX3).
    Discovers the available XAU/USD series, logs them, prefers the afternoon (PM) fixing.
    Returns {'YYYY-MM': USD month-end}."""
    rows, errs = [], []
    for key in ("D.XAU.USD.EA.AC.C05", "D.XAU.USD.EA.AC.", "D.XAU.....", "D..XAU...."):
        url = (f"https://api.statistiken.bundesbank.de/rest/data/BBEX3/{key}?"
               "format=sdmx_csv&startPeriod=2000-01-01")
        try:
            rows = list(csv.DictReader(io.StringIO(http_get(url, tries=1))))
            if rows:
                log(f"Bundesbank key {key}: {len(rows)} rows")
                break
        except Exception as e:
            errs.append(f"{key}: {e}")
    if not rows:
        raise RuntimeError("Bundesbank: no matching series; " + " | ".join(errs))
    cols = list(rows[0].keys())
    log(f"Bundesbank columns: {cols}")
    key_cols = [c for c in cols if c not in ("TIME_PERIOD", "OBS_VALUE") and c.upper() == c
                and not c.startswith(("BBK_OBS", "OBS_", "DATAFLOW"))]
    series = {}
    for r in rows:
        k = ".".join(r.get(c, "") for c in key_cols)
        v = (r.get("OBS_VALUE") or "").strip()
        if v and v not in (".", "NaN"):
            series.setdefault(k, {})[dt.date.fromisoformat(r["TIME_PERIOD"][:10])] = float(v)
    for k, s in series.items():
        log(f"Bundesbank series {k}: {len(s)} obs, {min(s)}..{max(s)}, last {s[max(s)]}")
    pm = [k for k in series if "C05" in k] or sorted(series, key=lambda k: -len(series[k]))
    k = pm[0]
    s = series[k]
    if min(s) > dt.date(2001, 1, 31) or (TODAY - max(s)).days > 45:
        raise RuntimeError(f"Bundesbank series {k} does not cover the window")
    save_raw(f"bundesbank_gold_USD_daily_{k.replace('.', '_')}", s)
    return complete_only(month_end(s)), k


def gold_worldbank(usd_per_eur_me):
    """Fallback: World Bank Pink Sheet monthly AVERAGE (USD) via datasets/gold-prices."""
    txt = http_get("https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv")
    usd = {}
    for r in list(csv.reader(io.StringIO(txt)))[1:]:
        if r and r[0] >= LONG_FROM.strftime("%Y-%m"):
            usd[r[0][:7]] = float(r[1])
    save_raw("worldbank_gold_USD_monthly_avg", usd)
    return complete_only({m: v / usd_per_eur_me[m] for m, v in usd.items() if m in usd_per_eur_me})


def worldbank_gold_usd():
    """World Bank Pink Sheet monthly AVERAGE gold price in USD, from LONG_FROM. Returns {'YYYY-MM': USD}."""
    txt = http_get("https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv")
    out = {r[0][:7]: float(r[1]) for r in list(csv.reader(io.StringIO(txt)))[1:] if r and r[0] >= LONG_FROM.strftime("%Y-%m")}
    return complete_only(out)


FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{f}"


def french_market(fname):
    """Kenneth French data library: monthly market total return in USD = (Mkt-RF + RF) / 100.
    Returns {'YYYY-MM': return}. Reads only the first (monthly) block of the CSV inside the zip."""
    z = zipfile.ZipFile(io.BytesIO(http_get_bytes(FRENCH.format(f=fname))))
    txt = z.read(z.namelist()[0]).decode("latin-1")
    hdr, out = None, {}
    for line in txt.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if hdr is None:
            if "Mkt-RF" in parts:
                hdr = parts
            continue
        if not parts[0] or not parts[0].isdigit() or len(parts[0]) != 6:
            if out:
                break
            continue
        m = f"{parts[0][:4]}-{parts[0][4:]}"
        out[m] = (float(parts[hdr.index("Mkt-RF")]) + float(parts[hdr.index("RF")])) / 100
    if not out:
        raise RuntimeError(f"French {fname}: no monthly rows parsed")
    save_raw(f"french_{fname.replace('_CSV.zip', '')}_market_USD", out)
    return complete_only(out)


def cnb_usd_dem(y0=1991, y1=2001):
    """Czech National Bank daily fixing 1991-2001: month-end USD per DEM (cross via CZK)."""
    usd, dem = {}, {}
    for y in range(y0, y1 + 1):
        hdr = None
        for line in http_get(CNB_URL.format(y=y)).splitlines():
            parts = line.strip().split("|")
            if not parts or not parts[0]:
                continue
            if parts[0] == "Date":
                hdr = parts
                continue
            if hdr is None:
                continue
            d = dt.datetime.strptime(parts[0], "%d.%m.%Y").date()
            for col, val in zip(hdr[1:], parts[1:]):
                bits = col.split(" ")
                if len(bits) != 2 or bits[1] not in ("USD", "DEM") or not val.strip():
                    continue
                rate = float(val.replace(",", ".")) / float(bits[0])
                (usd if bits[1] == "USD" else dem)[d] = rate
    usd_me, dem_me = complete_only(month_end(usd)), complete_only(month_end(dem))
    out = {m: dem_me[m] / usd_me[m] for m in dem_me if m in usd_me}
    save_raw("cnb_USD_per_DEM_monthend_1991_2001", out)
    return out


# ---------------------------------------------------------------- transforms
def bond_tr(y_prev, y_now, maturity=10.0):
    """Synthetic constant-maturity return: buy 10Y par bond (coupon = y_prev) at t-1,
    reprice as (10Y - 1M) bond at y_now, add one month of coupon. Annual coupons."""
    c, y, n = y_prev / 100.0, y_now / 100.0, maturity - 1.0 / 12.0
    if abs(y) < 1e-9:
        price = c * n + 1.0
    else:
        price = c * (1 - (1 + y) ** -n) / y + (1 + y) ** -n
    return price - 1.0 + c / 12.0


def bond_returns(yields):
    ks = sorted(yields)
    return {b: bond_tr(yields[a], yields[b]) for a, b in zip(ks, ks[1:]) if month_add(a, 1) == b}


def to_eur(local_ret, eur_per_ccy):
    """(1 + r_local) * FX_t / FX_{t-1} - 1, FX in EUR per unit of local currency."""
    out = {}
    for m, r in local_ret.items():
        p = month_add(m, -1)
        if m in eur_per_ccy and p in eur_per_ccy:
            out[m] = (1 + r) * eur_per_ccy[m] / eur_per_ccy[p] - 1
    return out


# ---------------------------------------------------------------- statistics
def stats(rets):
    n = len(rets)
    mu = sum(rets) / n
    sd = stdev(rets)
    wealth, peak, mdd, path = 1.0, 1.0, 0.0, [1.0]
    for r in rets:
        wealth *= 1 + r
        path.append(wealth)
        peak = max(peak, wealth)
        mdd = min(mdd, wealth / peak - 1)
    worst12 = min(path[i + 12] / path[i] - 1 for i in range(len(path) - 12))
    return {
        "expRet": mu * 12, "vol": sd * math.sqrt(12),
        "cagr": wealth ** (12 / n) - 1, "maxDD": mdd, "worst12m": worst12,
    }


# ---------------------------------------------------------------- universe
ASSETS = [
    # id, name, class, source kind, code, UCITS proxy, default on
    dict(id="EQ_US", name="US equities (MSCI USA)", cls="EQ", kind="msci", code="984000",
         proxy="CSPX / SXR8 (S&P 500)", defaultOn=True, usd2008=-0.376),
    dict(id="EQ_EU", name="European equities (MSCI Europe)", cls="EQ", kind="msci", code="990500",
         proxy="EXSA (STOXX Europe 600) / IMEU (MSCI Europe)", defaultOn=True, usd2008=-0.464),
    dict(id="EQ_EM", name="Emerging-market equities (MSCI EM)", cls="EQ", kind="msci", code="891800",
         proxy="EIMI", defaultOn=True, usd2008=-0.533),
    dict(id="EQ_WLD", name="World equities (MSCI World)", cls="EQ", kind="msci", code="990100",
         proxy="EUNL", defaultOn=False, usd2008=-0.407),
    dict(id="EQ_DE", name="German equities (MSCI Germany)", cls="EQ", kind="msci", code="928000",
         proxy="EXS1 (DAX)", defaultOn=False, usd2008=-0.459),
    dict(id="GOLD", name="Gold", cls="CM", kind="gold", proxy="4GLD (Xetra-Gold)", defaultOn=True),
    dict(id="BD_US10", name="US Treasury 10Y", cls="BD", kind="bond", code="IRLTLT01USM156N",
         ccy="USD", proxy="US Treasury 7-10Y UCITS ETF", defaultOn=True),
    dict(id="BD_DE10", name="German Bund 10Y", cls="BD", kind="bond", code="IRLTLT01DEM156N",
         ccy="EUR", proxy="German govt bond UCITS ETF", defaultOn=True),
    dict(id="BD_CZ10", name="Czech govt 10Y", cls="BD", kind="bond", code="IRLTLT01CZM156N",
         ccy="CZK", proxy="Direct CZ government bonds", defaultOn=True),
    dict(id="CASH_EUR", name="EUR cash", cls="CA", kind="cash", proxy="EUR overnight-rate ETF",
         defaultOn=True),
]
CLASSES = [
    {"id": "EQ", "name": "Equities"}, {"id": "BD", "name": "Bonds"},
    {"id": "CM", "name": "Commodities"}, {"id": "CA", "name": "Cash"},
]
MAX_ABS_MONTHLY = {"EQ": 0.35, "CM": 0.25, "BD": 0.18, "CA": 0.01}


def build():
    ret, meta = {}, {}

    # FX. CZK: Czech National Bank fixing (14:30 Prague). USD: Fed H.10 noon New York (FRED DEXUSEU),
    # chosen because it sits within ~0.2pp/month of the WM/Reuters 4pm London rate MSCI uses, so all
    # USD assets share the equities' fixing time. CNB EUR/USD is the cross-check and the fallback.
    czk_eur, czk_usd = cnb_fx()
    czk_eur_me, czk_usd_me = complete_only(month_end(czk_eur)), complete_only(month_end(czk_usd))
    usd_per_eur_cnb = {m: czk_eur_me[m] / czk_usd_me[m] for m in czk_eur_me if m in czk_usd_me}
    try:
        usd_per_eur = complete_only(month_end(fred("DEXUSEU")))
        fx_src = "USD: Fed H.10 noon NY (FRED DEXUSEU), month-end; CZK: Czech National Bank fixing, month-end"
        common = [m for m in usd_per_eur if m in usd_per_eur_cnb]
        dev = max(abs(usd_per_eur[m] / usd_per_eur_cnb[m] - 1) for m in common)
        check("FX: Fed EUR/USD vs CNB cross-rate", dev < 0.025, f"max month-end gap {dev:.2%} over {len(common)} months")
    except Exception as e:
        usd_per_eur = usd_per_eur_cnb
        fx_src = "USD and CZK: Czech National Bank fixing, month-end (Fed rate unavailable)"
        check("FX: Fed EUR/USD available", False, f"fell back to CNB: {e}", hard=False)
    eur_per = {"EUR": None,
               "USD": {m: 1 / v for m, v in usd_per_eur.items()},
               "CZK": {m: 1 / v for m, v in czk_eur_me.items()}}
    save_raw("fx_USD_per_EUR_monthend_used", usd_per_eur)
    meta["_fx"] = fx_src
    meta["_usd_per_eur"] = usd_per_eur

    # Equities: MSCI net return, native EUR series; USD series used for checks
    for a in [x for x in ASSETS if x["kind"] == "msci"]:
        lv_eur, lv_usd = msci(a["code"], "EUR"), msci(a["code"], "USD")
        r_eur, r_usd = level_returns(lv_eur), level_returns(lv_usd)
        ret[a["id"]] = r_eur
        y08 = lv_usd["2008-12"] / lv_usd["2007-12"] - 1
        check(f"{a['id']}: index code sanity (2008 USD return)", abs(y08 - a["usd2008"]) < 0.06,
              f"MSCI {a['code']} 2008 = {y08:.1%}, expected about {a['usd2008']:.1%}")
        conv = to_eur(r_usd, eur_per["USD"])
        common = sorted(set(conv) & set(r_eur))
        gap = sum(abs(conv[m] - r_eur[m]) for m in common) / len(common)
        check(f"{a['id']}: MSCI EUR vs MSCI USD converted at our FX", gap < 0.004,
              f"mean abs monthly gap {gap * 100:.2f}pp over {len(common)} months")
        meta[a["id"]] = dict(source=f"MSCI index {a['code']}, net return, EUR (MSCI end-of-month data)",
                             seriesType="index")

    # Gold: 1) LBMA PM in EUR, month-end  2) Bundesbank London fixing USD, month-end -> EUR
    #       3) World Bank monthly AVERAGE (vol understated)
    try:
        ret["GOLD"] = level_returns(gold_lbma())
        meta["GOLD"] = dict(source="LBMA Gold Price PM, EUR, month-end", seriesType="spot-price")
    except Exception as e1:
        log(f"LBMA gold unavailable: {e1}")
        try:
            g_usd, key = gold_bundesbank()
            ret["GOLD"] = to_eur(level_returns(g_usd), eur_per["USD"])
            meta["GOLD"] = dict(source=f"London gold fixing USD via Deutsche Bundesbank ({key}), month-end; "
                                       f"EUR at month-end FX", seriesType="spot-price")
        except Exception as e2:
            log(f"Bundesbank gold unavailable: {e2}")
            g = gold_worldbank(usd_per_eur)
            ret["GOLD"] = level_returns(g)
            meta["GOLD"] = dict(source="World Bank Pink Sheet, monthly AVERAGE USD price, EUR at month-end FX",
                                seriesType="spot-price (monthly average)")
            check("GOLD: month-end price available", False,
                  "no month-end source reachable - fallback uses monthly averages (vol understated)", hard=False)

    # Bonds: synthetic constant-maturity 10Y total return from OECD monthly yields (FRED)
    for a in [x for x in ASSETS if x["kind"] == "bond"]:
        y = complete_only({mkey(d): v for d, v in fred(a["code"]).items()})
        bad = [m for m, v in y.items() if not -1.5 < v < 20]
        check(f"{a['id']}: yields in plausible range", not bad, f"{len(y)} months, out-of-range: {bad[:5]}")
        local = bond_returns(y)
        ret[a["id"]] = local if a["ccy"] == "EUR" else to_eur(local, eur_per[a["ccy"]])
        meta[a["id"]] = dict(
            source=f"OECD 10Y govt yield via FRED {a['code']} (monthly average); synthetic constant-maturity "
                   f"total return" + ("" if a["ccy"] == "EUR" else f"; {a['ccy']}->EUR at month-end FX"),
            seriesType="synthetic-from-yield")

    # Cash: euro-area call money rate (EONIA proxy, OECD via FRED), extended with ESTR (ECB via FRED)
    call = complete_only({mkey(d): v for d, v in fred("IRSTCI01EZM156N").items()})
    estr = complete_only(month_mean(fred("ECBESTRVOLWGTTRMDMNRT")))
    overlap = [m for m in estr if m in call]
    if overlap:
        gap = sum(abs(call[m] - estr[m]) for m in overlap) / len(overlap)
        check("CASH: call-money vs ESTR overlap", gap < 0.25, f"mean abs gap {gap:.3f}pp over {len(overlap)} months")
    rate = dict(call)
    added = [m for m in sorted(estr) if m not in rate]
    for m in added:
        rate[m] = estr[m]
    ret["CASH_EUR"] = {m: v / 100 / 12 for m, v in rate.items()}
    meta["CASH_EUR"] = dict(
        source="Euro-area call money rate (OECD via FRED IRSTCI01EZM156N)"
               + (f"; {added[0]}..{added[-1]} from ESTR (ECB via FRED)" if added else ""),
        seriesType="short-rate")

    # US bond bias check: month-end daily yield vs monthly-average yield
    try:
        d10 = complete_only(month_end(fred("DGS10")))
        alt = to_eur(bond_returns(d10), eur_per["USD"])
        meta["_us_bond_bias"] = alt
    except Exception as e:
        log(f"DGS10 bias check skipped: {e}")

    return ret, meta


# ---------------------------------------------------------------- optional long window (v0.3)
LONG_ASSETS = {  # id -> how the pre-2001 part is built
    "EQ_US": dict(kind="french", file="F-F_Research_Data_Factors_CSV.zip", label="Kenneth French US market (CRSP)"),
    "EQ_EU": dict(kind="french", file="Europe_3_Factors_CSV.zip", label="Kenneth French Europe market"),
    "EQ_EM": dict(kind="french", file="Emerging_5_Factors_CSV.zip", label="Kenneth French Emerging market"),
    "GOLD": dict(kind="gold"),
    "BD_US10": dict(kind="bond", code="IRLTLT01USM156N", ccy="USD"),
    "BD_DE10": dict(kind="bond", code="IRLTLT01DEM156N", ccy="EUR"),
    "CASH_EUR": dict(kind="cash"),
}


def build_long(ret, meta, dates):
    """Monthly EUR returns from ~Feb 1991: main series from the main window start, spliced with
    pre-2001 constructions. Any failure here only drops the long window (soft checks)."""
    start_main = dates[0]
    fx_main = meta["_usd_per_eur"]
    lc = []                                       # long-window checks, added to CHECKS as soft

    def lcheck(name, ok, detail):
        lc.append((name, ok))
        check("LONG " + name, ok, detail, hard=False)

    # Synthetic EUR before 1999: USD per DEM (CNB cross) x 1.95583; Fed rate from 1999
    usd_dem = cnb_usd_dem()
    synth = {m: v * DEM_PER_EUR for m, v in usd_dem.items()}
    ov = [m for m in synth if m >= "1999-01" and m in fx_main]
    dev = max(abs(synth[m] / fx_main[m] - 1) for m in ov) if ov else 1
    lcheck("synthetic EUR/USD (CNB D-Mark x 1.95583) vs Fed, overlap", dev < 0.025, f"max gap {dev:.2%} over {len(ov)} months")
    usd_per_eur = {m: v for m, v in synth.items() if m not in fx_main}   # synthetic where the main FX series has no month
    usd_per_eur.update(fx_main)
    eur_per_usd = {m: 1 / v for m, v in usd_per_eur.items()}

    pre, src, splice = {}, {}, {}
    for aid, spec in LONG_ASSETS.items():
        if spec["kind"] == "french":
            usd = french_market(spec["file"])
            eur = to_eur(usd, eur_per_usd)
            common = [m for m in dates if m in eur]
            x, y = [eur[m] for m in common], [ret[aid][m] for m in common]
            c = corr(x, y) if len(common) > 24 else 0
            te = stdev([a - b for a, b in zip(x, y)]) * math.sqrt(12) if len(common) > 24 else 1
            gap = (sum(x) - sum(y)) / len(common) * 12 if common else 0
            splice[aid] = {"corr": round(c, 4), "te": round(te, 4), "meanGap": round(gap, 4), "months": len(common)}
            lcheck(f"{aid}: French vs MSCI overlap", c > 0.98 and te < 0.04,
                   f"corr {c:.3f}, tracking error {te:.1%} p.a., mean gap {gap * 100:+.2f}pp p.a. over {len(common)} months")
            pre[aid] = eur
            src[aid] = f"{spec['label']}, Mkt-RF + RF, USD -> EUR (synthetic EUR before 1999), before {start_main}; MSCI from {start_main}"
        elif spec["kind"] == "gold":
            g = worldbank_gold_usd()
            lv = {m: v / usd_per_eur[m] for m, v in g.items() if m in usd_per_eur}
            pre[aid] = level_returns(lv)
            src[aid] = f"World Bank monthly average USD price -> EUR before {start_main}; main gold series from {start_main}"
        elif spec["kind"] == "bond":
            y = complete_only({mkey(d): v for d, v in fred(spec["code"], since=LONG_FROM, tag="_long").items()})
            local = bond_returns(y)
            pre[aid] = local if spec["ccy"] == "EUR" else to_eur(local, eur_per_usd)
            src[aid] = f"OECD 10Y yield via FRED {spec['code']}, synthetic constant-maturity" + (", USD -> EUR" if spec["ccy"] != "EUR" else ", DEM = EUR / 1.95583")
        elif spec["kind"] == "cash":
            de = complete_only({mkey(d): v for d, v in fred("IRSTCI01DEM156N", since=LONG_FROM, tag="_long").items()})
            ez = complete_only({mkey(d): v for d, v in fred("IRSTCI01EZM156N", since=LONG_FROM, tag="_long").items()})
            rate = {m: v for m, v in de.items() if m < "1994-01"}
            rate.update({m: v for m, v in ez.items() if m >= "1994-01"})
            pre[aid] = {m: v / 100 / 12 for m, v in rate.items()}
            src[aid] = "German call money (FRED IRSTCI01DEM156N) before 1994, euro-area call money from 1994; main cash series from " + start_main

    series = {}
    for aid in LONG_ASSETS:
        s = {m: v for m, v in pre[aid].items() if m < start_main}
        s.update({m: ret[aid][m] for m in dates})
        series[aid] = s
    first = max(min(s) for s in series.values())
    ldates = months_between(first, dates[-1])
    for aid, s in series.items():
        miss = [m for m in ldates if m not in s]
        lim = MAX_ABS_MONTHLY[next(a["cls"] for a in ASSETS if a["id"] == aid)]
        big = [(m, round(s[m], 4)) for m in ldates if m in s and abs(s[m]) > lim]
        lcheck(f"{aid}: no gaps or implausible moves", not miss and not big, f"{first}..{dates[-1]}, missing {miss[:3]}, flagged {big[:3]}")
    lcheck("long window start", first <= LONG_MIN_START, f"starts {first} (must start by {LONG_MIN_START}), {len(ldates)} months")
    if not all(ok for _, ok in lc):
        log("Long window dropped: at least one long-window check failed.")
        return None
    return {
        "window": {"start": first, "end": dates[-1], "months": len(ldates)},
        "assets": list(LONG_ASSETS), "sources": src, "splice": splice,
        "fx": "USD before " + min(fx_main) + ": synthetic EUR = USD per DEM (Czech National Bank cross-rate, month-end) x 1.95583; from then as the main window",
        "dates": ldates,
        "returns": {aid: [round(series[aid][m], 8) for m in ldates] for aid in LONG_ASSETS},
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(RAW, exist_ok=True)
    for f in os.listdir(RAW):  # raw/ always mirrors the latest run only
        os.remove(os.path.join(RAW, f))
    retrieved = TODAY.isoformat()
    try:
        ret, meta = build()
    except Exception as e:
        check("download", False, str(e))
        ret, meta = None, None

    result = None
    if ret:
        ids = [a["id"] for a in ASSETS]
        end = min(max(ret[i]) for i in ids)      # last month every asset has
        start = max(min(ret[i]) for i in ids)    # first month every asset has (MSCI net: Jan 2001)
        start_by = {i: min(ret[i]) for i in ids}
        log(f"First available month per asset: {start_by}")
        check("window length", len(months_between(start, end)) >= MIN_MONTHS,
              f"{start}..{end} = {len(months_between(start, end))} months (minimum {MIN_MONTHS})")
        dates = months_between(start, end)
        for a in ASSETS:
            missing = [m for m in dates if m not in ret[a["id"]]]
            check(f"{a['id']}: no gaps in window", not missing,
                  f"{start}..{end}, missing {len(missing)} {missing[:3]}")
            lim = MAX_ABS_MONTHLY[a["cls"]]
            big = [(m, round(ret[a["id"]][m], 4)) for m in dates if m in ret[a["id"]] and abs(ret[a["id"]][m]) > lim]
            check(f"{a['id']}: no implausible monthly moves (>{lim:.0%})", not big, f"flagged {big[:3]}")
        lag = (TODAY.year * 12 + TODAY.month) - (int(end[:4]) * 12 + int(end[5:]))
        check("window is current", lag <= 3, f"window ends {end}, {lag} months before today", hard=False)

        if all(c["ok"] for c in CHECKS if c["hard"]):
            series = {a["id"]: [ret[a["id"]][m] for m in dates] for a in ASSETS}
            assets_out = []
            for a in ASSETS:
                s = stats(series[a["id"]])
                assets_out.append({
                    "id": a["id"], "name": a["name"], "class": a["cls"], "proxy": a["proxy"],
                    **{k: round(v, 6) for k, v in s.items()},
                    "income": None, "ter": 0.0, "min": 0, "max": 1, "defaultOn": a["defaultOn"],
                    "source": meta[a["id"]]["source"], "seriesType": meta[a["id"]]["seriesType"],
                    "window": {"start": start, "end": end, "months": len(dates)}, "retrieved": retrieved,
                })
            order = [a["id"] for a in ASSETS]
            matrix = [[round(corr(series[i], series[j]), 6) for j in order] for i in order]
            dups = [(order[i], order[j], matrix[i][j]) for i in range(len(order))
                    for j in range(i + 1, len(order)) if matrix[i][j] > 0.95]
            bias = None
            if "_us_bond_bias" in meta and all(m in meta["_us_bond_bias"] for m in dates):
                alt = [meta["_us_bond_bias"][m] for m in dates]
                bias = {
                    "vol_monthlyAvgYield": round(stdev(series["BD_US10"]) * math.sqrt(12), 6),
                    "vol_monthEndYield": round(stdev(alt) * math.sqrt(12), 6),
                    "corrWithEQ_US_monthlyAvgYield": round(corr(series["BD_US10"], series["EQ_US"]), 4),
                    "corrWithEQ_US_monthEndYield": round(corr(alt, series["EQ_US"]), 4),
                }
            result = {
                "settings": {"baseCurrency": "EUR", "riskFree": None, "riskFreeSource": "CASH_EUR historical mean",
                             "returnBasis": "nominal", "fx": meta["_fx"],
                             "window": {"start": start, "end": end, "months": len(dates)},
                             "built": retrieved},
                "classes": CLASSES,
                "assets": assets_out,
                "correlation": {"order": order, "matrix": matrix},
                "nearDuplicates": [{"a": a, "b": b, "corr": round(c, 4)} for a, b, c in dups],
                "usBondYieldBias": bias,
                "monthly": {"dates": dates, "returns": {k: [round(x, 8) for x in v] for k, v in series.items()}},
                "checks": CHECKS,
            }
            try:
                long = build_long(ret, meta, dates)
            except Exception as e:  # the long window is optional and must never block the main data
                check("LONG window built", False, f"skipped: {e}", hard=False)
                long = None
            if long:
                result["long"] = long
                with open(os.path.join(OUT, "monthly_returns_eur_long.csv"), "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["month"] + long["assets"])
                    for k, m in enumerate(long["dates"]):
                        w.writerow([m] + [f"{long['returns'][i][k]:.8f}" for i in long["assets"]])
            result["checks"] = CHECKS
            with open(os.path.join(OUT, "latest.json"), "w") as f:
                json.dump(result, f, separators=(",", ":"))
            with open(os.path.join(OUT, "monthly_returns_eur.csv"), "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["month"] + order)
                for k, m in enumerate(dates):
                    w.writerow([m] + [f"{series[i][k]:.8f}" for i in order])
            write_quality(result)

    ok = result is not None
    with open(os.path.join(OUT, "status.json"), "w") as f:
        json.dump({"run": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", "ok": ok,
                   "published": ok, "checks": CHECKS, "log": LOG[-200:]}, f, indent=1)
    if not ok:
        log("Quality checks failed - previous data/latest.json kept unchanged.")
        sys.exit(1)


def pct(x, d=1):
    return "–" if x is None else f"{x * 100:.{d}f}%"


def write_quality(r):
    w = r["settings"]["window"]
    L = [f"# Data quality report", "",
         f"Built {r['settings']['built']} · window {w['start']} – {w['end']} ({w['months']} months) · "
         f"all returns monthly, total return, EUR, unhedged · FX: {r['settings']['fx']}", "",
         "| Asset | Months | First | Last | μ (arith.) | σ | CAGR | Max DD | Worst 12m | Default | Source |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in r["assets"]:
        L.append(f"| {a['name']} | {a['window']['months']} | {a['window']['start']} | {a['window']['end']} | "
                 f"{pct(a['expRet'])} | {pct(a['vol'])} | {pct(a['cagr'])} | {pct(a['maxDD'])} | "
                 f"{pct(a['worst12m'])} | {'on' if a['defaultOn'] else 'optional'} | {a['source']} |")
    L += ["", "## Correlation matrix", "", "| | " + " | ".join(r["correlation"]["order"]) + " |",
          "|---" * (len(r["correlation"]["order"]) + 1) + "|"]
    for i, row in zip(r["correlation"]["order"], r["correlation"]["matrix"]):
        L.append(f"| {i} | " + " | ".join(f"{c:.2f}" for c in row) + " |")
    L += ["", "## Near-duplicates (corr > 0.95)", ""]
    L += [f"- {d['a']} / {d['b']}: {d['corr']:.3f}" for d in r["nearDuplicates"]] or ["- none"]
    b = r["usBondYieldBias"]
    if b:
        L += ["", "## Bias from monthly-average yields (US 10Y test)", "",
              f"- σ with monthly-average yields: {pct(b['vol_monthlyAvgYield'])}; with month-end yields: "
              f"{pct(b['vol_monthEndYield'])}",
              f"- corr with US equities: {b['corrWithEQ_US_monthlyAvgYield']:.2f} (avg) vs "
              f"{b['corrWithEQ_US_monthEndYield']:.2f} (month-end)"]
    lg = r.get("long")
    if lg:
        L += ["", f"## Optional long window {lg['window']['start']} – {lg['window']['end']} ({lg['window']['months']} months)", "",
              "| Asset | μ (arith.) | σ | Source before the main window |", "|---|---|---|---|"]
        for aid in lg["assets"]:
            x = lg["returns"][aid]
            L.append(f"| {aid} | {pct(sum(x) / len(x) * 12)} | {pct(stdev(x) * math.sqrt(12))} | {lg['sources'][aid]} |")
        L += ["", "Splice diagnostics (French vs MSCI, EUR, over the main window): " +
              "; ".join(f"{k} corr {v['corr']:.3f}, TE {pct(v['te'])}, mean gap {v['meanGap'] * 100:+.2f}pp" for k, v in lg["splice"].items())]
    L += ["", "## Checks", ""]
    L += [f"- {'✅' if c['ok'] else ('❌' if c['hard'] else '⚠️')} **{c['check']}** — {c['detail']}" for c in r["checks"]]
    with open(os.path.join(ROOT, "QUALITY.md"), "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
