#!/usr/bin/env python3
"""One-off probe: how far back does each source go? Writes PROBE.md."""
import csv, io, json, datetime as dt
from update_data import http_get, MSCI_URL, CNB_URL

L = ["# History depth probe", "", f"Run {dt.date.today()}", ""]
def row(*c): L.append("| " + " | ".join(str(x) for x in c) + " |")

L += ["## MSCI (requested from 1969-12-31)", "", "| code | variant | ccy | first | last | points |", "|---|---|---|---|---|---|"]
for code in ["990100", "984000", "990500", "928000", "891800"]:
    for var in ["NETR", "GRTR"]:
        for ccy in ["USD", "EUR"]:
            try:
                url = MSCI_URL.format(ccy=ccy, s="19691231", e=dt.date.today().strftime("%Y%m%d"), code=code).replace("NETR", var)
                j = json.loads(http_get(url, tries=2))
                lv = j["indexes"]["INDEX_LEVELS"]
                row(code, var, ccy, lv[0]["calc_date"], lv[-1]["calc_date"], len(lv))
            except Exception as e:
                row(code, var, ccy, "ERR", str(e)[:80], "")
# chunked request to detect a row cap
try:
    url = MSCI_URL.format(ccy="USD", s="19691231", e="19991231", code="990100")
    lv = json.loads(http_get(url, tries=2))["indexes"]["INDEX_LEVELS"]
    L += ["", f"Chunk test 990100 NETR USD 1969-1999: first {lv[0]['calc_date']}, last {lv[-1]['calc_date']}, {len(lv)} points"]
except Exception as e:
    L += ["", f"Chunk test failed: {e}"]

L += ["", "## FRED", "", "| series | first | last | obs |", "|---|---|---|---|"]
for s in ["IRLTLT01CZM156N", "IRLTLT01DEM156N", "IRLTLT01USM156N", "DGS10", "GS10", "IRSTCI01EZM156N",
          "IRSTCI01DEM156N", "IR3TIB01DEM156N", "IR3TIB01CZM156N", "IRSTCI01CZM156N", "DEXUSEU", "DEXGEUS", "EXGEUS",
          "CCUSMA02CZM618N", "ECBESTRVOLWGTTRMDMNRT", "TB3MS"]:
    try:
        rows = [r for r in csv.reader(io.StringIO(http_get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}", tries=2)))][1:]
        rows = [r for r in rows if len(r) > 1 and r[1] not in (".", "")]
        row(s, rows[0][0], rows[-1][0], len(rows))
    except Exception as e:
        row(s, "ERR", str(e)[:80], "")

L += ["", "## CNB fixing", "", "| year | has EUR | has USD | has DEM | has XEU | rows |", "|---|---|---|---|---|---|"]
for y in [1991, 1993, 1995, 1998, 1999]:
    try:
        t = http_get(CNB_URL.format(y=y), tries=2)
        hdr = " ".join(l for l in t.splitlines() if l.startswith("Date"))
        row(y, " EUR" in hdr, " USD" in hdr, " DEM" in hdr, " XEU" in hdr, len(t.splitlines()))
    except Exception as e:
        row(y, "ERR", str(e)[:60], "", "", "")

try:
    g = [r for r in csv.reader(io.StringIO(http_get("https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv")))][1:]
    g = [r for r in g if r[0] >= "1960"]
    L += ["", f"## Gold (World Bank monthly, true monthly data): first {g[0][0]}, last {g[-1][0]}"]
except Exception as e:
    L += ["", f"Gold failed: {e}"]

open("PROBE.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
