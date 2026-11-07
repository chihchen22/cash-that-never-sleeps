# Cash That Never Sleeps, Chapter 5: the mutual with a Treasury-backed tail (mutual_tail.py results)

Run environment: Python 3.12.13, numpy 2.5.2, matplotlib 3.11.1; a single process; the run time is printed to the console and not written here, so two runs give the same file. Command: `python -I -B model/mutual_tail.py` from the repository root. The script imports the clearing-cost engine's engine (`model/clearing_cost.py`) by path and reuses its parameters, copulas and quadrature. Seeds: 20261101 (member sizes), 20261102 (risk classes), 20261103 and 20261104 (one-year Monte Carlo check), 20261105 to 20261107 (reserve paths), 20261108 and 20261109 (settlement-draw sensitivity). Risk-free rate r = 4.3% (the clearing-cost engine's value; verify before relying on it).

All parameters are illustrative. Apart from figures labelled as reported public benchmarks, which are not model numbers, every parameter is an author assumption, chosen to be plausible and stated openly, and calibrated to no bank, mutual, vehicle or investor. Units: bps a year per unit of covered excess (the uninsured excess not placed through reciprocal networks) unless stated. Every number below is computed by `mutual_tail.py`; edit parameters there, not here.

## 1. Parameters

| Parameter | Symbol | Base | Range / set | Source |
|---|---|---|---|---|
| Member banks | N | 150 | 100, 150, 200 | [author assumption] |
| Member size | sigma | lognormal, sigma 1.0 | 1.0, 1.5; clipped to $1bn to $250bn of assets; seed 20261101 | [author assumption] |
| Liabilities / assets |  | 90% |  | [author assumption] |
| Covered excess sought, share of liabilities |  | 20% | 20%, 35%, 50% | [author assumption] |
| Tiered per-member cap on covered excess |  | 50% of the first $5bn of liabilities, 40% of the next $5bn, 30% above; at most $30bn | applied before the concentration cap | [author assumption (shape mirrors the reciprocal-deposit rule; not its parameters)] |
| Concentration cap on covered excess |  | 5% | 2%, 5%, 10% | [author assumption (design)] |
| Reserve target, paid in as capital at entry, in T-bills | theta_m | 3% | 2%, 3%, 5% | [author assumption (design)] |
| Special assessment cap, multiple of annual assessment | m | 2 | 0, 1, 2, 3 | [author assumption (design)] |
| Reserve opportunity cost over T-bills |  | 100 bps | 50, 100, 150 | [author assumption (the clearing-cost engine's Part I pool value)] |
| Mutual frictions | f_m | 5 bps | 2, 5, 10 | [author assumption] |
| Probability an acquirer takes all deposits at closure (rule M) | q_acq | 0.50 | 0.25, 0.50, 0.75, 1.00 | [author assumption] |
| Rule M: days the tail carries its advance of the assessment slice; carry rate |  | 7; r + s_b = 5.3% |  | [author assumption (the assessment is collected within the week)] |
| Exhaustion point X (cash at the trigger) | X | smallest X with P(not paid in full | median member fails) <= 1%, Gaussian, rho 0.30: 10.0% | alternative: 5% under Student-t(5): 21.8% | [author assumption (design; the clearing-cost engine's Section 39 standards)] |
| Lock-up premium on the tail's funded thickness | s_lock | 10 bps | 5, 10, 15 | [author assumption (the clearing-cost engine's FUND_K)] |
| Tail frictions per unit of funded thickness |  | 75 bps | 25.0, 37.5, 50.0, 75.0 | [author assumption (the clearing-cost engine's 15 bps, and its technology scenarios, per 20% of funded capacity)] |
| Default probability per member (P) | lambda_P | 0.25% | 0.10%, 0.25%, 0.50%, 1.00% | [author assumption (the clearing-cost engine's base)] |
| Risk-class mix |  | 60% of members at 0.15%; 30% of members at 0.35%; 10% of members at 0.75% | average 0.270% by member count, 0.291% by covered excess; seed 20261102 | [author assumption] |
| Risk premium multiplier (tail investors) | mu | 3 |  | [author assumption (the clearing-cost engine's base)] |
| Loss on the deposit claim | LGD | 25% | 15%, 25%, 40% | [author assumption (the clearing-cost engine's base)] |
| Advance dividend (rule B), linked to LGD | a | (2/3)(1 - LGD) = 50% | 56.7%, 50.0%, 40.0% | [author assumption (the clearing-cost engine's linked mode)] |
| Years to final receivership dividends (rule B) | D | 2 |  | [author assumption (the clearing-cost engine's base)] |
| Risk-free rate; bridge funding spread | r; s_b | 4.3%; 1.0% |  | [the clearing-cost engine's values] |
| Asset correlation | rho | 0.20 (prices) | 0.10, 0.20, 0.30; 0.30 for reliability, as the clearing-cost engine | [author assumption (the clearing-cost engine's set)] |
| Copulas |  | Gaussian | Student-t(5) | [the clearing-cost engine's] |
| State-dependent LGD (reliability, paths) |  | LGD 15% for z >= 0, linear to 40% at z = -3 | a = (2/3)(1 - LGD) | [the clearing-cost engine's correlated mode] |
| Replenishment assessment |  | over 3 years | 1, 3, 5 years | [author assumption] |
| Replacement funding spread | s_rep |  | 20, 40, 60, 80 bps | [author assumption] |

Reported public benchmarks beside the frictions and price assumptions (reported figures, not model numbers):

| Benchmark | Reported figures | bps of the base |
|---|---|---|
| Massachusetts Depositors Insurance Fund, 2025 net expenses | $3.45m on $21.92bn of insured excess deposits | 1.6 |
| Massachusetts Depositors Insurance Fund, 2025 assessments | $4.61m on $21.92bn | 2.1 |
| Excess Share Insurance Corp, 2025 premiums earned (loss and profit included) | $8.81m on about $8bn of excess limits | about 11 |

Conventions [author assumption unless noted]. Every layer is measured in the cash the applicable rule needs at its trigger date. Rule M (primary): the stack pays the FDIC the uninsured loss share, LGD x covered excess, at closure, so an acquirer assumes every deposit whole; no advance dividend, no later dividend, no access cost. Rule B (fallback): the depositor collects the advance dividend and the layers pay (1 - a) x covered excess on day seven, own the claim and fund the remaining recovery 1 - a - LGD for D years at r + s_b. Rule M applies with probability q_acq, drawn once for all of a year's failures (acquirer appetite as a market-wide state); Section 3 shows the same statistic with the draw independent failure by failure, and q_acq is the same under P and Q. A reported fact for orientation, not a calibration: of the three failures of spring 2023, one was a whole-bank acquisition and two went to bridge banks. The special assessment is collectable from surviving members only, m x assessment x (W - S), within the week, so it is not cash at closure: under rule M the tail advances the assessment slice at closure and is repaid from the assessment when it is collected, and cash at closure is the reserve plus the tail. Under rule B the assessment is assumed collectable by day seven, so rule B is unchanged. The tail's layer attaches where the reserve and the collectable assessment run out and is T = X - A thick, A = theta_m + m x assessment; its funded commitment is T plus the advance capacity m x assessment x W, that is X - theta_m, and it carries the advance for up to 7 days at r + s_b. The mutual prices its layer under P, the tail under Q = mu x lambda_P. All of a year's failures fall inside one settlement window. Prices use fixed LGD (the clearing-cost engine's pricing convention); reliability and the reserve paths use the state-dependent LGD and dividend of results_clearing_cost.md, Sections 38 and 44. The clearing-cost engine charges its 15 bps of frictions on the whole covered notional; here the tail's frictions scale with its funded thickness.

## 2. Member weights and caps

| Profile | Effective names | Top-5 share | Largest | Median | Smallest | Tiered cap binds: members / share of demand cut | Members at the 5% cap | Covered excess |
|---|---|---|---|---|---|---|---|---|
| Base: lognormal, N 150, demand 20%, tiered cap, cap 5% | 74.1 | 15.1% | 3.43% | 0.452% | 0.027% | 0 / 0.0% | 0 | $640bn |
| Same, no tiered cap (v1 weights) | 74.1 | 15.1% | 3.43% | 0.452% | 0.027% | n/a | 0 | $640bn |
| Lognormal, N 100 | 53.3 | 19.5% | 4.58% | 0.678% | 0.040% | 0 / 0.0% | 0 | $457bn |
| Lognormal, N 200 | 98.5 | 11.8% | 2.59% | 0.330% | 0.020% | 0 / 0.0% | 0 | $849bn |
| Lognormal, cap 2% | 87.8 | 10.0% | 2.00% | 0.492% | 0.030% | 0 / 0.0% | 12 | $640bn |
| Lognormal, cap 10% | 74.1 | 15.1% | 3.43% | 0.452% | 0.027% | 0 / 0.0% | 0 | $640bn |
| Lognormal, demand 35% of liabilities | 80.2 | 13.4% | 2.81% | 0.472% | 0.030% | 34 / 4.5% | 0 | $1,069bn |
| Lognormal, demand 50% of liabilities | 88.0 | 12.5% | 2.62% | 0.510% | 0.040% | 124 / 28.4% | 0 | $1,145bn |
| Lognormal, sigma 1.5 | 55.6 | 16.3% | 3.26% | 0.315% | 0.020% | 9 / 8.2% | 0 | $921bn |
| Equal, N 150 | 150.0 | 3.3% | 0.67% | 0.667% | 0.667% | n/a | 0 | n/a |

At a demand of 20% of liabilities the tiered shape cannot bind (its lowest rate, 30%, is above the demand) and the $30bn maximum binds for no members (the largest member seeks $22bn); at 35% and 50% the cap binds for 34 and 124 members. Weights are rounded to 1/30,000 of covered excess. The median member (rank 76) and the largest member are the reference members for reliability.

## 3. Method checks

Parity with the clearing-cost engine: the engine configured as the clearing-cost engine's reference design (50 banks at 2% each, all-funded 20% buffer, no mutual, gross par, lambda_P 0.25%, mu 3, LGD 25%, a 50%; price Gaussian rho 0.20 fixed LGD; reliability conditional on a given bank failing, rho 0.30, state-dependent LGD). Printed values are read from the clearing-cost engine's results file `model/results_clearing_cost.md`; 'engine code' is its in-memory value.

| Quantity | This model | Clearing-cost (printed) | Clearing-cost (code) | Within rounding |
|---|---|---|---|---|
| Price c* (bps), layer only | 37.71 | 37.7 | 37.74 | yes |
| Price c* (bps), with the expected loss above 20% added (the clearing-cost engine's credit convention) | 37.74 | 37.7 | 37.74 | yes |
| Section 38, 20% capacity, Gaussian: shortfall | 1.00836% | 1.008% | 1.00836% | yes |
| Section 38, 20% capacity, Gaussian: severity | 23.169% | 23.2% | 23.169% | yes |
| Section 38, 20% capacity, Gaussian: E[unpaid] | 0.233627% | 0.2336% | 0.233627% | yes |
| Section 38, 20% capacity, Gaussian: E[loss] | 0.093436% | 0.0934% | 0.093438% | yes |
| Section 38, 20% capacity, Student-t(5): shortfall | 27.73360% | 27.734% | 27.73360% | yes |
| Section 38, 20% capacity, Student-t(5): severity | 39.207% | 39.2% | 39.207% | yes |
| Section 38, 20% capacity, Student-t(5): E[unpaid] | 10.873405% | 10.8734% | 10.873405% | yes |
| Section 38, 20% capacity, Student-t(5): E[loss] | 3.291407% | 3.2914% | 3.291407% | yes |
| Section 44, rule B, 20% buffer, Gaussian: shortfall | 0.13740% | 0.137% | 0.13740% | yes |
| Section 44, rule B, 20% buffer, Student-t(5): shortfall | 10.45029% | 10.450% | 10.45029% | yes |
| Section 44, rule B, 20% buffer, Student-t(5): E[depositor loss] | 0.892881% | 0.8929% | 0.892881% | yes |

Parity result: all rows match the printed values within rounding.

Monte Carlo check of the engine: 1,000,000 simulated years per copula (the clearing-cost engine's latent-variable design), base weights, lambda_P 0.25%, rho 0.30, state-dependent LGD, mixed rule drawn once a year, the reference design. Exact = the subset-sum engine.

| Copula | Quantity | Exact | Monte Carlo (95% band) | z |
|---|---|---|---|---|
| Gaussian | P(reserve alone does not pay) | 0.42883% | 0.43000% +/- 0.01282% | +0.18 |
| Gaussian | P(mutual's resources exhausted) | 0.32738% | 0.32640% +/- 0.01118% | -0.17 |
| Gaussian | E[tail payout] (% of covered excess) | 0.00567% | 0.00555% +/- 0.00027% | -0.87 |
| Gaussian | E[cash at the trigger] (% of covered excess) | 0.10215% | 0.10258% +/- 0.00086% | +0.99 |
| Student-t(5) | P(reserve alone does not pay) | 0.79431% | 0.79480% +/- 0.01740% | +0.06 |
| Student-t(5) | P(mutual's resources exhausted) | 0.69843% | 0.69290% +/- 0.01626% | -0.67 |
| Student-t(5) | E[tail payout] (% of covered excess) | 0.02212% | 0.02181% +/- 0.00064% | -0.94 |
| Student-t(5) | E[cash at the trigger] (% of covered excess) | 0.09429% | 0.09362% +/- 0.00163% | -0.81 |

Monte Carlo check: every |z| is at most 3. Mix engine check (risk-class engine with one default probability against the exchangeable engine, rho 0.30, Gaussian): largest relative difference 1.8e-13.

Settlement-draw sensitivity: P(not paid in full | median member fails), reference design, rho 0.30, 400,000 simulated years with the median member forced to fail and each year weighted by its conditional default probability. 'Once a year' is the engine's convention; 'each failure' draws rule M or B independently for every failed member.

| Copula | Exact engine (once a year) | Monte Carlo, once a year | Monte Carlo, each failure |
|---|---|---|---|
| Gaussian | 0.99% | 1.00% +/- 0.098% | 1.00% +/- 0.098% |
| Student-t(5) | 20.19% | 21.01% +/- 0.970% | 21.34% +/- 0.975% |

## 4. Two settlement rules

Cash each failure draws at the trigger, economic loss and access, per unit of the failed member's covered excess, by LGD:

| LGD | Rule M: cash | Rule M: loss | Rule M: claim funded | Rule B: cash | Rule B: loss | Rule B: claim funded |
|---|---|---|---|---|---|---|
| 15% | 15.0% at closure | 15.0% | 0 | 43.3% on day seven | 15.0% | 28.3% for 2 years |
| 25% | 25.0% at closure | 25.0% | 0 | 50.0% on day seven | 25.0% | 25.0% for 2 years |
| 40% | 40.0% at closure | 40.0% | 0 | 60.0% on day seven | 40.0% | 20.0% for 2 years |

Under rule M the depositor never waits and the stack needs only the loss in cash; the receivership claim stays with the FDIC. Under rule B the stack needs the advance-dividend gap in cash and later recovers part of it. Rule M needs 50% of rule B's cash at the base LGD and 67% at LGD 40%.

Cash at closure under rule M, reference design, in a year in which members holding 10% of covered excess fail at LGD 40% (share of covered excess). The assessment, 2 x assessment x (W - S), is collected from survivors within the week, after closure. Without an advance it is a receivable at closure; in this design the tail advances it and is repaid when it is collected.

| Item | Assessment counted as a receivable | Tail advances the assessment (this design) |
|---|---|---|
| Due to the FDIC at closure (LGD x S) | 4.0000% | 4.0000% |
| Reserve | 3.0000% | 3.0000% |
| Assessment slice, collected within the week | 0.3786% (not cash at closure) | 0.3786% (repays the advance) |
| Tail: advance of the slice | 0 | 0.3786% |
| Tail: own layer | 0.6214% | 0.6214% |
| Cash at closure | 3.6214% | 4.0000% |
| Gap at closure | 0.3786% | 0.0000% |
| Tail: funded commitment (T + advance capacity) | 6.579% | 7.000% |

Across the conditional distribution (median member fails, Gaussian, rho 0.30) the tail advances in 4.35% of years and its largest cash call at closure (advance plus layer) is 6.896% of covered excess, within its funded commitment of 7.000%. The advance's expected carry is 0.0000 bps a year (r + s_b for 7 days on the expected advance under Q).

## 5. The reference design: sizing the tail

Exhaustion point needed to meet each conditional standard (median member fails, rho 0.30, state-dependent LGD), rounded up to 0.1%, by q_acq; all-in price at that X; and the other copula's performance of the same design.

| q_acq | Gaussian 1%: X | all-in | achieved | same design under t(5) | t(5) 5%: X | all-in | achieved | same design under Gaussian |
|---|---|---|---|---|---|---|---|---|
| rule B only | 11.6% | 22.73 | 1.00% | 23.76% | 26.4% | 34.98 | 4.96% | 0.0175% |
| 0.25 | 10.9% | 22.16 | 0.98% | 21.83% | 24.3% | 33.46 | 4.96% | 0.0236% |
| 0.50 (base) | 10.0% | 21.03 | 0.99% | 20.19% | 21.8% | 31.01 | 4.95% | 0.0320% |
| 0.75 | 9.0% | 19.82 | 0.97% | 18.69% | 18.8% | 28.12 | 4.97% | 0.0422% |
| rule M only | 7.8% | 18.44 | 0.97% | 17.76% | 15.5% | 24.97 | 4.99% | 0.0418% |

Layer stack (base, q_acq 0.5). Base-weight member = 1/N of covered excess; it draws 0.167% under rule M and 0.333% under rule B at the base LGD.

| Design | Reserve | Special assessment capacity | A | X | T | Tail commitment (T + rule-M advance) | A / X in base-weight members, rule M | rule B | A / X in largest members, rule M | rule B |
|---|---|---|---|---|---|---|---|---|---|---|
| Reference: X for 1% Gaussian | 3.00% | 0.421% | 3.421% | 10.00% | 6.579% | 7.000% | 20.5 / 60.0 | 10.3 / 30.0 | 5 / 19 | 3 / 8 |
| Alternative: X for 5% Student-t(5) | 3.00% | 0.620% | 3.620% | 21.80% | 18.180% | 18.800% | 21.7 / 130.8 | 10.9 / 65.4 | 5 / 86 | 3 / 22 |
| Memo: X at 10 base-weight members under rule B | 3.00% | 0.297% | 3.297% | 3.33% | 0.037% | 0.333% | 19.8 / 20.0 | 9.9 / 10.0 | 5 / 5 | 2 / 2 |

The memo row keeps v1's exhaustion point: 10 base-weight members under rule B pay 3.33% against the mutual's own attachment of 3.30%, so the tail is a sliver 0.037% thick at N 150 (it was empty in v1, when the higher assessment put A above X).

## 6. Price by layer

| Component (bps a year) | Reference: X for 1% Gaussian, mixed rule | Alternative: X for 5% Student-t(5), mixed rule | Reference: X for 1% Gaussian, rule B only (same X) | Alternative: X for 5% Student-t(5), rule B only (same X) | Reference: X for 1% Gaussian, equal weights | Alternative: X for 5% Student-t(5), equal weights |
|---|---|---|---|---|---|---|
| Mutual: expected loss on its retention (P) | 6.21 | 6.21 | 6.17 | 6.18 | 6.23 | 6.23 |
| Mutual: access (P) | 0.33 | 0.33 | 0.65 | 0.66 | 0.33 | 0.33 |
| Mutual: reserve carry theta_m x opportunity cost | 3.00 | 3.00 | 3.00 | 3.00 | 3.00 | 3.00 |
| Mutual: frictions f_m | 5.00 | 5.00 | 5.00 | 5.00 | 5.00 | 5.00 |
| **Mutual, own layer** | **14.54** | **14.54** | 14.83 | 14.84 | 14.56 | 14.56 |
| Tail: expected loss in the layer (Q) | 0.50 | 0.45 | 0.89 | 0.80 | 0.36 | 0.32 |
| Tail: access (Q) | 0.05 | 0.04 | 0.09 | 0.08 | 0.03 | 0.03 |
| Tail: lock-up s_lock x commitment | 0.70 | 1.88 | 0.66 | 1.82 | 0.70 | 1.88 |
| Tail: frictions on the commitment | 5.25 | 14.10 | 4.93 | 13.63 | 5.25 | 14.10 |
| Tail: carry on the rule-M assessment advance | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **Tail premium** | **6.50** | **16.47** | 6.57 | 16.33 | 6.34 | 16.33 |
| **All-in assessment** | **21.03** | **31.01** | 21.39 | 31.17 | 20.90 | 30.89 |
| Memo: expected loss above X, unprotected (P) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

Side by side (bps a year per unit of covered balance):

| Comparison | bps | Basis |
|---|---|---|
| All-in, reference design (X 10.0%) | 21.03 | this model |
| All-in, alternative design (X 21.8%) | 31.01 | this model |
| Memo: X at 10 base-weight members (tail 0.037% thick) | 14.83 | this model |
| The clearing-cost engine's reference design (all-funded 20% buffer, gross par) | 37.7 | results_clearing_cost.md, Section 36 |
| The clearing-cost engine's regional mutual pool (Part I), c*; net of its wrong-way haircut | 46; 42 | results_clearing_cost.md, Section 7 |
| Massachusetts Depositors Insurance Fund, 2025 assessments / insured excess deposits | 2.1 | reported, not a model number |
| Excess Share Insurance Corp, 2025 premiums earned / excess limits | about 11 | reported, not a model number |

Step by step from v1's Gaussian 1% design. Each step re-sizes X to the 1% Gaussian standard (median member, rho 0.30); C, the choice of that standard as the reference design, is the starting row.

| Step | X | T | Mutual | Tail | All-in | Change |
|---|---|---|---|---|---|---|
| v1: f_m 10 bps, rule B, no tiered cap (v1's Gaussian 1% design) | 11.7% | 8.15% | 19.83 | 7.84 | 27.67 |  |
| A: mutual frictions 5 bps | 11.6% | 8.15% | 14.83 | 7.90 | 22.73 | -4.95 |
| B: reserve paid in at entry (price already assumes the reserve at target) | 11.6% | 8.15% | 14.83 | 7.90 | 22.73 | +0.00 |
| Tiered per-member cap applied before the 5% cap | 11.6% | 8.15% | 14.83 | 7.90 | 22.73 | +0.00 |
| D: mixed settlement, q_acq 0.5 (= v2 reference design) | 10.0% | 6.58% | 14.54 | 6.50 | 21.03 | -1.69 |

## 7. Sensitivities

One assumption at a time from the base case (X held at each design's contract value). A is the nominal attachment, T the tail's funded thickness; bps a year except A and T.

| Case | A | Reference: T | mutual | tail | all-in | Alternative: T | tail | all-in |
|---|---|---|---|---|---|---|---|---|
| lambda_P 0.10% | 3.333% | 6.67% | 10.63 | 6.03 | 16.65 | 18.27% | 16.04 | 26.67 |
| lambda_P 0.25% | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| lambda_P 0.50% | 3.582% | 6.42% | 20.96 | 8.15 | 29.11 | 18.02% | 18.04 | 39.03 |
| lambda_P 1.00% | 3.944% | 6.06% | 33.56 | 13.63 | 47.19 | 17.65% | 23.69 | 57.33 |
| LGD 15% (a 56.7%) | 3.366% | 6.63% | 12.11 | 6.19 | 18.29 | 18.23% | 16.19 | 28.30 |
| LGD 25% (a 50.0%) | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| LGD 40% (a 40.0%) | 3.510% | 6.49% | 18.13 | 7.39 | 25.52 | 18.09% | 17.29 | 35.44 |
| rho 0.10 | 3.413% | 6.59% | 14.58 | 6.06 | 20.63 | 18.19% | 16.07 | 30.64 |
| rho 0.20 | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| rho 0.30 | 3.434% | 6.57% | 14.39 | 7.30 | 21.70 | 18.17% | 17.30 | 31.72 |
| Gaussian | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| Student-t(5) | 3.460% | 6.54% | 13.15 | 9.87 | 23.02 | 18.13% | 20.51 | 33.73 |
| rule B only | 3.428% | 6.57% | 14.83 | 6.57 | 21.39 | 18.18% | 16.33 | 31.17 |
| q_acq 0.25 | 3.428% | 6.57% | 14.68 | 6.71 | 21.39 | 18.17% | 16.66 | 31.36 |
| q_acq 0.50 | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| q_acq 0.75 | 3.413% | 6.59% | 14.39 | 6.28 | 20.67 | 18.19% | 16.27 | 30.67 |
| rule M only | 3.406% | 6.59% | 14.24 | 6.06 | 20.31 | 18.19% | 16.07 | 30.32 |
| N 100 | 3.423% | 6.58% | 14.51 | 6.64 | 21.15 | 18.18% | 16.60 | 31.12 |
| N 150 | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| N 200 | 3.419% | 6.58% | 14.55 | 6.42 | 20.96 | 18.18% | 16.40 | 30.95 |
| concentration cap 2% | 3.420% | 6.58% | 14.54 | 6.44 | 20.98 | 18.18% | 16.42 | 30.97 |
| concentration cap 5% | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| concentration cap 10% | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| covered excess sought 20% of liabilities | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| covered excess sought 35% of liabilities | 3.420% | 6.58% | 14.54 | 6.47 | 21.01 | 18.18% | 16.44 | 30.99 |
| covered excess sought 50% of liabilities | 3.420% | 6.58% | 14.54 | 6.44 | 20.99 | 18.18% | 16.42 | 30.97 |
| no tiered cap | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| size dispersion sigma 1.0 | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| size dispersion sigma 1.5 | 3.423% | 6.58% | 14.52 | 6.61 | 21.13 | 18.18% | 16.57 | 31.10 |
| equal weights, N 150 | 3.418% | 6.58% | 14.56 | 6.34 | 20.90 | 18.18% | 16.33 | 30.89 |
| theta_m 2% | 2.429% | 7.57% | 13.45 | 8.02 | 21.47 | 19.17% | 17.89 | 31.36 |
| theta_m 3% | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| theta_m 5% | 5.419% | 4.58% | 16.57 | 4.38 | 20.95 | 16.18% | 14.41 | 30.98 |
| m 0 | 3.000% | 7.00% | 14.51 | 6.69 | 21.20 | 18.80% | 16.73 | 31.24 |
| m 1 | 3.211% | 6.79% | 14.53 | 6.58 | 21.11 | 18.49% | 16.58 | 31.11 |
| m 2 | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| m 3 | 3.629% | 6.37% | 14.54 | 6.42 | 20.97 | 17.87% | 16.38 | 30.93 |
| reserve opportunity cost 50 bps | 3.391% | 6.61% | 13.03 | 6.51 | 19.54 | 18.21% | 16.48 | 29.52 |
| reserve opportunity cost 100 bps | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| reserve opportunity cost 150 bps | 3.450% | 6.55% | 16.04 | 6.49 | 22.52 | 18.15% | 16.46 | 32.50 |
| mutual frictions 2 bps | 3.361% | 6.64% | 11.53 | 6.52 | 18.05 | 18.24% | 16.49 | 28.03 |
| mutual frictions 5 bps | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| mutual frictions 10 bps | 3.520% | 6.48% | 19.54 | 6.46 | 26.00 | 18.08% | 16.44 | 35.98 |
| lock-up premium 5 bps | 3.414% | 6.59% | 14.53 | 6.15 | 20.68 | 18.20% | 15.53 | 30.08 |
| lock-up premium 10 bps | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |
| lock-up premium 15 bps | 3.428% | 6.57% | 14.54 | 6.84 | 21.38 | 18.16% | 17.40 | 31.95 |
| tail frictions 25.0 bps per unit of thickness | 3.351% | 6.65% | 14.53 | 3.02 | 17.56 | 18.37% | 7.13 | 21.67 |
| tail frictions 37.5 bps per unit of thickness | 3.368% | 6.63% | 14.53 | 3.89 | 18.42 | 18.32% | 9.47 | 24.00 |
| tail frictions 50.0 bps per unit of thickness | 3.386% | 6.61% | 14.53 | 4.76 | 19.29 | 18.27% | 11.80 | 26.34 |
| tail frictions 75.0 bps per unit of thickness | 3.421% | 6.58% | 14.54 | 6.50 | 21.03 | 18.18% | 16.47 | 31.01 |

Range of the all-in assessment across each sweep (bps), largest first for the reference design:

| Assumption | Reference: low to high | spread | Alternative: low to high | spread |
|---|---|---|---|---|
| lambda_P | 16.65 to 47.19 | 30.54 | 26.67 to 57.33 | 30.66 |
| f_m | 18.05 to 26.00 | 7.95 | 28.03 to 35.98 | 7.96 |
| LGD | 18.29 to 25.52 | 7.22 | 28.30 to 35.44 | 7.14 |
| f_tail | 17.56 to 21.03 | 3.48 | 21.67 to 31.01 | 9.34 |
| opp | 19.54 to 22.52 | 2.98 | 29.52 to 32.50 | 2.98 |
| copula | 21.03 to 23.02 | 1.99 | 31.01 to 33.73 | 2.72 |
| q_acq | 20.31 to 21.39 | 1.09 | 30.32 to 31.36 | 1.04 |
| rho | 20.63 to 21.70 | 1.06 | 30.64 to 31.72 | 1.07 |
| s_lock | 20.68 to 21.38 | 0.70 | 30.08 to 31.95 | 1.87 |
| theta_m | 20.95 to 21.47 | 0.52 | 30.98 to 31.36 | 0.38 |
| m | 20.97 to 21.20 | 0.23 | 30.93 to 31.24 | 0.31 |
| N | 20.96 to 21.15 | 0.18 | 30.95 to 31.12 | 0.17 |
| sigma | 21.03 to 21.13 | 0.09 | 31.01 to 31.10 | 0.09 |
| cap | 20.98 to 21.03 | 0.05 | 30.97 to 31.01 | 0.04 |
| demand | 20.99 to 21.03 | 0.05 | 30.97 to 31.01 | 0.04 |

All-in against lambda_P (bps), with the clearing-cost engine's reference design at the same default probability:

| lambda_P | Gaussian, reference | Gaussian, alternative | Student-t(5), reference | Student-t(5), alternative | Pooled-vehicle reference design |
|---|---|---|---|---|---|
| 0.05% | 15.28 | 25.31 | 15.71 | 25.84 | 21.1 |
| 0.10% | 16.65 | 26.67 | 17.51 | 27.77 | 25.3 |
| 0.25% | 21.03 | 31.01 | 23.02 | 33.73 | 37.7 |
| 0.50% | 29.11 | 39.03 | 32.34 | 43.99 | 58.5 |
| 0.75% | 37.91 | 47.86 | 41.68 | 54.50 | 79.2 |
| 1.00% | 47.19 | 57.33 | 50.99 | 65.17 | 100.0 |
| 1.50% | 66.49 | 77.66 | 69.31 | 86.79 | 141.4 |

## 8. Risk-class mix

Members assigned to classes at random (seed 20261102), independent of size. Coverage share by class: 0.15% class 54.4%, 0.35% class 33.0%, 0.75% class 12.5%. Average lambda_P 0.270% by member count, 0.291% by covered excess. Class rates allocate the risk terms by class lambda_P relative to the coverage-weighted average and the fixed terms pro rata [allocation convention]. The mix carries fixed LGD 25% throughout: a state-dependent LGD would need the frequency-domain step once per LGD state, which does not fit the run-time budget.

| Copula | Design | A | Mutual | Tail | All-in (pool) | Class 0.15% rate | Class 0.35% rate | Class 0.75% rate |
|---|---|---|---|---|---|---|---|---|
| Gaussian | Reference: X for 1% Gaussian | 3.445% | 15.61 | 6.63 | 22.24 | 18.22 | 23.91 | 35.30 |
| Gaussian | Alternative: X for 5% Student-t(5) | 3.644% | 15.62 | 16.59 | 32.21 | 28.22 | 33.86 | 45.16 |
| Student-t(5) | Reference: X for 1% Gaussian | 3.485% | 14.21 | 10.03 | 24.24 | 19.25 | 26.31 | 40.45 |
| Student-t(5) | Alternative: X for 5% Student-t(5) | 3.698% | 14.29 | 20.64 | 34.92 | 29.62 | 37.13 | 52.16 |

Reliability with the mix, rho 0.30, fixed LGD, design at the Gaussian mix price:

| Copula | Member | Design | Reserve alone | Plus special assessment | Plus tail | Short | Unconditional: stack exhausted |
|---|---|---|---|---|---|---|---|
| Gaussian | median | Reference: X for 1% Gaussian | 88.66% | 2.13% | 8.56% | 0.64% | 0.0060% |
| Gaussian | median | Alternative: X for 5% Student-t(5) | 88.66% | 2.92% | 8.40% | 0.0131% | < 0.0001% |
| Gaussian | largest | Reference: X for 1% Gaussian | 77.31% | 4.89% | 16.79% | 1.01% | 0.0060% |
| Gaussian | largest | Alternative: X for 5% Student-t(5) | 77.31% | 6.62% | 16.05% | 0.0182% | < 0.0001% |
| Student-t(5) | median | Reference: X for 1% Gaussian | 35.48% | 3.61% | 36.58% | 24.33% | 0.14% |
| Student-t(5) | median | Alternative: X for 5% Student-t(5) | 35.48% | 5.14% | 54.46% | 4.92% | 0.0158% |
| Student-t(5) | largest | Reference: X for 1% Gaussian | 25.20% | 4.24% | 42.72% | 27.84% | 0.14% |
| Student-t(5) | largest | Alternative: X for 5% Student-t(5) | 25.20% | 6.02% | 63.22% | 5.56% | 0.0158% |

## 9. Reliability in the year a given member fails

Real-world measure, conditional on the reference member failing in the year (the clearing-cost engine's ref_cond logic), state-dependent LGD and advance dividend, mixed rule; the cash test is at the trigger date of the rule that applies. 'Reserve alone' = the cash is within the reserve; 'plus special assessment' = the special assessment completes it; 'plus tail' = the tail is needed and completes it; 'short' = the stack is exhausted (public tail). The four sum to 100%. E[loss] = expected unpaid share x LGD, % of the member's covered excess. Unconditional 'stack exhausted' is the probability, in any year, that the public layer is reached.

rho 0.30:

| Copula | Member (weight) | Design | Reserve alone | Plus special assessment | Plus tail | Short | Paid in full | Severity | E[loss] | Unconditional: mutual exhausted | Unconditional: stack exhausted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Gaussian | median (0.45%) | Reference: X for 1% Gaussian | 87.41% | 1.99% | 9.61% | 0.99% | 99.01% | 21.2% | 0.0839% | 0.33% | 0.0128% |
| Gaussian | median (0.45%) | Alternative: X for 5% Student-t(5) | 87.41% | 2.79% | 9.77% | 0.0320% | 99.97% | 12.8% | 0.0016% | 0.29% | 0.0002% |
| Gaussian | median (0.45%) | Reference, rule B only (comparison) | 83.53% | 2.49% | 12.39% | 1.59% | 98.41% | 22.2% | 0.1410% | 0.48% | 0.0219% |
| Gaussian | largest (3.43%) | Reference: X for 1% Gaussian | 75.19% | 4.50% | 18.76% | 1.55% | 98.45% | 20.5% | 0.1269% | 0.33% | 0.0128% |
| Gaussian | largest (3.43%) | Alternative: X for 5% Student-t(5) | 75.19% | 6.27% | 18.49% | 0.0436% | 99.96% | 12.5% | 0.0022% | 0.29% | 0.0002% |
| Gaussian | largest (3.43%) | Reference, rule B only (comparison) | 65.54% | 6.22% | 25.71% | 2.53% | 97.47% | 21.3% | 0.2157% | 0.48% | 0.0219% |
| Student-t(5) | median (0.45%) | Reference: X for 1% Gaussian | 47.97% | 3.03% | 28.81% | 20.19% | 79.81% | 37.0% | 2.3827% | 0.70% | 0.15% |
| Student-t(5) | median (0.45%) | Alternative: X for 5% Student-t(5) | 47.97% | 4.35% | 42.73% | 4.95% | 95.05% | 22.6% | 0.3887% | 0.66% | 0.0239% |
| Student-t(5) | median (0.45%) | Reference, rule B only (comparison) | 38.43% | 3.03% | 30.46% | 28.08% | 71.92% | 39.6% | 3.4524% | 0.96% | 0.24% |
| Student-t(5) | largest (3.43%) | Reference: X for 1% Gaussian | 38.13% | 3.92% | 35.05% | 22.90% | 77.10% | 36.6% | 2.6541% | 0.70% | 0.15% |
| Student-t(5) | largest (3.43%) | Alternative: X for 5% Student-t(5) | 38.13% | 5.62% | 50.77% | 5.48% | 94.52% | 22.5% | 0.4260% | 0.66% | 0.0239% |
| Student-t(5) | largest (3.43%) | Reference, rule B only (comparison) | 25.45% | 4.15% | 38.26% | 32.14% | 67.86% | 39.1% | 3.8682% | 0.96% | 0.24% |

rho 0.20:

| Copula | Member (weight) | Design | Reserve alone | Plus special assessment | Plus tail | Short | Paid in full | Severity | E[loss] | Unconditional: mutual exhausted | Unconditional: stack exhausted |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Gaussian | median (0.45%) | Reference: X for 1% Gaussian | 95.62% | 1.05% | 3.26% | 0.0757% | 99.92% | 15.2% | 0.0046% | 0.14% | 0.0012% |
| Gaussian | median (0.45%) | Alternative: X for 5% Student-t(5) | 95.62% | 1.44% | 2.94% | 0.0004% | 100.00% | 8.8% | 0.0000% | 0.12% | < 0.0001% |
| Gaussian | median (0.45%) | Reference, rule B only (comparison) | 93.60% | 1.48% | 4.79% | 0.14% | 99.86% | 15.5% | 0.0086% | 0.23% | 0.0023% |
| Gaussian | largest (3.43%) | Reference: X for 1% Gaussian | 86.83% | 3.51% | 9.51% | 0.16% | 99.84% | 14.5% | 0.0092% | 0.14% | 0.0012% |
| Gaussian | largest (3.43%) | Alternative: X for 5% Student-t(5) | 86.83% | 4.79% | 8.39% | 0.0006% | 100.00% | 8.6% | 0.0000% | 0.12% | < 0.0001% |
| Gaussian | largest (3.43%) | Reference, rule B only (comparison) | 79.56% | 5.40% | 14.74% | 0.29% | 99.71% | 14.7% | 0.0173% | 0.23% | 0.0023% |
| Student-t(5) | median (0.45%) | Reference: X for 1% Gaussian | 56.36% | 3.19% | 27.22% | 13.23% | 86.77% | 32.7% | 1.3442% | 0.65% | 0.11% |
| Student-t(5) | median (0.45%) | Alternative: X for 5% Student-t(5) | 56.36% | 4.57% | 36.82% | 2.25% | 97.75% | 19.4% | 0.1510% | 0.61% | 0.0116% |
| Student-t(5) | median (0.45%) | Reference, rule B only (comparison) | 45.74% | 3.38% | 31.13% | 19.75% | 80.25% | 34.7% | 2.0678% | 0.93% | 0.18% |
| Student-t(5) | largest (3.43%) | Reference: X for 1% Gaussian | 45.69% | 4.30% | 34.44% | 15.57% | 84.43% | 32.4% | 1.5494% | 0.65% | 0.11% |
| Student-t(5) | largest (3.43%) | Alternative: X for 5% Student-t(5) | 45.69% | 6.14% | 45.59% | 2.58% | 97.42% | 19.3% | 0.1708% | 0.61% | 0.0116% |
| Student-t(5) | largest (3.43%) | Reference, rule B only (comparison) | 31.05% | 4.82% | 40.66% | 23.47% | 76.53% | 34.2% | 2.3983% | 0.93% | 0.18% |

Reference design by q_acq (X held at the reference value), median member, rho 0.30, short / stack exhausted:

| q_acq | Gaussian | Student-t(5) |
|---|---|---|
| rule B only | 1.59% / 0.0219% | 28.08% / 0.24% |
| 0.25 | 1.29% / 0.0173% | 24.14% / 0.20% |
| 0.50 | 0.99% / 0.0128% | 20.19% / 0.15% |
| 0.75 | 0.69% / 0.0082% | 16.25% / 0.11% |
| rule M only | 0.39% / 0.0037% | 12.31% / 0.0723% |

Equal weights and fixed-LGD sensitivities, rho 0.30, median member, short / stack exhausted:

| Copula | Base, ref | Base, alt | Equal weights, ref | Equal weights, alt | Fixed LGD 25%, ref | Fixed LGD 25%, alt |
|---|---|---|---|---|---|---|
| Gaussian | 0.99% / 0.0128% | 0.0320% / 0.0002% | 0.92% / 0.0104% | 0.0280% / 0.0002% | 0.46% / 0.0053% | 0.0094% / < 0.0001% |
| Student-t(5) | 20.19% / 0.15% | 4.95% / 0.0239% | 20.23% / 0.15% | 4.88% / 0.0229% | 18.10% / 0.14% | 3.49% / 0.0166% |

Memo (v1's X at 10 members, tail empty), median member, rho 0.30, short: Gaussian 10.96%; Student-t(5) 49.58%.

## 10. Single-member test

One member fails alone: a member sized at the concentration cap, and the largest member actually drawn where the cap does not bind. Cash at the trigger as % of covered excess against the reserve; 'yes' = the reserve alone pays. The last case is a rule-B failure whose dividend is not paid by day seven, so the layers pay par.

| Cap | Member | Weight | Case | Cash | Economic loss | Reserve 2% pays alone | Reserve 3% pays alone | Reserve 5% pays alone |
|---|---|---|---|---|---|---|---|---|
| 2% | member at the cap | 2.00% | rule M, LGD 25% | 0.50% | 0.50% | yes | yes | yes |
| 2% | member at the cap | 2.00% | rule M, LGD 40% | 0.80% | 0.80% | yes | yes | yes |
| 2% | member at the cap | 2.00% | rule B, LGD 25% (a 50%) | 1.00% | 0.50% | yes | yes | yes |
| 2% | member at the cap | 2.00% | rule B, LGD 40% (a 40%) | 1.20% | 0.80% | yes | yes | yes |
| 2% | member at the cap | 2.00% | rule B, dividend not paid by day seven (par) | 2.00% | 0.80% | yes | yes | yes |
| 5% | member at the cap | 5.00% | rule M, LGD 25% | 1.25% | 1.25% | yes | yes | yes |
| 5% | member at the cap | 5.00% | rule M, LGD 40% | 2.00% | 2.00% | yes | yes | yes |
| 5% | member at the cap | 5.00% | rule B, LGD 25% (a 50%) | 2.50% | 1.25% | no | yes | yes |
| 5% | member at the cap | 5.00% | rule B, LGD 40% (a 40%) | 3.00% | 2.00% | no | yes | yes |
| 5% | member at the cap | 5.00% | rule B, dividend not paid by day seven (par) | 5.00% | 2.00% | no | no | yes |
| 5% | largest drawn member | 3.43% | rule M, LGD 25% | 0.86% | 0.86% | yes | yes | yes |
| 5% | largest drawn member | 3.43% | rule M, LGD 40% | 1.37% | 1.37% | yes | yes | yes |
| 5% | largest drawn member | 3.43% | rule B, LGD 25% (a 50%) | 1.72% | 0.86% | yes | yes | yes |
| 5% | largest drawn member | 3.43% | rule B, LGD 40% (a 40%) | 2.06% | 1.37% | no | yes | yes |
| 5% | largest drawn member | 3.43% | rule B, dividend not paid by day seven (par) | 3.43% | 1.37% | no | no | yes |
| 10% | member at the cap | 10.00% | rule M, LGD 25% | 2.50% | 2.50% | no | yes | yes |
| 10% | member at the cap | 10.00% | rule M, LGD 40% | 4.00% | 4.00% | no | no | yes |
| 10% | member at the cap | 10.00% | rule B, LGD 25% (a 50%) | 5.00% | 2.50% | no | no | yes |
| 10% | member at the cap | 10.00% | rule B, LGD 40% (a 40%) | 6.00% | 4.00% | no | no | no |
| 10% | member at the cap | 10.00% | rule B, dividend not paid by day seven (par) | 10.00% | 4.00% | no | no | no |
| 10% | largest drawn member | 3.43% | rule M, LGD 25% | 0.86% | 0.86% | yes | yes | yes |
| 10% | largest drawn member | 3.43% | rule M, LGD 40% | 1.37% | 1.37% | yes | yes | yes |
| 10% | largest drawn member | 3.43% | rule B, LGD 25% (a 50%) | 1.72% | 0.86% | yes | yes | yes |
| 10% | largest drawn member | 3.43% | rule B, LGD 40% (a 40%) | 2.06% | 1.37% | no | yes | yes |
| 10% | largest drawn member | 3.43% | rule B, dividend not paid by day seven (par) | 3.43% | 1.37% | no | no | yes |

Probability the reserve alone (3%) does not pay in a year in which the largest member (3.43%) fails, mixed rule, state-dependent LGD: Gaussian rho 0.30: 24.81%; Gaussian rho 0.20: 13.17%; Student-t(5) rho 0.30: 61.87%; Student-t(5) rho 0.20: 54.31%.

## 11. Replenishment after a loss year

Ten-year paths from the target reserve (3%, paid in at entry), 100,000 paths, base weights, lambda_P 0.25%, state-dependent LGD, mixed rule drawn each year, reference design. Each year: cash payouts from the reserve, then the special assessment (up to the cap), then the tail up to T; T-bill income; the expected-loss and access parts of the assessment kept as income; rule-B recoveries after D years. At year end a reserve below target is restored first by a special assessment up to the unused part of that year's cap, then by a replenishment assessment in equal annual instalments (the first at once). Reserve above target is rebated; the rebate includes the T-bill income on the members' paid-in reserve. Reserve ratio = liquid reserve / covered excess at year end, after restoration.

| Run | Replenish over (years) | Year 1: 5th / 50th / 95th | Year 5: 5th / 50th / 95th | Year 10: 5th / 50th / 95th | Years starting below target | At least one special assessment for losses | At least one restoration | Tail pays at least once | Tail pays in a year started below target | Stack exhausted at least once | Mean restoration assessment (bps a year) | Mean rebate (bps a year) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gaussian, rho 0.20 (base) | 1 | 3.00% / 3.00% / 3.00% | 3.00% / 3.00% / 3.00% | 3.00% / 3.00% / 3.00% | 0 | 2.14% | 73.43% | 1.47% | 0 | 0.0110% | 6.44 | 18.37 |
| Gaussian, rho 0.20 (base) | 3 | 3.00% / 3.00% / 3.00% | 2.88% / 3.00% / 3.00% | 2.88% / 3.00% / 3.00% | 6.20% | 2.21% | 73.43% | 1.51% | 0.15% | 0.0110% | 6.09 | 18.20 |
| Gaussian, rho 0.20 (base) | 5 | 3.00% / 3.00% / 3.00% | 2.76% / 3.00% / 3.00% | 2.77% / 3.00% / 3.00% | 7.27% | 2.26% | 73.43% | 1.54% | 0.22% | 0.0110% | 5.67 | 17.89 |
| Gaussian, rho 0.30 | 1 | 3.00% / 3.00% / 3.00% | 3.00% / 3.00% / 3.00% | 3.00% / 3.00% / 3.00% | 0 | 4.15% | 68.56% | 3.24% | 0 | 0.14% | 6.98 | 18.75 |
| Gaussian, rho 0.30 | 3 | 3.00% / 3.00% / 3.00% | 2.84% / 3.00% / 3.00% | 2.83% / 3.00% / 3.00% | 6.40% | 4.26% | 68.56% | 3.32% | 0.35% | 0.14% | 6.53 | 18.55 |
| Gaussian, rho 0.30 | 5 | 3.00% / 3.00% / 3.00% | 2.67% / 3.00% / 3.00% | 2.67% / 3.00% / 3.00% | 7.57% | 4.31% | 68.56% | 3.37% | 0.48% | 0.14% | 6.02 | 18.18 |
| Student-t(5), rho 0.20 | 1 | 3.00% / 3.00% / 3.00% | 3.00% / 3.00% / 3.00% | 3.00% / 3.00% / 3.00% | 0 | 7.29% | 42.21% | 6.30% | 0 | 1.07% | 5.41 | 19.95 |
| Student-t(5), rho 0.20 | 3 | 3.00% / 3.00% / 3.00% | 2.99% / 3.00% / 3.00% | 2.99% / 3.00% / 3.00% | 4.40% | 7.35% | 42.21% | 6.35% | 0.43% | 1.08% | 4.97 | 19.76 |
| Student-t(5), rho 0.20 | 5 | 3.00% / 3.00% / 3.00% | 2.81% / 3.00% / 3.00% | 2.82% / 3.00% / 3.00% | 5.20% | 7.39% | 42.21% | 6.38% | 0.56% | 1.09% | 4.51 | 19.45 |
| Gaussian, rho 0.20, alternative design | 3 | 3.00% / 3.00% / 3.00% | 2.99% / 3.00% / 3.00% | 2.99% / 3.00% / 3.00% | 4.54% | 2.19% | 73.43% | 1.27% | 0.0890% | 0 | 6.17 | 18.26 |

Probability the reserve is below target at each year end (after restoration):

| Run | Replenish over | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 | Year 6 | Year 7 | Year 8 | Year 9 | Year 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Gaussian, rho 0.20 (base) | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gaussian, rho 0.20 (base) | 3 | 4.99% | 7.51% | 7.11% | 7.00% | 7.11% | 7.03% | 7.12% | 7.03% | 7.06% | 7.01% |
| Gaussian, rho 0.20 (base) | 5 | 4.99% | 8.22% | 8.43% | 8.61% | 8.56% | 8.42% | 8.52% | 8.47% | 8.46% | 8.47% |
| Gaussian, rho 0.30 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Gaussian, rho 0.30 | 3 | 4.96% | 7.70% | 7.36% | 7.32% | 7.30% | 7.41% | 7.33% | 7.28% | 7.38% | 7.39% |
| Gaussian, rho 0.30 | 5 | 4.96% | 8.34% | 8.75% | 9.04% | 8.95% | 9.02% | 8.90% | 8.83% | 8.95% | 8.95% |
| Student-t(5), rho 0.20 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Student-t(5), rho 0.20 | 3 | 3.20% | 5.20% | 5.05% | 4.94% | 5.06% | 5.17% | 5.15% | 5.15% | 5.08% | 5.07% |
| Student-t(5), rho 0.20 | 5 | 3.20% | 5.53% | 5.97% | 6.11% | 6.17% | 6.23% | 6.24% | 6.30% | 6.23% | 6.22% |

Memo (v1 convention, for comparison): starting at 1% with no capital call and no replenishment, Gaussian rho 0.20, the median reserve is 1.71% at year 10 and the stack is exhausted at least once in 0.0290% of paths; the tail pays in a year started below target in 11.26% of paths.

Year 2 after a 2023-like cluster (the logic of results_clearing_cost.md, Section 40). Year 1: three members of about base weight (2.03% of covered excess together) fail, two settled under rule B and one under rule M at the base LGD, taking 0.84% of cash from the reserve; rule-B recoveries have not yet arrived. Year 2: 147 surviving members at their original weights, rho 0.30, state-dependent LGD, mixed rule, the reference design's tail unchanged; the reserve enters Year 2 at the level shown. Conditional on the median surviving member failing in Year 2: short / E[unpaid share]; unconditional: stack exhausted.

| Year-2 reserve regime | Reserve entering Year 2 | Gaussian: short / E[unpaid] | Student-t(5): short / E[unpaid] | Gaussian: stack exhausted | Student-t(5): stack exhausted |
|---|---|---|---|---|---|
| Not restored | 2.16% | 1.23% / 0.2716% | 21.93% / 8.3870% | 0.0170% | 0.17% |
| Special assessment at year end, up to the cap | 2.57% | 1.08% / 0.2315% | 20.81% / 7.7928% | 0.0143% | 0.16% |
| Special assessment, then the first of 5 replenishment instalments | 2.66% | 1.05% / 0.2240% | 20.59% / 7.6750% | 0.0138% | 0.16% |
| Special assessment, then the first of 3 replenishment instalments | 2.71% | 1.03% / 0.2191% | 20.44% / 7.5976% | 0.0134% | 0.16% |
| Special assessment, then the rest at once (fully restored) | 3.00% | 0.93% / 0.1965% | 19.72% / 7.2237% | 0.0119% | 0.15% |
| Year 1 at full reserve (reference) | 3.00% | 0.99% / 0.2097% | 20.19% / 7.4690% | 0.0128% | 0.15% |

## 12. The bank's side: three-party clearing with a replacement-cost ceiling

The condition of results_clearing_cost.md, Section 41, Delta + bank value >= price, with the bank's replacement funding spread s_rep (reciprocal fee plus rate uplift, or an FHLB advance, over the deposit's cost) added to the retention value WTP = dP_run x V x 4.067. Two readings. Full count: s_rep in full each year (the counterfactual is the balance not held at the bank); this is the ceiling on what the bank should pay to keep the balance. Probability-weighted: dP_run x s_rep x 4.067, the expected replacement cost avoided. Smallest Delta that clears (bps):

Full-count reading (ceiling):

| s_rep | Retention cell | WTP | Bank total | Min Delta, reference (21.03) | Min Delta, alternative (31.01) | Min Delta, pooled-vehicle reference (37.7) |
|---|---|---|---|---|---|---|
| 20 | none | 0.0 | 20.0 | 1.0 | 11.0 | 17.7 |
| 20 | V 100, dP_run 1.0% | 4.1 | 24.1 | 0.0 | 6.9 | 13.7 |
| 20 | V 150, dP_run 5.0% | 30.5 | 50.5 | 0.0 | 0.0 | 0.0 |
| 40 | none | 0.0 | 40.0 | 0.0 | 0.0 | 0.0 |
| 40 | V 100, dP_run 1.0% | 4.1 | 44.1 | 0.0 | 0.0 | 0.0 |
| 40 | V 150, dP_run 5.0% | 30.5 | 70.5 | 0.0 | 0.0 | 0.0 |
| 60 | none | 0.0 | 60.0 | 0.0 | 0.0 | 0.0 |
| 60 | V 100, dP_run 1.0% | 4.1 | 64.1 | 0.0 | 0.0 | 0.0 |
| 60 | V 150, dP_run 5.0% | 30.5 | 90.5 | 0.0 | 0.0 | 0.0 |
| 80 | none | 0.0 | 80.0 | 0.0 | 0.0 | 0.0 |
| 80 | V 100, dP_run 1.0% | 4.1 | 84.1 | 0.0 | 0.0 | 0.0 |
| 80 | V 150, dP_run 5.0% | 30.5 | 110.5 | 0.0 | 0.0 | 0.0 |

Probability-weighted reading (expected value):

| s_rep | Retention cell | WTP | Bank total | Min Delta, reference (21.03) | Min Delta, alternative (31.01) | Min Delta, pooled-vehicle reference (37.7) |
|---|---|---|---|---|---|---|
| 20 | none | 0.0 | 0.0 | 21.0 | 31.0 | 37.7 |
| 20 | V 100, dP_run 1.0% | 4.1 | 4.9 | 16.2 | 26.1 | 32.9 |
| 20 | V 150, dP_run 5.0% | 30.5 | 34.6 | 0.0 | 0.0 | 3.2 |
| 40 | none | 0.0 | 0.0 | 21.0 | 31.0 | 37.7 |
| 40 | V 100, dP_run 1.0% | 4.1 | 5.7 | 15.3 | 25.3 | 32.0 |
| 40 | V 150, dP_run 5.0% | 30.5 | 38.6 | 0.0 | 0.0 | 0.0 |
| 60 | none | 0.0 | 0.0 | 21.0 | 31.0 | 37.7 |
| 60 | V 100, dP_run 1.0% | 4.1 | 6.5 | 14.5 | 24.5 | 31.2 |
| 60 | V 150, dP_run 5.0% | 30.5 | 42.7 | 0.0 | 0.0 | 0.0 |
| 80 | none | 0.0 | 0.0 | 21.0 | 31.0 | 37.7 |
| 80 | V 100, dP_run 1.0% | 4.1 | 7.3 | 13.7 | 23.7 | 30.4 |
| 80 | V 150, dP_run 5.0% | 30.5 | 46.8 | 0.0 | 0.0 | 0.0 |

## 13. What the numbers say

The reference design sizes the tail so that, in the year the median member fails, the stack falls short with probability at most 1% under the Gaussian copula. With an acquirer settling under rule M in 50% of loss years, that takes X to 10.0% and the all-in assessment to 21.0 bps a year on covered excess: 14.5 for the mutual and 6.5 for the tail. Expected loss and access are 7.1 of it. From v1's 27.7 bps, lower frictions take 4.9 bps off and the mixed rule 1.7; the paid-in reserve and the tiered cap leave the price unchanged.

The same design falls short with probability 20.19% under the Student-t(5) copula. Meeting a 5% t standard takes X to 21.8% and the price to 31.0 bps. The stack is exhausted, and the public layer reached, in 0.0128% of years (Gaussian) and 0.15% (t).

With the reserve paid in at entry and losses restored by special assessment and then a 3-year replenishment, the reserve is below target at a year end with probability about 7.11%, and the tail pays in a year started short in 0.15% of ten-year paths. After a 2023-like cluster with the reserve not restored, the Year-2 Gaussian shortfall is 1.23% against 0.99% in Year 1.

The clearing-cost engine's all-funded reference is 37.7 bps; the Massachusetts fund reported 2.1 bps of assessments. Across the sweeps the reference price moves most with the default probability, the mutual's frictions and LGD.

## 14. Modelling notes

1. Layers are measured in the cash the applicable rule needs at its trigger date (rule M at closure, rule B on day seven). Economic loss equals the cash under rule M and LGD / (1 - a) of it under rule B.
2. Rule M or B is drawn once for all of a year's failures; Section 3 shows that drawing it failure by failure changes the reference design's conditional shortfall by less than the Monte Carlo error.
3. The special assessment is levied on survivors only and collected within the week. Under rule M it is not cash at closure: the tail advances it and is repaid when it is collected, so the tail's funded commitment is its layer T plus the advance capacity (X - theta_m in all), and lock-up and frictions are charged on the commitment. The tail's layer attaches where the reserve and the collectable assessment run out (fixed thickness T). While the reserve is below target the tail attaches lower than priced.
4. The reserve is paid in at entry; its carry is priced as theta_m x the opportunity cost. A year-end special assessment for restoration uses only the unused part of that year's cap.
5. Members price their own layer under P; the tail's investors price under Q (mu 3); q_acq is the same under both.
6. Tail frictions scale with funded thickness at the clearing-cost engine's ratio; the fixed costs of a separate vehicle would make a thin layer dearer than shown.
7. The risk-class mix carries fixed LGD; all other reliability figures use the state-dependent LGD.
8. The tiered cap uses member liabilities derived from the lognormal sizes; its shape mirrors the reciprocal-deposit rule and its parameters are author assumptions.
9. The bank's side shows both readings of the replacement spread: the full count as a ceiling, the probability-weighted count as the expected value.
10. The run time is printed to the console only, so the results file is identical across runs.
11. The advance carries no credit charge: the assessment on survivors is assumed collectable within the week. A survivor that cannot pay would leave the tail with a claim on it; that risk is not priced.
