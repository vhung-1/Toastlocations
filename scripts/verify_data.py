#!/usr/bin/env python3
"""Independently verify every data-derived number embedded in index.html against
the raw government source files.

It re-computes STATE_DATA, STATE_HIST and BFS_MONTHLY from the BLS QCEW + Census
BFS files and asserts they match the JSON baked into index.html byte-for-byte
(after rounding). Exit code 0 = all match; non-zero = at least one mismatch.

    python3 scripts/verify_data.py            # verify against data/*.csv in repo
    python3 scripts/verify_data.py --download  # re-download raw files first, then verify

This proves the dashboard's state/formation data is exactly what the public
files produce — nothing is hand-entered or invented. (Company KPIs that come
from SEC filings/transcripts are cited in the dashboard's "Sources & Verify"
tab; they are not computable from a CSV and are not checked here.)
"""
import csv, json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
INDEX = ROOT / "index.html"

QCEW_CUR = ("2025", "4")
QCEW_PREV = ("2024", "4")
TTM_END = (2026, 5)
HIST_YEARS = list(range(2015, 2026))

FIPS2ST = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE','11':'DC',
 '12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS','21':'KY','22':'LA',
 '23':'ME','24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV',
 '33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA',
 '44':'RI','45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV',
 '55':'WI','56':'WY'}
MONTHS = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']

SOURCES = {
    f"qcew_722_{QCEW_CUR[0]}q{QCEW_CUR[1]}.csv": f"https://data.bls.gov/cew/data/api/{QCEW_CUR[0]}/{QCEW_CUR[1]}/industry/722.csv",
    f"qcew_722_{QCEW_PREV[0]}q{QCEW_PREV[1]}.csv": f"https://data.bls.gov/cew/data/api/{QCEW_PREV[0]}/{QCEW_PREV[1]}/industry/722.csv",
    "bfs_monthly.csv": "https://www.census.gov/econ/bfs/csv/bfs_monthly.csv",
}
for y in HIST_YEARS:
    SOURCES[f"qcew_722_{y}a.csv"] = f"https://data.bls.gov/cew/data/api/{y}/a/industry/722.csv"


