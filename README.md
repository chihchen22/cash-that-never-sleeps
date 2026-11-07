# Cash That Never Sleeps

A small manual of commercial deposit liquidity at regional banks, worked with frontier AI models. Chih Chen, November 2026.

## The question

A regional bank holds commercial cash it cannot insure, and that cash runs on two clocks the bank does not run on. On the run clock, a balance above the insured limit is the first to leave when the bank is doubted, and in March 2023 it left in hours. On the settlement clock, a tokenized or always-on deposit can move to another bank at any hour of any day, while the bank's assets, its repo market and the large-value settlement rail keep business hours. FedNow runs around the clock; the funding side does not. The manual asks whether a regional bank can keep such cash, and at what price.

## The answer, in brief

Nine routes go on one price list, each priced in the same four terms (credit, access, capacity, frictions), scored against five screens and picked by a rule written before any number was read: the cheapest all-in price among routes passing every applicable screen, an open legal question counting as a failure.

Read strictly, the champion for the run clock is a pooled Treasury-backed vehicle sized to a 99 percent standard, at 37.94 basis points a year, with no challenger. With each open legal question resolved in the route's favor, a member-owned mutual with a Treasury-backed tail wins at 21.03, with the vehicle as challenger; the tail advances the members' special assessment at closure, so the stack pays the FDIC in cash on the day it is due. One legal question decides between them: whether a national bank may contribute entry capital to a state-licensed excess-deposit mutual.

For the settlement clock none of the nine routes qualifies strictly, with every open legal question counted as a failure. Read in the route's favor, a collateralized weekend netting facility wins at 10 to 34 basis points for a fifth of the balance (base 22.00), and the challenger is a prefunded joint account at a Reserve Bank on the model of the RTP network, at 13.6 to 37.1 (base 25.35). Neither keeps the balance nine tenths lendable at that share. Every net debtor in the facility must settle at the Sunday 9:00 p.m. Fedwire opening in reserves or collateralized Reserve Bank credit of at least its cap, and the balance stays 0.80 lendable only if that collateral is loans the bank already holds. At the assumed weekend peak net debit the facility cannot keep the balance nine tenths lendable and hold a member's cap to a rare event at once: a cap that binds in 1 percent of a member's weekends needs backing of a third of the balance, and at a dispersion of 0.8 the two hold together only if the median peak net debit is at most 1.56 percent of the balance against the 5 percent assumed, a number only a bank with tokenized deposits can observe. Holding today's bind rate, under the announced Sunday-to-Friday Fedwire schedule the facility misses the lendable screen by 0.004 if the debit scales with the hours (0.044 under square-root scaling). Under seven-day operation it passes only with weekend Reserve Bank credit, since Fedwire Securities and the repo market still close for the weekend; with reserves held against the weekend debit it fails. Every parameter is illustrative and calibrated to no bank.

## This is an experiment

Frontier AI models did the financial engineering under my direction. Models from three families drafted, extended and challenged the work in turn, and checks by models that did not write a passage traced its numbers to the code and its facts to primary sources. Each chapter of the manual ends with a short account of what the models built there and what they got wrong; Part 5 gives the full account. In the seventh stage GPT Astra reviewed the manual adversarially; every number it recomputed reproduced (one extreme tail percentile only within simulation error), four definitions and one cash-timing assumption did not, and the manual and engines were changed for all ten findings. [`PROCESS.md`](PROCESS.md) is the process record: the seven stages of the work, the error and challenge log, what is unverified, and the lessons. The last step is human expert review.

## Challenge it

Open an [issue](../../issues) with a correction, a counter-argument or evidence. Chapter 10 of the manual lists the questions I most want challenged, the deciding legal question first.

## Contents

