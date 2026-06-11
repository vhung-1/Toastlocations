# Toast (TOST) Location Adds Dashboard

A self-contained, single-page dashboard for analyzing **Toast's net location adds** from a long/short equity perspective. Open `index.html` in any browser — no server or internet connection required (Chart.js is vendored in `/vendor`).

## Tabs

| Tab | What it shows |
|---|---|
| **Overview** | KPI tear sheet, one-paragraph setup, bull/bear case, consensus & guidance anchor (S&P Capital IQ, June 2026) |
| **Net Adds Backdrop** | Quarterly locations & net adds (Q4'21–Q1'26, SEC-verified), annual record streak, ARR & ARR/location, Census BFS restaurant business applications (leading indicator), Toast adds vs industry net growth, TAM/penetration ladder |
| **Forecast Tool** | Driver-based 2026E–2030E model (core SMB + enterprise + international + F&B retail − churn) with sliders and Bear/Base/Bull/Mgmt scenario presets; outputs net adds, ending locations, SMB penetration, implied ARR, and the quarterly path vs the "record >30k" 2026 bar |
| **Biggest Customers** | Enterprise book (Applebee's, Firehouse Subs, Papa Murphy's, Topgolf, TGI Fridays, hotels, …) with deal sizes, rollout status, and — the L/S kicker — whether each host chain is net-opening or net-closing units; churn map (Jamba → Qu) and competitive landscape |
| **State Formation Map** | Tile cartogram + sortable 51-state table: BLS QCEW restaurant establishments (Q4'25 vs Q4'24) and Census BFS business applications (TTM May'26), with estimated state-level restaurant applications |

## Data provenance

- **Toast KPIs**: 8-K Ex-99.1 press releases, 10-K/10-Q (SEC CIK 1650164), earnings-call transcripts and prepared remarks; data through Q1 2026 (reported May 7, 2026).
- **Customer chains**: company press releases, Dine Brands / Hilton / Marriott / Choice / Topgolf-Callaway filings, franchise disclosures, trade press.
- **Consensus**: S&P Capital IQ (pulled June 11, 2026).
- **State data**: computed from raw BLS QCEW (NAICS 722 private establishments) and Census BFS (`bfs_monthly.csv`) files — see `data/state_formation.json` and `scripts/refresh_state_data.py`.
- Estimates are marked `[E]` in the UI; quarterly net adds derived from company-rounded "~X,000" disclosures carry ±1k error; Q1'21/Q3'21 locations were never disclosed.

## Refreshing the state data

```bash
python3 scripts/refresh_state_data.py            # downloads fresh QCEW/BFS files and re-injects
python3 scripts/refresh_state_data.py --offline  # reuse raw CSVs already in data/
```

After each Toast earnings report, update the hand-curated series at the top of the `<script>` block in `index.html` (`TQ`, `ARR`, `ANNUAL`, `CUST`) and the KPI cards.

Not investment advice.