def download():
    for name, url in SOURCES.items():
        print(f"  downloading {name}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (data-verification)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            (DATA / name).write_bytes(r.read())


def qcew_quarterly(fn):
    out = {}
    with open(DATA / fn) as f:
        for r in csv.DictReader(f):
            af = r['area_fips']
            if len(af) == 5 and af.endswith('000') and af[:2] in FIPS2ST and r['own_code'] == '5' and r['industry_code'] == '722':
                out[af[:2]] = int(r['qtrly_estabs'])
    return out


def qcew_annual(y):
    out = {}
    with open(DATA / f"qcew_722_{y}a.csv") as f:
        for r in csv.DictReader(f):
            af = r['area_fips']
            if len(af) == 5 and af.endswith('000') and af[:2] in FIPS2ST and r['own_code'] == '5' and r['industry_code'] == '722':
                out[af[:2]] = int(round(float(r['annual_avg_estabs'])))
    return out


def bfs_series(rows, geo, naics, sa='U'):
    d = {}
    for r in rows:
        if r['geo'] == geo and r['naics_sector'] == naics and r['series'] == 'BA_BA' and r['sa'] == sa:
            y = int(r['year'])
            for i, m in enumerate(MONTHS):
                if r[m].strip():
                    d[(y, i + 1)] = int(r[m])
    return d


def ttm(d, ey, em):
    keys, y, m = [], ey, em
    for _ in range(12):
        keys.append((y, m)); m -= 1
        if m == 0: y, m = y - 1, 12
    return sum(d[k] for k in keys) if all(k in d for k in keys) else None


def embedded(const):
    txt = INDEX.read_text()
    m = re.search(rf'const {const} = (.*?);\n', txt, re.S)
    if not m:
        raise SystemExit(f"could not find {const} in index.html")
    return json.loads(m.group(1))


def main():
    if "--download" in sys.argv:
        print("Re-downloading raw source files from BLS + Census ...")
        download()

    fails = []
    checks = 0

    # ---- STATE_DATA (map tab) ----
    cur, prev = qcew_quarterly(f"qcew_722_{QCEW_CUR[0]}q{QCEW_CUR[1]}.csv"), qcew_quarterly(f"qcew_722_{QCEW_PREV[0]}q{QCEW_PREV[1]}.csv")
    rows = list(csv.DictReader(open(DATA / "bfs_monthly.csv")))
    share = ttm(bfs_series(rows, 'US', 'NAICS72'), *TTM_END) / ttm(bfs_series(rows, 'US', 'TOTAL'), *TTM_END)
    sd = embedded("STATE_DATA")["states"]
    for fips, st in FIPS2ST.items():
        d = bfs_series(rows, st, 'TOTAL')
        t, p = ttm(d, *TTM_END), ttm(d, TTM_END[0] - 1, TTM_END[1])
        exp = {
            'estabs': cur.get(fips), 'estabsChg': cur.get(fips, 0) - prev.get(fips, 0),
            'estabsPct': round(100 * (cur.get(fips, 0) - prev.get(fips, 0)) / prev.get(fips, 1), 1),
            'appsTTM': t, 'appsYoY': round(100 * (t - p) / p, 1) if t and p else None,
            'est72Apps': round(t * share) if t else None,
        }
        for k, v in exp.items():
            checks += 1
            if sd[st].get(k) != v:
                fails.append(f"STATE_DATA[{st}].{k}: embedded={sd[st].get(k)} source={v}")

    # ---- STATE_HIST (10-yr tab) ----
    annual = {y: qcew_annual(y) for y in HIST_YEARS}
    sh = embedded("STATE_HIST")
    us_exp = [sum(annual[y].values()) for y in HIST_YEARS]
    for i, v in enumerate(us_exp):
        checks += 1
        if sh["us_series"][i] != v:
            fails.append(f"STATE_HIST.us_series[{HIST_YEARS[i]}]: embedded={sh['us_series'][i]} source={v}")
    for st_fips, st in FIPS2ST.items():
        series = [annual[y].get(st_fips) for y in HIST_YEARS]
        first, last = series[0], series[-1]
        exp_cum = last - first if first and last else None
        exp_cagr = round((((last / first) ** (1 / (len(HIST_YEARS) - 1))) - 1) * 100, 1) if first and last and first > 0 else None
        e = sh["states"][st]
        for k, v in [("series", series), ("cum10", exp_cum), ("cagr", exp_cagr), ("level25", last)]:
            checks += 1
            if e.get(k) != v:
                fails.append(f"STATE_HIST[{st}].{k}: embedded={e.get(k)} source={v}")

    # ---- BFS_MONTHLY (backdrop tab) ----
    us72sa = bfs_series(rows, 'US', 'NAICS72', 'A')
    exp_monthly = [{'date': f'{y}-{m:02d}', 'value': v} for (y, m), v in sorted(us72sa.items()) if y >= 2019]
    bm = embedded("BFS_MONTHLY")
    checks += 1
    if bm != exp_monthly:
        fails.append(f"BFS_MONTHLY: {len(bm)} embedded points vs {len(exp_monthly)} source points differ")

    print(f"\n{'='*60}")
    print(f"Verified {checks} data points against BLS QCEW + Census BFS source files")
    if fails:
        print(f"❌ {len(fails)} MISMATCH(es):")
        for f in fails[:40]:
            print("   " + f)
        sys.exit(1)
    print("✅ ALL MATCH — every embedded state/formation number reproduces")
    print(f"   exactly from the raw government files. (national 2025 base "
          f"{us_exp[-1]:,}; NAICS-72 share of apps {share*100:.2f}%)")
    print('='*60)


if __name__ == "__main__":
    main()
