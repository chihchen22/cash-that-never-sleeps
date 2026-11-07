# Cash That Never Sleeps, Chapter 1: uninsured share at banks of $10 billion to $250 billion (uninsured_panel.py results)

Built by `uninsured_panel.py` from FDIC BankFind Suite bank-level data. Every number below is the script's own output on data it pulled; nothing is typed in except the four printed reference values used to check the QBP spreadsheet read.

## Run record

- Data pulled (UTC): 2026-11-02T07:11:06Z to 2026-11-02T07:13:07Z, 24 cached files under `model/cache/` (per-file URL, time and size in `cache/pull_meta.json`). A second run reads the cache only.
- API financials index: `risview_20260819185831`, created 2026-08-19T18:58:33Z.
- Python 3.12.13, pandas 3.0.5, numpy 2.5.2; HTTP by urllib (the `requests` package is not installed in this environment).
- QBP comparison values: read from the spreadsheet.

| Date | Institutions returned by the API | Pages | In group |
|---|---|---|---|
| 2022 Q4 | 4773 | 5 | 149 |
| 2023 Q2 | 4714 | 5 | 146 |
| 2024 Q4 | 4560 | 5 | 150 |
| 2026 Q2 | 4313 | 5 | 147 |

## Method

- Endpoint and fields: `financials` (RIS view), fields CERT, NAME, REPDTE, ASSET, DEP, DEPDOM, DEPINS, plus DEPUNINS and DEPCSBQ for the diagnostics. The insured-deposit field is DEPINS, titled "ESTIMATED INSURED DEPOSITS" in the API's `risview_properties.yaml`. DEPDOM is "Deposits held in domestic offices". DEPUNINS is "ESTIMATED UNINSURED DEPOSITS IN DOMESTIC OFFICES AND IN INSURED BRANCHES IN US TERRITORIES AND POSSESSIONS"; DEPCSBQ is "DEPOSIT LIABILITIES AFTER EXCLUSIONS". Amounts are in thousands of dollars.
- Dates: REPDTE 20221231, 20230630, 20241231, 20260630; every institution at each date, paged 1000 at a time sorted by CERT.
- Group: 10,000,000 <= ASSET <= 250,000,000 (thousands), both bounds inclusive, at each date. The QBP labels the group "Assets $10 Billion - $250 Billion" and does not state inclusivity in its notes; banks reporting exactly a bound: 2022 Q4 0, 2023 Q2 0, 2024 Q4 0, 2026 Q2 0, so the choice does not bind.
- Group uninsured share = 100 x (1 - sum DEPINS / sum DEPDOM) over the group at that date, a weighted ratio of sums as the QBP notes describe for condition ratios. Uninsured dollars = sum (DEPDOM - DEPINS).
- 2023 failures: CERTs from the `failures` endpoint with FAILDATE in 2023, intersected with the 2022 Q4 group (not hard-coded).
- Fixed panel: 2022 Q4 group members, less the 2023 failures, that file at all three later dates; each bank's own data at each date, whether or not it is still in the size band.
- Acquirer screens: (i) DEPDOM growth above 30% from 2022 Q4 to 2026 Q2; (ii) the panel bank is ACQ_CERT on a `history` event from 2023-01-01 to 2026-06-30 with CHANGECODE in {211 Failure - Whole Institution, 216 Bridge Bank Resolution, 221 Absorption - Without Assistance, 223 Merger - Without Assistance, 224 Affiliated Institution Merger (corporate reorganization)}; (iii) the same without code 224; (iv) (i) or (ii). Branch purchases (code 712) are not counted as acquisitions.

## 1. Group uninsured share against the published QBP ratio

| Date | Banks in group (API) | QBP count | API share, 1 - DEPINS/DEPDOM | API share, DEPUNINS/DEPDOM | QBP share | Gap, API less QBP (points) | Uninsured $bn (API) |
|---|---|---|---|---|---|---|---|
| 2022 Q4 | 149 | 145 | 42.11 | 43.64 | 41.66 | +0.45 | 2,431.6 |
| 2023 Q2 | 146 | 142 | 33.98 | 35.04 | 33.36 | +0.62 | 1,751.8 |
| 2024 Q4 | 150 | 144 | 34.38 | 35.48 | 33.88 | +0.50 | 1,876.7 |
| 2026 Q2 | 147 | 140 | 37.32 | 37.70 | 36.46 | +0.86 | 1,848.1 |

