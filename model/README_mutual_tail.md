# The mutual-tail engine (`mutual_tail.py`, Chapter 5)

`mutual_tail.py` prices and sizes a three-layer private protection design for the uninsured excess of large corporate deposits at regional banks (Chapter 5 of "Cash That Never Sleeps"). It extends the clearing-cost engine (`model/clearing_cost.py`, Chapter 3), which it imports by path and does not copy.

All parameters are illustrative author assumptions, calibrated to no bank. Figures from the Massachusetts Depositors Insurance Fund and the Excess Share Insurance Corp are reported public benchmarks, not model numbers.

## What it computes

- **The stack.** Reciprocal placement covers the insured base, outside the model. A member-owned mutual holds a reserve paid in as capital at entry and may levy a capped special assessment on surviving members. The clearing-cost engine's funded vehicle sits on top, up to an exhaustion point X; above X the loss is public.
- **Settlement.** Rule M: an acquirer takes every deposit and the stack pays the FDIC the loss at closure. Rule B (the clearing-cost engine's): the layers pay par less the advance dividend on day seven. Rule M applies with a stated probability.
- **Timing at closure.** The special assessment is collected from survivors within the week, so it is not cash at closure. Under rule M the Treasury-backed tail advances the assessment slice at closure and is repaid from the assessment when it is collected: cash at closure is the reserve plus the tail. The tail's funded commitment is its layer T plus the advance capacity, X - theta_m in all; lock-up and frictions are charged on the commitment, and the advance carries r + s_b for up to seven days (`ADV_DAYS`, `ADV_RATE`, author assumptions). Rule B is unchanged, on the stated assumption that the assessment is collectable by day seven. Results Section 4 shows cash at closure, item by item, for a year in which 10 percent of covered excess fails at LGD 40 percent.
- **The reference design.** X is the smallest exhaustion point meeting the clearing-cost engine's 1% Gaussian conditional standard; the 5% Student-t(5) design is the alternative.
- **Price by layer.** Mutual under the real-world measure, tail under the clearing-cost engine's pricing measure, including the cost of standing ready to advance the assessment under rule M.
- **Unequal member weights.** Exact: the clearing-cost engine's count distribution (both copulas) combined with a subset-sum recursion over member weights, after a tiered per-member cap and a concentration cap.
- **Checks.** Parity with the clearing-cost engine's printed reference figures (`results_clearing_cost.md`, Sections 36, 38 and 44); seeded Monte Carlo checks.
- **Beyond price.** Reliability when a given member fails, a single-member test, replenishment paths, Year 2 after a cluster, and the bank's clearing condition.

## How to run

From the repository root, with the repository's requirements installed (numpy, matplotlib):

    python -I -B model/mutual_tail.py

A run takes under two minutes, including the clearing-cost engine's own import, and prints the run time. Importing the module computes every table and writes nothing when Python runs with `-B`.

## Outputs

- `model/results_mutual_tail.md`: every number, in tables, with the run environment in the header.
- `figures/mutual_tail/fig-M01.png` to `fig-M09.png` at the repository root: the figures (the folder is created if absent).

## Seeds and determinism

Seeds are fixed (20261101 to 20261109; the results header lists each use). Two runs produce the same results file and figures; the run time is printed to the console only.

## Uninsured-share panel (`uninsured_panel.py`)

A separate, data-only script that rebuilds the Chapter 1 reading for the $10 billion to $250 billion group from FDIC bank-level data and tests how much of the 2023 drop is composition. It does not import or change `mutual_tail.py`.

- **Inputs, all pulled by the script.** FDIC BankFind Suite API (`api.fdic.gov/banks`, the host that `banks.data.fdic.gov/api` redirects to): the `financials` endpoint for every institution at REPDTE 20221231, 20230630, 20241231 and 20260630 (fields CERT, NAME, REPDTE, ASSET, DEP, DEPDOM, DEPINS, DEPUNINS, DEPCSBQ, BKCLASS, paged 1,000 rows at a time); the `failures` endpoint for 2023 failures; the `history` endpoint for merger events from 2023 to 2026 Q2. Also the QBP second-quarter 2026 time-series spreadsheet and Notes to Users, for the published group ratio and bank count.
- **What it computes.** The group's uninsured share (1 less DEPINS over DEPDOM) at each date, for all API filers and in QBP scope (insured branches of foreign banks and non-deposit trust companies removed), against the published QBP ratio; the 2023 failures, identified by CERT; an exact four-part decomposition of the group's change; a fixed panel of the surviving 2022 Q4 members, with acquirer screens by deposit growth and by merger events; survivorship counts.
- **Cache.** Raw pulls go to `model/cache/` with a `pull_meta.json` of URLs, UTC pull dates and sizes. A cached file is never re-pulled, and a cached file from a different URL stops the run. To re-pull, pass `--cache <new dir>` and `--out <new file>`.
- **Run.** `python -I -B model/uninsured_panel.py` (numpy, pandas, openpyxl; HTTP by the standard library). The first run takes about two and a half minutes, mostly the QBP spreadsheet download; a cached run takes under a second and rewrites `model/results_panel.md` byte for byte.
- **Output.** `model/results_panel.md`. It names only the three failed banks; acquirers are counted, not named.
