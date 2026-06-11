#!/usr/bin/env python3
"""Rebuild data/state_formation.json from raw BLS QCEW + Census BFS files,
then inject it into index.html.

Usage:
    python3 scripts/refresh_state_data.py            # downloads fresh raw files
    python3 scripts/refresh_state_data.py --offline  # reuse data/*.csv already present

Update QCEW_CUR / QCEW_PREV each quarter and TTM_END after each BFS monthly release.
"""
import csv, json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

QCEW_CUR = ("2025", "4")   # latest QCEW quarter (year, qtr)
QCEW_PREV = ("2024", "4")  # same quarter, prior year
TTM_END = (2026, 5)        # last complete BFS month (year, month)

FILES = {
    f"qcew_722_{QCEW_CUR[0]}q{QCEW_CUR[1]}.csv": f"https://data.bls.gov/cew/data/api/{QCEW_CUR[0]}/{QCEW_CUR[1]}/industry/722.csv",
    f"qcew_722_{QCEW_PREV[0]}q{QCEW_PREV[1]}.csv": f"https://data.bls.gov/cew/data/api/{QCEW_PREV[0]}/{QCEW_PREV[1]}/industry/722.csv",
    "bfs_monthly.csv": "https://www.census.gov/econ/bfs/csv/bfs_monthly.csv",
}

FIPS2ST = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE','11':'DC',
 '12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS','21':'KY','22':'LA',
 '23':'ME','24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE','32':'NV',
 '33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND','39':'OH','40':'OK','41':'OR','42':'PA',
 '44':'RI','45':'SC','46':'SD','47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV',
 '55':'WI','56':'WY'}
MONTHS = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']


def download():
    for name, url in FILES.items():
        print("fetching", url)
        urllib.request.urlretrieve(url, DATA / name)


def load_qcew(fn):
    out = {}
    with open(DATA / fn) as f:
        for r in csv.DictReader(f):
            af = r['area_fips']
            if len(af) == 5 and af.endswith('000') and af[:2].isdigit() \
               and r['own_code'] == '5' and r['industry_code'] == '722':
                out[af[:2]] = int(r['qtrly_estabs'])
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


def ttm(d, endy, endm):
    keys, y, m = [], endy, endm
    for _ in range(12):
        keys.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sum(d[k] for k in keys) if all(k in d for k in keys) else None


def main():
    if "--offline" not in sys.argv:
        download()
    cur = load_qcew(f"qcew_722_{QCEW_CUR[0]}q{QCEW_CUR[1]}.csv")
    prev = load_qcew(f"qcew_722_{QCEW_PREV[0]}q{QCEW_PREV[1]}.csv")
    rows = list(csv.DictReader(open(DATA / "bfs_monthly.csv")))

    us72 = bfs_series(rows, 'US', 'NAICS72')
    us_all = bfs_series(rows, 'US', 'TOTAL')
    n72 = ttm(us72, *TTM_END)
    n72_prev = ttm(us72, TTM_END[0] - 1, TTM_END[1])
    share = n72 / ttm(us_all, *TTM_END)

    states = {}
    for fips, st in FIPS2ST.items():
        d = bfs_series(rows, st, 'TOTAL')
        t, p = ttm(d, *TTM_END), ttm(d, TTM_END[0] - 1, TTM_END[1])
        states[st] = {
            'estabs': cur.get(fips), 'estabsChg': cur.get(fips, 0) - prev.get(fips, 0),
            'estabsPct': round(100 * (cur.get(fips, 0) - prev.get(fips, 0)) / prev.get(fips, 1), 1),
            'appsTTM': t, 'appsTTMPrior': p,
            'appsYoY': round(100 * (t - p) / p, 1) if t and p else None,
            'est72Apps': round(t * share) if t else None,
        }

    us72sa = bfs_series(rows, 'US', 'NAICS72', 'A')
    monthly = [{'date': f'{y}-{m:02d}', 'value': v} for (y, m), v in sorted(us72sa.items()) if y >= 2019]

    out = {
        'asof': f'{TTM_END[0]}-{TTM_END[1]:02d}',
        'naics72_ttm': n72, 'naics72_ttm_prior': n72_prev,
        'naics72_share_of_total': round(share, 4),
        'us_estabs': sum(cur.values()), 'us_estabs_yoy_chg': sum(cur.values()) - sum(prev.values()),
        'states': states, 'naics72_monthly_sa': monthly,
    }
    json.dump(out, open(DATA / "state_formation.json", "w"), indent=1)
    print("wrote data/state_formation.json")

    # inject into index.html (replace previously injected payloads)
    html = (ROOT / "index.html").read_text()
    states_payload = json.dumps({'asof': out['asof'], 'states': states}, separators=(',', ':'))
    bfs_payload = json.dumps(monthly, separators=(',', ':'))
    html = re.sub(r'const STATE_DATA = .*?;\n', f'const STATE_DATA = {states_payload};\n', html, count=1, flags=re.S)
    html = re.sub(r'const BFS_MONTHLY = .*?;\n', f'const BFS_MONTHLY = {bfs_payload};\n', html, count=1, flags=re.S)
    (ROOT / "index.html").write_text(html)
    print("injected into index.html")


if __name__ == "__main__":
    main()