QBP share is 100 less "Estimated Insured Deposits as a Percent of Total Deposits - Domestic" for "Assets $10 Billion - $250 Billion" in the QBP second-quarter 2026 time-series spreadsheet. Check against the printed reference values (Chapter 1, one decimal): 2022 Q4 41.66 vs 41.7, 2023 Q2 33.36 vs 33.4, 2024 Q4 33.88 vs 33.9, 2026 Q2 36.46 vs 36.5.

## 1b. Same reading in QBP scope

The QBP Notes to Users exclude U.S. branches of foreign banks and non-deposit trust companies. This reading drops group members with BKCLASS OI (insured U.S. branch of a foreign chartered institution) or NC (noninsured non-deposit commercial bank or trust company) at each date, using the BKCLASS the financials endpoint reports for that date.

| Date | Banks in group (QBP scope) | QBP count | Dropped by class | Share, QBP scope | QBP share | Gap, API less QBP (points) | Share of the dropped banks | Uninsured $bn |
|---|---|---|---|---|---|---|---|---|
| 2022 Q4 | 145 | 145 | NC 2, OI 2 | 41.66 | 41.66 | +0.00 | 73.20 | 2,372.5 |
| 2023 Q2 | 142 | 142 | NC 2, OI 2 | 33.36 | 33.36 | +0.00 | 71.93 | 1,692.4 |
| 2024 Q4 | 144 | 144 | NC 3, OI 3 | 33.88 | 33.88 | +0.00 | 65.51 | 1,820.7 |
| 2026 Q2 | 140 | 140 | NC 3, OI 4 | 36.46 | 36.46 | +0.00 | 69.32 | 1,757.6 |

2022 Q4 in QBP scope: 41.66; with the three failures removed 38.41; difference -3.26 points. Decomposition 2022 Q4 to 2023 Q2 in QBP scope (same four parts as Section 3): -3.26, -0.42, -3.97, -0.66; total -8.30.

## 2. The three 2023 failures

| CERT | Name (failures endpoint) | Failure date | ASSET 2022 Q4 $bn | DEPDOM 2022 Q4 $bn | Uninsured share 2022 Q4 |
|---|---|---|---|---|---|
| 24735 | SILICON VALLEY BANK | 3/10/2023 | 209.0 | 161.5 | 93.81 |
| 57053 | SIGNATURE BANK | 3/12/2023 | 110.4 | 88.6 | 89.26 |
| 59017 | FIRST REPUBLIC BANK | 5/1/2023 | 212.6 | 176.4 | 67.32 |

Other 2023 failures on the endpoint (2) were not in the 2022 Q4 group.

2022 Q4 group share 42.11; with the three removed 38.93; difference -3.17 points.

## 3. Decomposition of the group's change, 2022 Q4 to 2023 Q2

| Component | Points |
|---|---|
| Failed 2023 banks leaving the group | -3.17 |
| Other exits (group members at the start no longer filing at the end) | -0.39 |
| Surviving banks' own change (fixed set, own data at both dates) | -3.93 |
| Size migration and entrants (survivors leaving the size band, banks entering it) | -0.63 |
| **Total (group share change)** | **-8.13** |

Group 149 banks at the start (42.11), 146 at the end (33.98); surviving set 143 banks, 38.54 at the start and 34.61 at the end. The parts telescope, so they sum to the total exactly.

## 3b. Same decomposition, 2022 Q4 to 2026 Q2

| Component | Points |
|---|---|
| Failed 2023 banks leaving the group | -3.17 |
| Other exits (group members at the start no longer filing at the end) | -0.32 |
| Surviving banks' own change (fixed set, own data at both dates) | -1.14 |
| Size migration and entrants (survivors leaving the size band, banks entering it) | -0.15 |
| **Total (group share change)** | **-4.78** |

Group 149 banks at the start (42.11), 147 at the end (37.32); surviving set 129 banks, 38.61 at the start and 37.47 at the end. The parts telescope, so they sum to the total exactly.

## 4. Fixed panel of surviving banks

