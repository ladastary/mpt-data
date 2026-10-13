#!/usr/bin/env python3
"""One-off probe: how far back does each source go? Writes PROBE.md."""
import csv, io, json, datetime as dt
from update_data import http_get, MSCI_URL, CNB_URL

L = ["# History depth probe", "", f"Run {dt.date.today()}", ""]
def row(*c): L.append("| " + " | ".join(str(x) for x in c) + " |")

import zipfile, urllib.request
L += ["## Kenneth French data library (monthly market return = Mkt-RF + RF)", "", "| file | first month | last month | months | header |", "|---|---|---|---|---|"]
FR = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
for f in ["F-F_Research_Data_Factors_CSV.zip", "Developed_3_Factors_CSV.zip", "Europe_3_Factors_CSV.zip",
          "Emerging_5_Factors_CSV.zip", "Developed_ex_US_3_Factors_CSV.zip"]:
    try:
        req = urllib.request.Request(FR + f, headers={"User-Agent": "Mozilla/5.0 (compatible; mpt-data/1.0)"})
        raw = urllib.request.urlopen(req, timeout=60).read()
        z = zipfile.ZipFile(io.BytesIO(raw)); txt = z.read(z.namelist()[0]).decode("latin-1")
        months, hdr = [], ""
        for line in txt.splitlines():
            c = [x.strip() for x in line.split(",")]
            if c and c[0] == "" and len(c) > 2 and not hdr: hdr = ",".join(c[1:])
            if c and len(c[0]) == 6 and c[0].isdigit(): months.append(c[0])
            elif months and c and len(c[0]) == 4 and c[0].isdigit(): break  # annual block starts
        row(f, months[0], months[-1], len(months), hdr[:60])
        with open(f"probe_french_{f.split('_')[0]}.csv", "w") as out:
            out.write("month,mkt_usd\n")
            for line in txt.splitlines():
                c = [x.strip() for x in line.split(",")]
                if c and len(c[0]) == 6 and c[0].isdigit():
                    hd = hdr.split(",")
                    out.write(f"{c[0][:4]}-{c[0][4:]},{(float(c[1]) + float(c[1 + hd.index('RF')])) / 100}\n")
                elif c and len(c[0]) == 4 and c[0].isdigit():
                    break
    except Exception as ex:
        row(f, "ERR", str(ex)[:80], "", "")
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