| Path | What it is |
|---|---|
| [`cash-that-never-sleeps.pdf`](cash-that-never-sleeps.pdf) | The manual (97 pages, 16 figures, 19 tables) |
| [`model/`](model/) | The five engines: `clearing_cost.py` (Chapter 3: the clearing cost and the pooled vehicle), `mutual_tail.py` (Chapter 5: the mutual and its Treasury-backed tail, which advances the special assessment at closure), `uninsured_panel.py` with its cached FDIC pulls (Chapter 1), `routes.py` (Chapters 2 and 4 to 7: nine routes priced, screened and run through the rule, imports the first two by path), `settlement.py` (Chapter 6: each member's peak net debit in an open debtor cohort, the cap ladder and median sensitivity, the closed-window calendar, the buffer test, the Sunday settlement cash and the Monday cash gap, imports `routes.py` by path); each writes its `results_*.md` |
| [`figures/`](figures/) | Every figure the engines draw, one folder per engine; the map below names the sixteen the manual uses |
| [`docs/`](docs/) | Two interactive dashboards served by GitHub Pages: the clearing cost (Chapter 3, `index.html`) and the settlement clock (Chapter 6, `settlement.html`); [`tests/`](tests/) checks each against the Python engines |
| [`PROCESS.md`](PROCESS.md), [`reviews/`](reviews/) | The process record, and a review of an outside AI-produced draft |

## Reproduce the numbers

Python 3.12, from the repository root:

```
pip install -r requirements.txt
python -I -B model/clearing_cost.py
python -I -B model/mutual_tail.py
python -I -B model/uninsured_panel.py
python -I -B model/routes.py
python -I -B model/settlement.py
python -I -B tests/fixtures.py
node tests/parity.mjs
python -I -B tests/fixtures_settlement.py
node tests/parity_settlement.mjs
```

The whole set runs in about ten minutes, plus about eight for the settlement page's fixtures, which import both engines, the routes and settlement engines taking about two and a half each. The panel script runs offline from its cached FDIC pulls. Each engine writes its results file in `model/` and its figures in `figures/<engine>/`; all were run from a fresh copy of the repository and reproduce every number in every results file (only the printed run time varies with the machine). Before any new result is read, the routes engine reads fourteen headlines from the two engines it imports and checks them at the precision the manual quotes:

| Headline (engine) | Imported | Recorded |
|---|---|---|
| Single-name funded vehicle c*, bps (clearing-cost engine) | 45.7375 | 45.74 |
| Pooled all-funded reference design c*, bps (clearing-cost engine) | 37.7375 | 37.7 |
| Self-insured cost, credit + access under Q, bps (clearing-cost engine) | 20.7375 | 21 |
| Conditional shortfall at 20% capacity, Gaussian rho 0.30, % (clearing-cost engine) | 1.0084 | 1.0 |
| Conditional shortfall at 20% capacity, Student-t(5) rho 0.30, % (clearing-cost engine) | 27.7336 | 27.7 |
| All-in, reference design, mixed rule, bps (mutual engine) | 21.0319 | 21.03 |
| All-in, alternative design, bps (mutual engine) | 31.0108 | 31.01 |
| All-in, reference X, rule B only, bps (mutual engine) | 21.3916 | 21.39 |
| Mutual own layer, reference design, bps (mutual engine) | 14.5350 | 14.54 |
| Tail premium, reference design, bps (mutual engine) | 6.4969 | 6.50 |
| Reference design short given median member fails, Gaussian, % (mutual engine) | 0.9877 | 0.99 |
| Reference design short given median member fails, Student-t(5), % (mutual engine) | 20.1948 | 20.19 |
| Exhaustion point X, reference, % (mutual engine) | 10.0000 | 10.0 |
| Exhaustion point X, alternative, % (mutual engine) | 21.8000 | 21.8 |
| Method check: R6 sizing wrapper against the mutual engine's iso_x, X; and its all-in, bps | 0.100000; 21.031883 | 0.100000; 21.031883 |
| Method check: R5 sizing wrapper against the clearing-cost engine's iso-reliability row, failures covered; price, bps | 11.000000; 37.937500 | 11.000000; 37.937500 |
| Method check: bearer split against the self-insured cost, largest absolute gap, bps | 0.000000 | 0.000000 |

Every row passes; source: `model/results_routes.md`, Section 2. The settlement engine checks the twelve values it imports from the routes engine the same way, and every row passes; source: `model/results_settlement.md`, Section 2.

## Where each chapter's numbers come from

Section numbers refer to `model/results_routes.md` unless another results file is named.

| Part of the manual | Results-file sections |
|---|---|
| Abstract | 9 (champions, challengers, t(5) prices and shortfalls); 4; 7; `results_settlement.md`, Sections 3, 4 and 8 |
| Chapter 1 | `results_panel.md`, Sections 1, 1b, 3, 4 and 5 (the surviving-bank panel and its decomposition) |
| Chapter 2 | 1; 3; 8 (screen definitions); 9 (the rule); 10b (which deposit runs on which clock); `results_panel.md`, Section 2 (the 93.8 percent) |
| Chapter 3 | `results_clearing_cost.md`, Sections 2, 5 (the sensitivities), 3 (the bank seller and the 0.28 percent crossover), 8 (the break-even advantage), 9 (the wedge, the $4.6 million premium and the 60 years), 11, 17, 18 and 22 (pooling, the state-dependent loss, the Student-t shortfall and the pooled vehicle), 21 and 37 (the facility cost floor and the buffer-versus-facility rule), 33 (the retention-value sweep), 36 (the reference design), 38 (the conditional shortfalls), 39, 41 (three-party clearing), 42 (the exact cash-flow check), 44 (settlement rules and the quiet-year value) |
| Chapter 4 | 4 and 5; 6; 7 (route detail, R9 and its share table included); 8 (reasons and sources); 9 |
| Chapter 5 | 9 (reliability of every design); 11; `results_mutual_tail.md`, Sections 4 (settlement rules, cash at closure and the tail's advance of the assessment), 5 and 6 (sizing, the tail's funded commitment and the price by layer), 7 (sweeps), 8 (risk classes), 9, 11 (replenishment and the second year); `results_clearing_cost.md`, Sections 38 and 39 (the 1.0084 percent and the 11-failure row) |
| Chapter 6 | 7 (the facility's and R9's prices, lendable shares and shared-infrastructure figures); 8; 9; `results_settlement.md`, Sections 2 (parity), 3 (the peak net debit, same-weekend binding in an open debtor cohort, the cap ladder and the median sensitivity), 4 (the closed-window calendar, the schedules, the elapsed-hours check and the seven-day conditions), 5 (the liquidity-buffer test), 6 (sponsored access), 7 (the Monday cash gap, legal and operational intervals), 8 (the Sunday settlement cash source) and 9 (conventions) |
| Chapter 7 | 10 (the two banks, R9 included, and the replacement-cost ceiling); 10b (the charge by kind of deposit, Table 17); `results_mutual_tail.md`, Section 12; `results_clearing_cost.md`, Section 44 (the quiet-year value) |
| Chapter 8 | 8; `results_clearing_cost.md`, Section 28 (the challenge register); `results_mutual_tail.md`, Section 8 (class rates) |
| Chapter 9 | [`PROCESS.md`](PROCESS.md) |
| Appendices | 2 (parity); 1 (parameters); `results_mutual_tail.md` and `results_settlement.md`, Section 1 (the advance, overdraft and Fedwire Securities parameters) |

## Figure map

| Manual | File |
|---|---|
| Figure 1 | [`figures/routes/fig-U01.png`](figures/routes/fig-U01.png) |
| Figure 2 | [`figures/clearing_cost/fig-03.png`](figures/clearing_cost/fig-03.png) |
| Figure 3 | [`figures/clearing_cost/fig-10.png`](figures/clearing_cost/fig-10.png) |
| Figures 4 to 9 | [`figures/routes/`](figures/routes/) `fig-U02.png` to `fig-U07.png` |
| Figure 10 | [`figures/mutual_tail/fig-M03.png`](figures/mutual_tail/fig-M03.png) |
| Figure 11 | [`figures/routes/fig-U08.png`](figures/routes/fig-U08.png) |
| Figures 12 to 14 | [`figures/settlement/`](figures/settlement/) `fig-S01.png` to `fig-S03.png` |
| Figures 15 and 16 | [`figures/routes/`](figures/routes/) `fig-U09.png` and `fig-U10.png` |

Stage 7 regenerated Figures 4 to 12 and 14 to 16 under the same file names; Figures 1 to 3 and 13 are unchanged. R9 appears in Figures 4 to 7 and 15, and Figure 14 now draws the buffer test on the absolute lendable-share convention.

## Citation and licence

Cite as: Chen, C. (2026). Cash That Never Sleeps: a small manual of commercial deposit liquidity at regional banks, worked with frontier AI models. November 2026. See [`CITATION.cff`](CITATION.cff).

The code (`model/`, `docs/`, `tests/`) is MIT licensed ([`LICENSE`](LICENSE)). The manual, the figures, the process record and the review are licensed CC BY 4.0 ([`LICENSE-paper.md`](LICENSE-paper.md)).

## Disclaimer

The views expressed are my own and do not represent those of any employer or organization with which I am affiliated. The parameters and results are illustrative and are not estimates for any bank, nor are they a forecast; any term sheet is indicative and for discussion only. Nothing here is legal, investment or regulatory advice; readers should consult qualified professionals before relying on it. The private protection described is not deposit insurance and is not insured by any government agency. The manual is shared for discussion and challenge and may change in later versions.