129 banks: the 149 group members at 2022 Q4, less 3 failures, less those not filing at every later date. The panel defined by filing at 2023 Q2 and 2026 Q2 only has 129 banks (the same set).

| Date | Banks | Uninsured share | Uninsured $bn | DEPDOM $bn | Above $250bn | Below $10bn |
|---|---|---|---|---|---|---|
| 2022 Q4 | 129 | 38.61 | 1,851.0 | 4,794.1 | 0 | 0 |
| 2023 Q2 | 129 | 34.97 | 1,723.5 | 4,928.7 | 1 | 1 |
| 2024 Q4 | 129 | 35.47 | 1,837.6 | 5,180.4 | 1 | 0 |
| 2026 Q2 | 129 | 37.47 | 2,177.4 | 5,811.3 | 5 | 2 |

QBP scope (drop 4 panel banks with BKCLASS OI or NC at 2022 Q4): 125 banks.

| Date | Banks | Uninsured share | Uninsured $bn | DEPDOM $bn | Above $250bn | Below $10bn |
|---|---|---|---|---|---|---|
| 2022 Q4 | 125 | 38.02 | 1,791.8 | 4,713.3 | 0 | 0 |
| 2023 Q2 | 125 | 34.34 | 1,664.0 | 4,846.0 | 1 | 1 |
| 2024 Q4 | 125 | 34.91 | 1,781.8 | 5,103.6 | 1 | 0 |
| 2026 Q2 | 125 | 36.63 | 2,087.4 | 5,698.9 | 5 | 2 |

## 5. Panel without likely acquirers

(i) DEPDOM grew more than 30%, 2022 Q4 to 2026 Q2: 35 banks excluded, 94 remain.

| Date | Banks | Uninsured share | Uninsured $bn | DEPDOM $bn | Above $250bn | Below $10bn |
|---|---|---|---|---|---|---|
| 2022 Q4 | 94 | 39.08 | 1,326.3 | 3,393.3 | 0 | 0 |
| 2023 Q2 | 94 | 35.55 | 1,196.7 | 3,366.3 | 0 | 1 |
| 2024 Q4 | 94 | 36.17 | 1,250.5 | 3,457.1 | 0 | 0 |
| 2026 Q2 | 94 | 37.90 | 1,371.8 | 3,619.3 | 1 | 2 |

Same in QBP scope: 91 banks.

| Date | Banks | Uninsured share | Uninsured $bn | DEPDOM $bn | Above $250bn | Below $10bn |
|---|---|---|---|---|---|---|
| 2022 Q4 | 91 | 38.33 | 1,271.4 | 3,316.8 | 0 | 0 |
| 2023 Q2 | 91 | 34.73 | 1,142.3 | 3,288.6 | 0 | 1 |
| 2024 Q4 | 91 | 35.54 | 1,204.8 | 3,390.2 | 0 | 0 |
| 2026 Q2 | 91 | 36.90 | 1,301.2 | 3,526.4 | 1 | 2 |

(ii) Acquirer on a whole-institution history event, 2023-01-01 to 2026-06-30: 46 banks excluded (3 of them acquired a failed bank or its bridge bank), 83 remain. Overlap with screen (i): 25 banks.

| CHANGECODE | Events with a panel bank as acquirer | Distinct panel acquirers |
|---|---|---|
| 211 | 1 | 1 |
| 216 | 2 | 2 |
| 223 | 53 | 36 |
| 224 | 13 | 11 |

| Date | Banks | Uninsured share | Uninsured $bn | DEPDOM $bn | Above $250bn | Below $10bn |
|---|---|---|---|---|---|---|
| 2022 Q4 | 83 | 38.83 | 1,296.7 | 3,339.1 | 0 | 0 |
| 2023 Q2 | 83 | 34.52 | 1,144.3 | 3,315.2 | 0 | 0 |
| 2024 Q4 | 83 | 35.16 | 1,221.6 | 3,474.5 | 0 | 0 |
| 2026 Q2 | 83 | 37.40 | 1,402.9 | 3,750.9 | 2 | 2 |

(iii) As (ii) without affiliated reorganizations (code 224): 39 excluded, 90 remain.

| Date | Banks | Uninsured share | Uninsured $bn | DEPDOM $bn | Above $250bn | Below $10bn |
|---|---|---|---|---|---|---|
| 2022 Q4 | 90 | 37.86 | 1,336.9 | 3,531.6 | 0 | 0 |
| 2023 Q2 | 90 | 33.59 | 1,179.3 | 3,511.3 | 0 | 1 |
| 2024 Q4 | 90 | 34.31 | 1,260.5 | 3,673.9 | 0 | 0 |
| 2026 Q2 | 90 | 36.54 | 1,448.6 | 3,963.9 | 2 | 2 |

(iv) Excluded by (i) or (ii): 56 excluded, 73 remain.

| Date | Banks | Uninsured share | Uninsured $bn | DEPDOM $bn | Above $250bn | Below $10bn |
|---|---|---|---|---|---|---|
| 2022 Q4 | 73 | 40.28 | 1,165.6 | 2,894.2 | 0 | 0 |
| 2023 Q2 | 73 | 36.53 | 1,040.2 | 2,847.9 | 0 | 0 |
| 2024 Q4 | 73 | 37.57 | 1,105.8 | 2,943.1 | 0 | 0 |
| 2026 Q2 | 73 | 39.24 | 1,207.4 | 3,077.0 | 1 | 2 |

## 6. Survivorship

| Date | 2022 Q4 group members no longer filing (incl. failures) | Same, failures excluded | Panel-eligible banks still in the size band | Banks in the band not from the 2022 Q4 group (net of failures) |
|---|---|---|---|---|
| 2023 Q2 | 6 | 3 | 140 | 6 |
| 2024 Q4 | 8 | 5 | 140 | 10 |
| 2026 Q2 | 20 | 17 | 122 | 25 |

Of the 17 non-failed 2022 Q4 group members not filing at 2026 Q2, 16 appear as OUT_CERT on a history event from 2023-01-01 to 2026-06-30.

## 7. Differences from the published QBP ratio and why

What the QBP second-quarter 2026 Notes to Users state (cached as `cache/qbp_notes_users_2026q2.pdf`):

- Coverage is "all FDIC-insured Call Report filers"; U.S. branches of foreign banks and non-deposit trust companies are excluded unless indicated. Subsidiary reports are included with no adjustment for double counting. The financials endpoint returns the excluded filers too, so the all-filer sum in Section 1 includes institutions the QBP leaves out; Section 1b removes them by BKCLASS.
- Estimated insured deposits are "total deposit liabilities after exclusions minus estimated uninsured deposits"; banks of $1 billion or more report the uninsured estimate. The ratio's denominator is domestic deposits. The API's DEPINS reconciles to DEPCSBQ less DEPUNINS for 2022 Q4: 149 of 149 group banks within $1 thousand (max gap 0); 2023 Q2: 146 of 146 group banks within $1 thousand (max gap 0); 2024 Q4: 150 of 150 group banks within $1 thousand (max gap 0); 2026 Q2: 147 of 147 group banks within $1 thousand (max gap 0). The DEPUNINS/DEPDOM column of the Section 1 table is the uninsured estimate taken directly.
- Ratios are weighted (sum of numerators over sum of denominators). Size groups are by total assets; the QBP notes do not state the bound convention or whether size is measured on the current quarter's report.

Bank-count check: the API group has 149 banks at 2022 Q4 (QBP 145), 146 banks at 2023 Q2 (QBP 142), 150 banks at 2024 Q4 (QBP 144), 147 banks at 2026 Q2 (QBP 140).

Bank-count check in QBP scope: 145 at 2022 Q4 (QBP 145), 142 at 2023 Q2 (QBP 142), 144 at 2024 Q4 (QBP 144), 140 at 2026 Q2 (QBP 140).

Gap, API less QBP, in points, all API filers: 2022 Q4 +0.45, 2023 Q2 +0.62, 2024 Q4 +0.50, 2026 Q2 +0.86; in QBP scope: 2022 Q4 +0.004, 2023 Q2 +0.000, 2024 Q4 +0.002, 2026 Q2 -0.004. The all-filer gap is the scope difference the QBP notes state: removing BKCLASS OI and NC filers reproduces the QBP bank count at every date and leaves a residual inside the spreadsheet's two-decimal rounding (largest 0.004 points), so nothing is left to explain.

