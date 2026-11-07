# Cash That Never Sleeps, Chapters 4 to 7: one price list for the large uninsured deposit (routes.py results)

Every number is illustrative and calibrated to no bank, vehicle, mutual, facility or investor. Parameters are author assumptions unless labelled as a reported figure with its source; reported figures are not model numbers. Units: bps a year per unit of a $100 million corporate balance above the insured limit, unless stated. Command: `python -I -B model/routes.py` from the repository root. The script imports the clearing-cost engine (`model/clearing_cost.py`) and the mutual engine (`model/mutual_tail.py`) by path and copies no code from either. Seeds: 20261110 (weekend outflow Monte Carlo check), 20261111 (illustrative weekend path, fig-U08); the imported engines carry their own. Run environment: Python 3.12.13, numpy 2.5.2; the run time is printed to the console and not written here, so two runs give the same file. Attributions of who bears the risk and the screen verdicts marked [author's reading] are readings, not findings of law.

## 1. Parameters

| Parameter | Value | Label |
|---|---|---|
| Balance above the insured limit | $100 million | [author assumption] |
| lambda_P; mu; LGD; a; D | 0.25%; 3; 25%; 50% (linked to LGD, a = (2/3)(1 - LGD)); 2 years | [author assumption (the clearing-cost engine's base)] |
| r; s_b | 4.3%; 1.0% | [author assumption (the clearing-cost engine's base; r rounded from a reported 3-month bill rate, as the clearing-cost engine states)] |
| rho | 0.20 for prices, 0.30 for reliability; Gaussian copula, Student-t(5) disclosed | [author assumption (the clearing-cost engine's)] |
| Screen S2 threshold; screen S5 standard | lendable share >= 0.9; P(not paid in full \| own bank fails) <= 1%, Gaussian, rho 0.30 | [author assumption] |
| R1 over-collateralization | 110% of the deposit | [reported figure, Cal. Gov. Code 53651 and 53652 (via a secondary source)] |
| R1 cost, pledged from securities held; if bought | 10.0 to 30.0; 150.0 to 300.0 loan-to-security spread on 110% | [author assumption, Chapter 4] |
| R2 public-unit letter fee by district | 10.5 to 18.0; to 35.0 variable-balance and 20.0 other purposes at one district; activity stock 10.0 bps of the letter where required (not priced here) | [reported figure, FHLBank Des Moines 2026; FHLBank San Francisco 2025; FHLBank Boston 2022; FHLBank Topeka 2023] |
| R3 placement fee | 12.5 | [reported figure, Chain Bridge Bancorp 2026 (one bank's disclosure)] |
| R3 rate uplift | 0.0, 10.0, 25.0 (base 10.0) | [author assumption] |
| R4 replacement spread | 50.0 to 300.0 | [author assumption, Chapter 3] |
| R7 always-on share; haircut | 20%; 2% on bills | [author assumption, Chapter 6] |
| R7 terms: credit; access; encumbrance spread; frictions | 0.0 to 1.0; 2.0 to 5.0; 25.0 to 100.0 on the bill slice; 3.0 to 8.0 | [author assumption, Chapter 6] |
| R7 weekend net outflow / always-on tier | lognormal, median 25%, sigma 0.8 (sweep 0.5, 0.8, 1.2); 52 weekends a year, independent | [author assumption (illustrative)] |
| R8 shared-infrastructure saving | 50% of the smaller structure's access term plus 1.0 bp of frictions; swept from none to the full access term | [author assumption] |
| R9 prefunded share of the tokenized balance | 20% (by share: 5%, 7%, 10%, 20%, 35%, 50%) | [author assumption, R9 block] |
| R9 joint-account balance earns IORB | yes in the base (the other setting is shown as a sensitivity) | [reported figure for the RTP joint account, Board order effective 7 June 2023; no general rule for other joint accounts] |
| R9 IORB; 3-month bill (coupon-equivalent) | 3.90%; 4.13% | [reported figures, Board of Governors (IORB since 17 September 2026) and US Treasury, accessed 3 November 2026] |
| R9 terms: credit; access; loan spread over bills; frictions | 0.0 to 0.5; 2.0 to 6.0; 25.0 to 100.0 on the position; 2.0 to 6.0 | [author assumption, R9 block] |
| R9 per-payment fee; per-payment limit; liquidity management transfer limit | $0.045 per payment sent, nothing to receive (negligible in bps); $10 million; $500 million per transfer | [reported figures, The Clearing House RTP; FedNow Service operating procedures v3.7, 13 October 2026] |
| Banks: assets; liabilities / assets; covered excess / liabilities | $50bn and $5bn; 90%; 20% | [author assumption] |
| Reciprocal allowance (non-brokered) | 50% of the first $1bn of liabilities, 40% of the next $9bn, 30% above, at most $30bn; agent well capitalized, CAMELS 1 to 3 | [reported figure, 12 CFR 337.6(e); FDIC 2026] |
| Replacement spread s_rep; retention cells | 20.0, 40.0, 60.0, 80.0; none, V 100 with dP_run 1%, V 150 with dP_run 5% | [author assumption (the mutual model's)] |
| Mutual design (R6) | N 150, theta_m 3% paid in, m 2, reserve opportunity cost 100.0, f_m 5.0, q_acq 0.5 | [author assumption (the mutual model's)] |

## 2. Parity with the imported engines

Each headline is read from the imported engine in memory (no number is typed in) and compared at the precision the headline is quoted.

| Headline | Imported value | Quoted | Match |
|---|---|---|---|
| Single-name funded vehicle c*, bps (clearing_cost.py) | 45.7375 | 45.74 | pass |
| Pooled all-funded reference design c*, bps (clearing_cost.py) | 37.7375 | 37.7 | pass |
| Self-insured cost, credit + access under Q, bps (clearing_cost.py) | 20.7375 | 21 | pass |
| Conditional shortfall at 20% capacity, own bank fails, Gaussian rho 0.30, % (clearing_cost.py) | 1.0084 | 1.0 | pass |
| Conditional shortfall at 20% capacity, own bank fails, Student-t(5) rho 0.30, % (clearing_cost.py) | 27.7336 | 27.7 | pass |
| All-in, reference design (X 10.0%, Gaussian 1%, q_acq 0.5, mixed rule), bps (mutual) | 21.0319 | 21.03 | pass |
| All-in, alternative design (X 21.8%, t(5) 5%), bps (mutual) | 31.0108 | 31.01 | pass |
| All-in, reference X, rule B only, bps (mutual) | 21.3916 | 21.39 | pass |
| Mutual own layer, reference design, bps (mutual) | 14.5350 | 14.54 | pass |
| Tail premium, reference design, bps (mutual) | 6.4969 | 6.50 | pass |
| Reference design short given median member fails, Gaussian rho 0.30, % (mutual) | 0.9877 | 0.99 | pass |
| Reference design short given median member fails, Student-t(5) rho 0.30, % (mutual) | 20.1948 | 20.19 | pass |
| Exhaustion point X, reference, % (mutual) | 10.0000 | 10.0 | pass |
| Exhaustion point X, alternative, % (mutual) | 21.8000 | 21.8 | pass |

Parity result: all rows pass.

| Method check | This model | Engine | Match |
|---|---|---|---|
| R6 sizing wrapper at base vs the mutual model's iso_x: X | 0.100000 | 0.100000 | pass |
| R6 sizing wrapper at base vs the mutual model's reference all-in, bps | 21.031883 | 21.031883 | pass |
| R5 sizing wrapper at base vs the clearing-cost engine's iso-reliability row: failures covered | 11.000000 | 11.000000 | pass |
| R5 sizing wrapper at base vs the clearing-cost engine's iso-reliability row: price, bps | 37.937500 | 37.937500 | pass |
| Bearer split sums to the self-insured cost: largest absolute gap, bps | 0.000000 | 0.000000 | pass |

## 3. The risk the balance carries

Self-insured cost of the uninsured balance, the clearing-cost engine's credit + access terms (no transfer cost):

| Measure | Credit | Access | Self-insured (credit + access) |
|---|---|---|---|
| Q (mu 3), pricing | 18.75 | 1.99 | 20.74 |
| P (mu 1), real world | 6.25 | 0.66 | 6.91 |

Every route below either prices this risk, moves it to someone who does not charge for it, or removes the balance.

## 4. The price list

One row per priced variant. 'Basis' says whether the figure is a model number or a reported or assumed range; reported figures are not model numbers. The t(5) column re-prices the same design under the Student-t(5) copula.

| Route | Variant | Price (bps a year) | t(5) price | Basis | Source |
|---|---|---|---|---|---|
| R1 | Pledged from securities already held | 10.0 to 30.0 (base 20.0) | n/a (no failure payoff) | author assumption | Chapter 4 |
| R1 | Securities bought for the purpose (150.0 to 300.0 spread on 110%) | 165.0 to 330.0 (base 247.5) | n/a (no failure payoff) | author assumption | Chapter 4 |
| R2 | Public-unit fee by district, standard structures | 10.5 to 18.0 (base 14.3) | n/a (no failure payoff) | reported figure | FHLBank Des Moines 2026; FHLBank San Francisco 2025; FHLBank Boston 2022; FHLBank Topeka 2023 |
| R3 | Placement fee plus rate uplift (base 10.0) | 12.5 to 37.5 (base 22.5) | n/a (insured by the FDIC) | reported figure (fee); author assumption (uplift) | Chain Bridge Bancorp 2026 |
| R4 | Replacement spread on each dollar replaced | 50.0 to 300.0 (base 175.0) | n/a (no failure payoff) | author assumption | Chapter 3 |
| R5 | Single-name funded vehicle | 45.74 | 45.74 (no copula) | model number | clearing_cost.py |
| R5 | Pooled all-funded reference design (theta 20%, 50 banks) | 37.74 | 37.74 (same design under t(5)) | model number | clearing_cost.py |
| R5 | Pooled, capacity sized to the S5 standard (11 failures, theta 22%; results_clearing_cost.md, Section 38) | 37.94 | 37.94 (same design under t(5)) | model number | clearing_cost.py |
| R6 | Reference design: X 10.0% for the Gaussian 1% standard, q_acq 0.5 | 21.03 | 23.02 (same design under t(5)) | model number | mutual_tail.py |
| R6 | Alternative design: X 21.8% for the Student-t(5) 5% standard | 31.01 | 33.73 (same design under t(5)) | model number | mutual_tail.py |
| R7 | Facility at a 20% always-on share, 2% haircut | 10.0 to 34.0 (base 22.0) | n/a (no failure payoff) | author assumption (illustrative) | Chapter 6 |
| R8 | R6 reference design + R7 less the shared-infrastructure saving | 29.7 to 55.0 (base 41.8) | 43.83 (R6 under t(5) + R7) | model number + author assumption | mutual_tail.py; Chapter 6 |
| R9 | Joint-account position at a 20% prefunded share, balance earning interest | 13.6 to 37.1 (base 25.4) | n/a (no failure payoff) | author assumption (illustrative) | this engine (section 1, R9 block) |

Reading the reported routes: R2's fee leaves the risk unpriced; fee plus the risk the super-lien moves to the fund is 31.2 to 38.7 under Q (17.4 to 24.9 under P) [author's reading]. R3 by uplift: uplift 0.0 gives 12.5; uplift 10.0 gives 22.5; uplift 25.0 gives 37.5. R4's spread applies to each dollar replaced, on the whole balance if it all leaves. R7 is a different product (liquidity outside funding-market hours), shown on the same scale for comparison only.

R9 is a second liquidity product, priced from the author assumptions of the R9 block and shown on the same scale for comparison only.

## 5. Lendable share and capacity consumed

| Route | Variant | Lendable share | Capacity consumed ($100m balance) |
|---|---|---|---|
| R1 | Pledged from securities already held | 0.00 | $110m of high-quality liquid assets, encumbered |
| R1 | Securities bought for the purpose (150.0 to 300.0 spread on 110%) | 0.00 | $110m of securities bought and pledged |
| R2 | Public-unit fee by district, standard structures | 1.00 | $100m of FHLB borrowing capacity, and the collateral behind it |
| R3 | Placement fee plus rate uplift (base 10.0) | 1.00 | The non-brokered allowance (tiered, up to $30bn) |
| R4 | Replacement spread on each dollar replaced | 0.00 | None (the balance has left) |
| R5 | Single-name funded vehicle | 1.00 | The provider's buffer, 100% of the balance; none of the bank's |
| R5 | Pooled all-funded reference design (theta 20%, 50 banks) | 1.00 | The provider's buffer, 20% of covered notional; none of the bank's |
| R5 | Pooled, capacity sized to the S5 standard (11 failures, theta 22%; results_clearing_cost.md, Section 38) | 1.00 | The provider's buffer, 22% of covered notional; none of the bank's |
| R6 | Reference design: X 10.0% for the Gaussian 1% standard, q_acq 0.5 | 0.97 | 3% capital contribution and a call of up to 2 x the assessment; the reciprocal allowance for the base |
| R6 | Alternative design: X 21.8% for the Student-t(5) 5% standard | 0.97 | 3% capital contribution and a call of up to 2 x the assessment |
| R7 | Facility at a 20% always-on share, 2% haircut | 0.80 | $20.4m of Treasury bills positioned each weekend |
| R8 | R6 reference design + R7 less the shared-infrastructure saving | 0.77 | Both of the above |
| R9 | Joint-account position at a 20% prefunded share, balance earning interest | 0.80 | $20.0m of reserves held in the joint account at all times |

R6's lendable share counts the member's 3% capital contribution, held in bills at the mutual, as not lendable; R7's counts the always-on tier, matched one for one by bills, as not lendable [author's reading].

R9's counts the prefunded position, reserves held in the joint account, as not lendable (lendable share 1 minus the prefunded share, 0.80); a top-up from the master account draws reserves the bank also cannot lend.

## 6. Who bears the risk

Where each route puts the self-insured cost of Section 3, bps a year on the balance, under Q and under P. All attributions are the author's reading. R6's rule-M access sits with the receivership, which carries the recovery of the excess when an acquirer takes every deposit at closure; R5 pooled's depositor share is the expected loss and access on par the buffer cannot pay.

Under Q:

| Route variant | Depositor | Bank's own encumbered collateral | Deposit insurance fund | FHLB super-lien | Private buffer | Mutual members | Leaves with the balance | Total |
|---|---|---|---|---|---|---|---|---|
| R1 | 0.00 | 20.74 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 20.74 |
| R2 | 0.00 | 0.00 | 0.00 | 20.74 | 0.00 | 0.00 | 0.00 | 20.74 |
| R3 | 0.00 | 0.00 | 20.74 | 0.00 | 0.00 | 0.00 | 0.00 | 20.74 |
| R4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 20.74 | 20.74 |
| R5 single | 0.00 | 0.00 | 0.00 | 0.00 | 20.74 | 0.00 | 0.00 | 20.74 |
| R5 pooled | 0.03 | 0.00 | 0.00 | 0.00 | 20.71 | 0.00 | 0.00 | 20.74 |
| R5 sized | 0.02 | 0.00 | 0.00 | 0.00 | 20.72 | 0.00 | 0.00 | 20.74 |
| R6 | 0.01 | 0.00 | 0.99 | 0.00 | 0.55 | 19.19 | 0.00 | 20.74 |
| R6 alt | 0.00 | 0.00 | 0.99 | 0.00 | 0.49 | 19.26 | 0.00 | 20.74 |
| R7 | 20.74 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 20.74 |
| R8 | 0.01 | 0.00 | 0.99 | 0.00 | 0.55 | 19.19 | 0.00 | 20.74 |
| R9 | 20.74 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 20.74 |

Under P:

| Route variant | Depositor | Bank's own encumbered collateral | Deposit insurance fund | FHLB super-lien | Private buffer | Mutual members | Leaves with the balance | Total |
|---|---|---|---|---|---|---|---|---|
| R1 | 0.00 | 6.91 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 |
| R2 | 0.00 | 0.00 | 0.00 | 6.91 | 0.00 | 0.00 | 0.00 | 6.91 |
| R3 | 0.00 | 0.00 | 6.91 | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 |
| R4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 | 6.91 |
| R5 single | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 | 0.00 | 0.00 | 6.91 |
| R5 pooled | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 | 0.00 | 0.00 | 6.91 |
| R5 sized | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 | 0.00 | 0.00 | 6.91 |
| R6 | 0.00 | 0.00 | 0.33 | 0.00 | 0.05 | 6.54 | 0.00 | 6.91 |
| R6 alt | 0.00 | 0.00 | 0.33 | 0.00 | 0.04 | 6.54 | 0.00 | 6.91 |
| R7 | 6.91 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 |
| R8 | 0.00 | 0.00 | 0.33 | 0.00 | 0.05 | 6.54 | 0.00 | 6.91 |
| R9 | 6.91 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 6.91 |

Who pays when the risk is moved rather than priced: R2 moves 6.91 bps a year under P (20.74 under Q) to the deposit insurance fund through the FHLB super-lien; R7 moves up to 1.38 under P (4.15 under Q) through the safe-harbored repo, an upper bound that assumes every failure follows a weekend in which the capped outflow left; R4 moves the cost to borrowers or shareholders through the replacement spread. R3 puts the risk on the fund against assessments, a priced public cover.

## 7. Route detail

R7, the four terms at the illustrative inputs (bps a year on the whole tokenized balance; per tier dollar = divided by the always-on share):

| Term | Low | High |
|---|---|---|
| Credit | 0.0 | 1.0 |
| Access | 2.0 | 5.0 |
| Capacity | 5.0 | 20.0 |
| Frictions | 3.0 | 8.0 |
| Facility price, whole balance | 10.0 | 34.0 |
| Facility price, per always-on tier dollar | 50.0 | 170.0 |
| Memo: bank committed facility cost floor on the undrawn amount (Chapter 3) | 55.4 | 117.0 |

Bills positioned: 20.41% of the tokenized balance (the 20% share grossed up for the 2% haircut). The usage charge between net debtors and net creditors nets to zero across members and is not in the price.

R7 by always-on share (the standing-capacity term scales with the share, the others do not):

| Always-on share | Price, whole balance | Per tier dollar | Lendable share | S2 |
|---|---|---|---|---|
| 5% | 6.3 to 19.0 | 125.0 to 380.0 | 0.95 | pass |
| 7% | 6.8 to 21.0 | 96.4 to 300.0 | 0.93 | pass |
| 10% | 7.5 to 24.0 | 75.0 to 240.0 | 0.90 | pass |
| 20% | 10.0 to 34.0 | 50.0 to 170.0 | 0.80 | fail |
| 35% | 13.8 to 49.0 | 39.3 to 140.0 | 0.65 | fail |
| 50% | 17.5 to 64.0 | 35.0 to 128.0 | 0.50 | fail |

How often the cap binds (illustrative): weekend net outflow as a share of the always-on tier, lognormal with median 25%; the cap binds when the outflow exceeds the tier. Per year assumes 52 independent weekends; serial dependence across weekends is not modelled. Monte Carlo check: 1,000,000 draws, seed 20261110.

| sigma | P(cap binds) per weekend | Weekends a year it binds (mean) | P(binds at least once a year) | Monte Carlo per weekend (z) |
|---|---|---|---|---|
| 0.5 | 0.278% | 0.14 | 13.5% | 0.274% (-0.82) |
| 0.8 | 4.156% | 2.16 | 89.0% | 4.100% (-2.83) |
| 1.2 | 12.399% | 6.45 | 99.9% | 12.364% (-1.09) |

R8, the shared-infrastructure saving. The smaller structure's access term is the smaller of R6's access (0.37, the clearing-cost engine's four-term access) and R7's (2.0 to 5.0), so 0.37 [author assumption]. The credit tranche and the liquidity tranche share a ledger and no reserve.

| Share of the access term saved | Saving | R8 price, whole balance | Memo: saving if R7's membership access (2.0 to 5.0) is the term |
|---|---|---|---|
| none (no frictions saved either) | 0.00 | 31.0 to 55.0 | 0.00 to 0.00 |
| 50% | 1.19 | 29.8 to 53.8 | 2.00 to 3.50 |
| 100% | 1.37 | 29.7 to 53.7 | 3.00 to 6.00 |

R8 range reported: 29.7 to 55.0 (base 41.8); under t(5), R6's price becomes 23.02.

R9, prefunded joint-account instant settlement (the design of The Clearing House RTP network), the four terms at the illustrative inputs of the R9 block, at a 20% prefunded share (bps a year on the whole tokenized balance). An operator holds a joint account at a Reserve Bank; each member prefunds its position during Fedwire hours; weekend transfers between members settle instantly and finally against positions in central bank money; positions can be topped up at any hour by FedNow liquidity management transfers from the member's master account (RTP Operating Rules effective 1 November 2026 allow weekend funding by liquidity management transfer where the participant enables it, and defunding by the same route while Fedwire is closed; FedNow Operating Circular 8, Section 9.7.1, allows such transfers for an instant payment system backed by a joint account); a payment beyond the sender's position is rejected, not queued. Capacity is the opportunity cost of reserves held in the joint account instead of loans, measured against bills: the prefunded share times the loan spread over bills (25.0 to 100.0) plus the bill yield over IORB (23.0 at 4.13% and 3.90%) when the balance earns IORB, or plus the whole bill yield when it earns nothing. Base: the balance earns IORB (the RTP joint account's treatment). The prefunded slice is not counted as HQLA in the base.

| Term | Low | High | Memo: low, balance earning no interest | Memo: high |
|---|---|---|---|---|
| Credit | 0.0 | 0.5 | 0.0 | 0.5 |
| Access | 2.0 | 6.0 | 2.0 | 6.0 |
| Capacity | 9.6 | 24.6 | 87.6 | 102.6 |
| Frictions | 2.0 | 6.0 | 2.0 | 6.0 |
| Price, whole balance | 13.6 | 37.1 | 91.6 | 115.1 |
| Price, per prefunded dollar | 68.0 | 185.5 | 458.0 | 575.5 |

R9 by prefunded share (lendable share 1 minus the share, the absolute convention):

| Prefunded share | Price, whole balance | Memo: balance earning no interest | Lendable share | S2 |
|---|---|---|---|---|
| 5% | 6.4 to 18.7 | 25.9 to 38.2 | 0.95 | pass |
| 7% | 7.4 to 21.1 | 34.7 to 48.4 | 0.93 | pass |
| 10% | 8.8 to 24.8 | 47.8 to 63.8 | 0.90 | pass |
| 20% | 13.6 to 37.1 | 91.6 to 115.1 | 0.80 | fail |
| 35% | 20.8 to 55.6 | 157.3 to 192.1 | 0.65 | fail |
| 50% | 28.0 to 74.0 | 223.0 to 269.0 | 0.50 | fail |

At a 20% prefunded share R9's base price is 25.35 with the balance earning interest and 103.35 with it earning no interest, against R7's 22.00. At equal shares R9's base is below R7's only at a share below 5.4%, because the bill yield over IORB adds to the loan spread.

Memo: R7's Sunday settlement cash. At the Sunday 21:00 Fedwire Funds opening a net debtor settles in reserves and needs capacity of at least its cap, the 20% always-on share. R7's published price assumes case (a); cases (b1) and (b2) add the cost of that capacity, on this engine's own constants. The bills' haircut gross-up (0.20 / 0.98) is not charged again: it sits in frictions.

| R7 Sunday settlement cash | Range, whole balance | Base | Lendable share (absolute) | Base by share s (bps) | Against R9 at equal shares |
|---|---|---|---|---|---|
| (a) Reserve Bank credit against loans already pledged, within net debit cap headroom (published) | 10.0 to 34.0 | 22.00 | 0.80 | 9.50 + 62.5s | R9 cheaper below a share of 5.43% |
| (b1) Securities bought and pledged at the Reserve Bank, at R7's encumbrance spread | 15.0 to 54.0 | 34.50 | 0.60 | 9.50 + 125.0s | R9 cheaper at every share |
| (b2) Reserves held for the Sunday opening, on R9's reserve convention (loan spread over bills + bill over IORB) | 19.6 to 58.6 | 39.10 | 0.60 | 9.50 + 148.0s | R9 cheaper at every share |
| R9 (published) | 13.6 to 37.1 | 25.35 | 0.80 | 8.25 + 85.5s |  |

In case (a) R9 crosses R7 at a share of 5.43%, as above. In cases (b1) and (b2) R7 has the higher intercept and the steeper slope, so R9 is cheaper at every share. At the published 20% share R9's base (25.35) is below R7's once 19.6% of the Sunday capacity comes from new reserves, or 26.8% from bought securities, the rest from loans already pledged at the Reserve Bank.

Rejection, not queueing. Without a weekend top-up a payment is rejected when the member's weekend peak debit (lognormal, median 5.0% of the balance, sigma 0.8, the routes engine's outflow) passes its position. A top-up by liquidity management transfer (up to $500 million each) lowers the rejection rate only by drawing master-account reserves the bank also cannot lend.

| Prefunded share | P(a payment is rejected) per weekend | Expected rejected amount, share of the balance | Lendable share |
|---|---|---|---|
| 5% | 50.000% | 2.9269% | 0.95 |
| 7% | 33.703% | 2.1014% | 0.93 |
| 10% | 19.313% | 1.3292% | 0.90 |
| 20% | 4.156% | 0.3769% | 0.80 |
| 35% | 0.750% | 0.0907% | 0.65 |
| 50% | 0.200% | 0.0298% | 0.50 |

## 8. Screens

Verdicts are pass, fail, open (a question the sources do not settle) or n/a, each with a one-line reason and its source. S5 is computed for R5, R6 and R8, passes by construction for R3 and is n/a where the route has no failure payoff.

| Screen | Definition |
|---|---|
| S1 | Open to a private corporate depositor at a national bank |
| S2 | Lendable share at least 0.9 |
| S3 | Cover continues, and can grow, below well capitalized or at CAMELS 4 |
| S4 | No hidden public subsidy |
| S5 | Pays in full with probability at least 99% in the year the depositor's own bank fails (Gaussian, rho 0.30) |

| Variant | S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|---|
| R1 held | fail | fail | pass | open | n/a |
| R2 | open | pass | open | fail | n/a |
| R3 | pass | pass | fail | pass | pass |
| R4 | pass | fail | n/a | pass | n/a |
| R5 single | pass | pass | pass | pass | pass |
| R5 pooled | pass | pass | pass | pass | fail |
| R5 sized | pass | pass | pass | pass | pass |
| R6 | open | pass | pass | pass | pass |
| R6 alt | open | pass | pass | pass | pass |
| R7 | pass | fail | pass | open | n/a |
| R8 | open | fail | pass | open | pass |
| R9 | open | fail | pass | pass | n/a |

Reasons and sources (R1 bought shares R1 held's verdicts):

| Variant | Screen | Verdict | Reason | Source |
|---|---|---|---|---|
| R1 held | S1 | fail | National banks lack the power to pledge assets to secure a private deposit; the exceptions cover public funds, tribes and trust funds | Chapter 4 (Texas and Pacific Railway Co. v. Pottorff, 291 U.S. 245 (1934); 12 U.S.C. 90; 12 U.S.C. 92a(d)) |
| R1 held | S2 | fail | Lendable share about 0: the deposit funds its own collateral | Chapter 4 |
| R1 held | S3 | pass | A perfected pledge does not lapse when the bank's capital category or rating falls [author's reading] | author's reading |
| R1 held | S4 | open | The pledge puts the depositor ahead of the fund; at a lendable share of 0 the deposit funds its own collateral and the fund loses nothing net, but a pledge from securities already held subordinates it [author's reading] | Chapters 4 and 5 |
| R1 held | S5 | n/a | No failure payoff for the engine to price; the pledge pays from collateral at 110 percent | Chapter 4 |
| R2 | S1 | open | The regulation does not restrict the beneficiary; the FHLBanks' public-unit product terms do, and a letter backed by the member's pledged assets raises the Pottorff question | Chapter 4 (12 CFR 1269.2; FHLBank Boston 2022; Pottorff) |
| R2 | S2 | pass | Lendable share about 1: the deposit stays on the balance sheet and funds loans | Chapter 4 |
| R2 | S3 | open | An issued letter runs to its term; a new or larger letter for a weakened member turns on the FHLBank's credit and collateral terms, which tighten as the member weakens [author's reading] | author's reading; Chapter 4 (12 CFR 1269.2(b)) |
| R2 | S4 | fail | The FHLBank's lien outranks the receiver, so the letter's risk lands on the deposit insurance fund, unpriced in the fee: 6.9 bps a year under P, 20.7 under Q | Chapter 4 (12 U.S.C. 1430(e)) |
| R2 | S5 | n/a | Pays in full while the FHLBank's collateral holds; no failure payoff for the engine to price | Chapter 4 |
| R3 | S1 | pass | Open to a private corporation; the account becomes a set of insured accounts at other banks | Chapter 4 |
| R3 | S2 | pass | Lendable share about 1: matched placement returns an equal balance | Chapter 4 |
| R3 | S3 | fail | Below well capitalized or at CAMELS 4 the bank keeps what it holds up to a special cap but may not grow; growth past it makes every reciprocal deposit brokered; the rate cap applies | Chapter 5 (12 U.S.C. 1831f(i); 12 CFR 337.6; 12 CFR 337.7) |
| R3 | S4 | pass | A priced public cover: FDIC insurance against the assessments the banks pay, not a hidden subsidy; the fund's exposure to large corporate balances grows with the layer | Chapter 5 |
| R3 | S5 | pass | FDIC-insured within the cap: pays in full by construction | Chapter 4 (12 CFR 337.6(e)) |
| R4 | S1 | pass | Always open: the depositor sweeps to a fund, a tokenized Treasury fund or a stablecoin | Chapter 4 |
| R4 | S2 | fail | Lendable share 0: the dollar has left | Chapter 4 |
| R4 | S3 | n/a | No cover to continue; the balance has left | Chapter 4 |
| R4 | S4 | pass | No public party bears the risk; the cost falls on borrowers or shareholders through the replacement spread | Chapters 3 and 4 |
| R4 | S5 | n/a | No failure payoff; the balance is no longer at the bank | Chapter 4 |
| R5 single | S1 | pass | Open in principle in the depositor-paid wrapper, where the bank is not a party; the licensing and dealer-registration questions are general, not charter-specific; no such vehicle exists | Chapters 3 and 4 |
| R5 single | S2 | pass | Lendable share 1: the buffer is the provider's | Chapter 4 |
| R5 single | S3 | pass | Annual contract; pre-agreed step-ups move a weakening bank up the pricing grid rather than cutting it off | Chapter 3 (term sheet) |
| R5 single | S4 | pass | No public party bears the loss; the buffer is paid for by the premium | Chapter 4 |
| R5 single | S5 | pass | Fully funded single name: pays par in every state (shortfall 0) | clearing_cost.py |
| R5 pooled | S5 | fail | P(not paid in full given own bank fails) 1.01%: paid in full 98.99% | computed (clearing_cost.py or mutual_tail.py) |
| R5 sized | S5 | pass | P(not paid in full given own bank fails) 0.72%: paid in full 99.28% | computed (clearing_cost.py or mutual_tail.py) |
| R6 | S1 | open | The design sets no charter limit and nothing is pledged, so Pottorff does not bite; whether a national bank may make the entry capital contribution to a state-licensed mutual insurer is an open counsel question [author's reading] | Chapter 5 |
| R6 | S2 | pass | Lendable share 0.97: the member's 3% capital contribution sits in Treasury bills at the mutual [author's reading] | Chapter 5; mutual_tail.py parameters |
| R6 | S3 | pass | Cover turns on the mutual's own covenants, not the member's capital category; covered excess grows within the tiered per-member cap and the growth covenant while the reciprocal base under it stops | Chapter 5 |
| R6 | S4 | pass | Members and tail investors pay for the risk to X; rule M asks the receivership to carry the recovery of the excess at closure (0.99 bps a year under Q), a timing cost the FDIC carries in any all-deposit purchase and assumption; expected loss above X 0.00 bps [author's reading] | Chapter 5; mutual_tail.py |
| R6 | S5 | pass | P(not paid in full given own bank fails) 0.99%: paid in full 99.01% | computed (clearing_cost.py or mutual_tail.py) |
| R6 alt | S5 | pass | P(not paid in full given own bank fails) 0.032%: paid in full 99.97% | computed (clearing_cost.py or mutual_tail.py) |
| R7 | S1 | pass | The bank pledges bills to other member banks for its own net debits, not to secure the deposit; a corporation reaches the facility through its member bank [author's reading] | Chapter 6 |
| R7 | S2 | fail | Lendable share 0.80: each always-on tier dollar is matched by a bill the bank cannot lend; S2 holds only at an always-on share of 10% or less | Chapter 6 |
| R7 | S3 | pass | The cap rests on the member's own pledged bills, with no capital condition; the design expects a weak bank to use it and slows it through the cap | Chapter 6 |
| R7 | S4 | open | Safe-harbored repo puts net creditors ahead of the receiver for the capped weekend outflow: an upper bound of 1.38 bps a year under P, 4.15 under Q, on the whole balance; a weekday run through Fedwire moves the same loss with no cap [author's reading] | Chapter 6 (12 U.S.C. 1821(e)(8) to (10)) |
| R7 | S5 | n/a | Liquidity, not credit: the facility does nothing for the balance if the bank fails | Chapter 6 |
| R8 | S1 | open | Inherits R6's open question on the capital contribution | R6 |
| R8 | S2 | fail | Lendable share 0.77 (3% capital contribution plus the 20% always-on tier); S2 holds only at an always-on share of 7% or less | R6; R7 |
| R8 | S3 | pass | Both tranches pass | R6; R7 |
| R8 | S4 | open | Inherits R7's open question on the safe-harbored repo | R7 |
| R8 | S5 | pass | The credit tranche is R6's reference design and no reserve is shared: 0.99% short | Chapter 6; mutual_tail.py |
| R9 | S1 | open | A corporation reaches the arrangement through its member bank and nothing is pledged for the deposit, so Pottorff does not bite, and the operator need not be a bank; but a new joint account needs Reserve Bank approval under the Board's 2017 guidelines, not yet sought. Scored open, the scale's verdict for an approval or opinion the sources do not settle, as for R2's and R6's S1 [author's reading] | Board guidelines for evaluating joint account requests (82 FR 41951, 2017); FedNow Operating Circular 8, Section 9.7.1 |
| R9 | S2 | fail | Lendable share 0.80: each prefunded dollar is a reserve balance in the joint account the bank cannot lend, and in the base it is not counted as HQLA either (no public statement on its liquidity coverage treatment); S2 holds only at a prefunded share of 10% or less | this engine; absolute convention |
| R9 | S3 | pass | The position is the member's own prefunded central bank money, with no capital condition in the design; a Reserve Bank's account-risk controls on a troubled member bind every route that settles in central bank money, R7 included [author's reading] | author's reading |
| R9 | S4 | pass | Prefunded and final in central bank money: no secured priority over the receiver and no Reserve Bank credit; if a member is closed, its unspent position passes to the receiver [author's reading] | author's reading |
| R9 | S5 | n/a | Liquidity, not credit: the arrangement does nothing for the balance if the bank fails | this engine |

## 9. The rule: champion and challenger

Rule [author assumption, stated before the numbers]: among routes passing every applicable screen, the champion is the cheapest all-in price (base of the route's range) and the challenger the next cheapest route; variants of one route compete inside the route first. An 'open' verdict is not a pass. The rule is also run with every open item resolved in the route's favor, to show what the open items decide. Applicable screens: S1 to S5 for problem (a) and for both together; S1, S3 and S4 for problem (b), whose objective is movement, not lendable funding or failure cover (convention for the author to confirm; the result with S2 also applied to (b) is shown).

| Problem | Reading | Champion | Challenger (next route) | Next-cheapest passing variant |
|---|---|---|---|---|
| (a) keep the balance as stable lendable funding through a failure | strict (open is not a pass) | R5 (Pooled, capacity sized to the S5 standard (11 failures, theta 22%; results_clearing_cost.md, Section 38)) at 37.94 bps | none | R5 (Single-name funded vehicle) at 45.74 bps |
| (a) keep the balance as stable lendable funding through a failure | open items resolved in the route's favor | R6 (Reference design: X 10.0% for the Gaussian 1% standard, q_acq 0.5) at 21.03 bps | R5 (Pooled, capacity sized to the S5 standard (11 failures, theta 22%; results_clearing_cost.md, Section 38)) at 37.94 bps | R6 (Alternative design: X 21.8% for the Student-t(5) 5% standard) at 31.01 bps |
| (b) move it outside funding-market hours | strict (open is not a pass) | none | none | none |
| (b) move it outside funding-market hours | open items resolved in the route's favor | R7 (Facility at a 20% always-on share, 2% haircut) at 22.00 bps | R9 (Joint-account position at a 20% prefunded share, balance earning interest) at 25.35 bps | R9 (Joint-account position at a 20% prefunded share, balance earning interest) at 25.35 bps |
| (a) and (b) together | strict (open is not a pass) | none | none | none |
| (a) and (b) together | open items resolved in the route's favor | none | none | none |

With S2 also applied to problem (b): strict: no route passes; open resolved: no route passes.

R9 in the rule: it applies to problem (b) only. Its S1 is open (Reserve Bank approval of a new joint account, under the Board's 2017 guidelines, not yet sought), so it does not qualify under the strict reading; with open items resolved it competes at its base 25.35. With the interest switch at its other setting (balance earning no interest, base 103.35), problem (b) gives: strict: champion none, challenger none; open resolved: champion R7 (Facility at a 20% always-on share, 2% haircut) at 22.00 bps, challenger R8 (R6 reference design + R7 less the shared-infrastructure saving) at 41.84 bps.

Memo, R7's Sunday settlement cash (Section 7; R8, which contains R7, carries the same extra term), problem (b): strict: case (a): champion none, challenger none; case (b1): champion none, challenger none; case (b2): champion none, challenger none. Open items resolved: case (a): champion R7 at 22.00, challenger R9 at 25.35; case (b1): champion R9 at 25.35, challenger R7 at 34.50; case (b2): champion R9 at 25.35, challenger R7 at 39.10. Under the open-resolved reading the settlement champion is R7 in case (a) and R9 in case (b). The published rule above is case (a).

Champion and challenger beside what the Gaussian standard hides (P(not paid in full given own bank fails), rho 0.30):

| Route | Gaussian price | t(5) price, same design | Gaussian shortfall | t(5) shortfall |
|---|---|---|---|---|
| R5 sized (champion, strict) | 37.94 | 37.94 | 0.72% | 24.75% |
| R6 (champion, open resolved) | 21.03 | 23.02 | 0.99% | 20.19% |

Reliability of every computed design (S5 is the Gaussian column):

| Design | Price | t(5) price, same design | Gaussian: short | Gaussian: paid in full | t(5): short |
|---|---|---|---|---|---|
| R5 single-name | 45.74 | 45.74 | 0 (fully funded) | 100.00% | 0 (fully funded) |
| R5 pooled reference (20%) | 37.74 | 37.74 | 1.01% | 98.99% | 27.73% |
| R5 pooled sized to S5 (22%) | 37.94 | 37.94 | 0.72% | 99.28% | 24.75% |
| Memo: R5 pooled sized to t(5) 5% (50%) | 40.74 | 40.74 | 0.007% | 99.99% | 4.38% |
| R6 reference (X 10.0%) | 21.03 | 23.02 | 0.99% | 99.01% | 20.19% |
| R6 alternative (X 21.8%) | 31.01 | 33.73 | 0.032% | 99.97% | 4.95% |
| R8 (credit tranche = R6 reference) | 41.84 | 43.83 | 0.99% | 99.01% | 20.19% |

The clearing-cost engine's reference design misses S5 by 0.0084%: 10 failures of 2% leave 1.008% short. One more failure of capacity (11 in all) passes at 37.94 bps, 0.20 more. The clearing-cost engine's t(5) 5% design needs 25 failures (50%) at 40.74; the mutual's t(5) 5% design costs 31.01.

## 9b. S2 bar sensitivity

The rule of record keeps S2 at 0.90. This section re-scores S2 at bars of 0.75, 0.80, 0.85, 0.90 at the published route parameters and reruns the rule; nothing else moves. S2 applies to problem (a) and to (a) and (b) together; problem (b) as specified does not apply it, so its champion does not move with the bar, and the variant with S2 also applied to (b) is shown beside it. A bar below 0.90 is reasonable only if the route's encumbered bills or reserves can also be the bank's own liquidity buffer against the same deposit, a question this engine does not settle; if they cannot, the encumbrance stacks on the buffer and a lower bar overstates what the bank keeps lending. R7 is at its Sunday settlement cash case (a) (Section 7).

| Variant | Lendable share (absolute) | S2 at 0.75 | S2 at 0.80 | S2 at 0.85 | S2 at 0.90 |
|---|---|---|---|---|---|
| R1 held | 0.00 | fail | fail | fail | fail |
| R2 | 1.00 | pass | pass | pass | pass |
| R3 | 1.00 | pass | pass | pass | pass |
| R4 | 0.00 | fail | fail | fail | fail |
| R5 single | 1.00 | pass | pass | pass | pass |
| R5 pooled | 1.00 | pass | pass | pass | pass |
| R5 sized | 1.00 | pass | pass | pass | pass |
| R6 | 0.97 | pass | pass | pass | pass |
| R6 alt | 0.97 | pass | pass | pass | pass |
| R7 | 0.80 | pass | pass | fail | fail |
| R8 | 0.77 | pass | fail | fail | fail |
| R9 | 0.80 | pass | pass | fail | fail |

| Bar | Problem | Strict: champion | Strict: challenger | Open resolved: champion | Open resolved: challenger |
|---|---|---|---|---|---|
| 0.75 | (a) stable lendable funding | R5 sized at 37.94 | none | R6 at 21.03 | R5 sized at 37.94 |
| 0.75 | (b) movement outside funding-market hours | none | none | R7 at 22.00 | R9 at 25.35 |
| 0.75 | (b) with S2 also applied | none | none | R7 at 22.00 | R9 at 25.35 |
| 0.75 | (a) and (b) together | none | none | R8 at 41.84 | none |
| 0.80 | (a) stable lendable funding | R5 sized at 37.94 | none | R6 at 21.03 | R5 sized at 37.94 |
| 0.80 | (b) movement outside funding-market hours | none | none | R7 at 22.00 | R9 at 25.35 |
| 0.80 | (b) with S2 also applied | none | none | R7 at 22.00 | R9 at 25.35 |
| 0.80 | (a) and (b) together | none | none | none | none |
| 0.85 | (a) stable lendable funding | R5 sized at 37.94 | none | R6 at 21.03 | R5 sized at 37.94 |
| 0.85 | (b) movement outside funding-market hours | none | none | R7 at 22.00 | R9 at 25.35 |
| 0.85 | (b) with S2 also applied | none | none | none | none |
| 0.85 | (a) and (b) together | none | none | none | none |
| 0.90 | (a) stable lendable funding | R5 sized at 37.94 | none | R6 at 21.03 | R5 sized at 37.94 |
| 0.90 | (b) movement outside funding-market hours | none | none | R7 at 22.00 | R9 at 25.35 |
| 0.90 | (b) with S2 also applied | none | none | none | none |
| 0.90 | (a) and (b) together | none | none | none | none |

| Bar | R7: largest always-on share | R8: largest always-on share (with the 3% capital contribution) | R9: largest prefunded share |
|---|---|---|---|
| 0.75 | 25% | 22% | 25% |
| 0.80 | 20% | 17% | 20% |
| 0.85 | 15% | 12% | 15% |
| 0.90 | 10% | 7% | 10% |

Variants failing S2, by bar: 0.75: R1 held, R4; 0.80: R1 held, R4, R8; 0.85: R1 held, R4, R7, R8, R9; 0.90: R1 held, R4, R7, R8, R9. With R7's Sunday settlement cash in case (b1) or (b2) its lendable share is 0.60, which fails S2 at every bar in the grid.

Check: at this run's bar (0.90) the table reproduces Section 9: yes.

## 10. Dollars for two banks

| Bank | Liabilities | Covered excess (20% of liabilities) | Reciprocal allowance | Allowance / liabilities | Marginal tier | Headroom over covered excess | Mutual capital contribution (3%) |
|---|---|---|---|---|---|---|---|
| $50bn bank | $45.00bn | $9.00bn | $14.60bn | 32.4% | 30% | $5.60bn | $270m |
| $5bn community bank | $4.50bn | $0.90bn | $1.90bn | 42.2% | 40% | $1.00bn | $27m |

The reciprocal tier changes the arithmetic: the allowance is 32.4% of liabilities at the $50bn bank (marginal tier 30%) and 42.2% at the $5bn bank (marginal tier 40%), so at a 20% covered share neither binds; the cap binds once reciprocal holdings pass 32.4% and 42.2% of liabilities, beyond which placements are brokered. Existing reciprocal holdings use the same allowance. Fees in bps are the same at both banks; the fixed-cost terms (R5 frictions, R7 access, the mutual's f_m) would be dearer per dollar at the small bank, which this table does not model.

Annual cost of each route on the covered excess, $ million a year (low to high, base):

| Route | Variant | $50bn bank | $5bn community bank |
|---|---|---|---|
| R1 | Pledged from securities already held | 9.0 to 27.0 (18.0) | 0.9 to 2.7 (1.8) |
| R1 | Securities bought for the purpose (150.0 to 300.0 spread on 110%) | 148.5 to 297.0 (222.8) | 14.9 to 29.7 (22.3) |
| R2 | Public-unit fee by district, standard structures | 9.5 to 16.2 (12.8) | 0.9 to 1.6 (1.3) |
| R3 | Placement fee plus rate uplift (base 10.0) | 11.2 to 33.8 (20.3) | 1.1 to 3.4 (2.0) |
| R4 | Replacement spread on each dollar replaced | 45.0 to 270.0 (157.5) | 4.5 to 27.0 (15.8) |
| R5 | Single-name funded vehicle | 41.2 | 4.1 |
| R5 | Pooled all-funded reference design (theta 20%, 50 banks) | 34.0 | 3.4 |
| R5 | Pooled, capacity sized to the S5 standard (11 failures, theta 22%; results_clearing_cost.md, Section 38) | 34.1 | 3.4 |
| R6 | Reference design: X 10.0% for the Gaussian 1% standard, q_acq 0.5 | 18.9 | 1.9 |
| R6 | Alternative design: X 21.8% for the Student-t(5) 5% standard | 27.9 | 2.8 |
| R7 | Facility at a 20% always-on share, 2% haircut | 9.0 to 30.6 (19.8) | 0.9 to 3.1 (2.0) |
| R8 | R6 reference design + R7 less the shared-infrastructure saving | 26.7 to 49.5 (37.7) | 2.7 to 5.0 (3.8) |
| R9 | Joint-account position at a 20% prefunded share, balance earning interest | 12.2 to 33.4 (22.8) | 1.2 to 3.3 (2.3) |

Replacement-cost ceiling and the depositor advantage that clears (the mutual model's Section 12 logic): protection clears when Delta + WTP + replacement value >= price. Full count: the replacement spread in full each year (the ceiling on what the bank should pay to keep the balance). Probability-weighted: dP_run x s_rep x the clearing-cost engine's five-year annuity (4.067). Minimum Delta in bps; the ceiling in $ million a year on each bank's covered excess.

| s_rep | Retention cell | Ceiling, $50bn bank ($m) | Ceiling, $5bn bank ($m) | Min Delta, full count: R5 sized (37.94) | Min Delta, weighted: R5 sized | Min Delta, full count: R6 (21.03) | Min Delta, weighted: R6 | Min Delta, full count: R5 single (45.74) | Min Delta, weighted: R5 single |
|---|---|---|---|---|---|---|---|---|---|
| 20.0 | none | 18.0 | 1.8 | 17.9 | 37.9 | 1.0 | 21.0 | 25.7 | 45.7 |
| 20.0 | V 100, dP_run 1% | 21.7 | 2.2 | 13.9 | 33.1 | 0.0 | 16.2 | 21.7 | 40.9 |
| 20.0 | V 150, dP_run 5% | 45.5 | 4.5 | 0.0 | 3.4 | 0.0 | 0.0 | 0.0 | 11.2 |
| 40.0 | none | 36.0 | 3.6 | 0.0 | 37.9 | 0.0 | 21.0 | 5.7 | 45.7 |
| 40.0 | V 100, dP_run 1% | 39.7 | 4.0 | 0.0 | 32.2 | 0.0 | 15.3 | 1.7 | 40.0 |
| 40.0 | V 150, dP_run 5% | 63.5 | 6.3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 7.1 |
| 60.0 | none | 54.0 | 5.4 | 0.0 | 37.9 | 0.0 | 21.0 | 0.0 | 45.7 |
| 60.0 | V 100, dP_run 1% | 57.7 | 5.8 | 0.0 | 31.4 | 0.0 | 14.5 | 0.0 | 39.2 |
| 60.0 | V 150, dP_run 5% | 81.5 | 8.1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 3.0 |
| 80.0 | none | 72.0 | 7.2 | 0.0 | 37.9 | 0.0 | 21.0 | 0.0 | 45.7 |
| 80.0 | V 100, dP_run 1% | 75.7 | 7.6 | 0.0 | 30.6 | 0.0 | 13.7 | 0.0 | 38.4 |
| 80.0 | V 150, dP_run 5% | 99.5 | 9.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

In dollars the depositor advantage that clears scales with the covered excess: at the $50bn bank each bp of Delta is $0.90m a year, at the $5bn bank $0.09m. Against them, letting the balance go and replacing it costs $45m to $270m a year at the $50bn bank and $4.5m to $27.0m at the $5bn bank.

## 10b. By deposit type: which clock, and what the routes cost

Not every deposit runs on both clocks. A plain account above the insured limit runs on the run clock only; a tokenized balance runs on the settlement clock whether it is insured or not, where its transfers are netted between banks; a tokenized balance above the limit runs on both. Each row is a priced variant of this list, open items resolved and S2 not applied (the strict R5 row excepted), so the table prices the risk each type carries and does not choose a route. For both clocks the routes stack: R8 is R6 plus R7 less the shared ledger, and R6 plus R9 is the pairing with no shared ledger, for which no saving is priced. Lendable shares are on the absolute convention, so the encumbrances add. bps a year on the whole balance, low to high with the base.

| Deposit | Clock(s) | Route on the list | Price (base) | Lendable share | Source |
|---|---|---|---|---|---|
| Insured, plain account | neither | none needed | 0 | 1.00 | the FDIC insures it |
| Uninsured, plain account | run | R6 mutual with tail, reference design | 21.03 | 0.97 | Table 9, open items resolved |
| Uninsured, plain account | run | R5 pooled vehicle sized to S5 (strict champion) | 37.94 | 1.00 | Table 9, strict |
| Insured, tokenized | settlement | R7 facility, Sunday cash case (a) | 10.0 to 34.0 (22.00) | 0.80 | Table 9, open items resolved |
| Insured, tokenized | settlement | R9 joint account | 13.6 to 37.1 (25.35) | 0.80 | Table 9, challenger |
| Insured, tokenized | settlement | R7 facility, Sunday cash case (b1) | 15.0 to 54.0 (34.50) | 0.60 | Section 7 memo |
| Insured, tokenized | settlement | R7 facility, Sunday cash case (b2) | 19.6 to 58.6 (39.10) | 0.60 | Section 7 memo |
| Uninsured, tokenized | both | R8 one ledger (R6 + R7, Sunday cash case (a)) | 29.7 to 55.0 (41.84) | 0.77 | Table 6 |
| Uninsured, tokenized | both | R6 + R9, no shared ledger | 34.6 to 58.1 (46.38) | 0.77 | this section |
| Uninsured, tokenized | both | R8 one ledger, Sunday cash case (b1) | 34.7 to 75.0 (54.34) | 0.57 | this section |
| Uninsured, tokenized | both | R8 one ledger, Sunday cash case (b2) | 39.3 to 79.6 (58.94) | 0.57 | this section |

The self-insured cost of the run clock alone, with nothing for moving it, is 20.74 bps under the pricing measure and 6.91 under the real-world measure (Section 3); it is the charge a plain uninsured account carries with no route bought, and the settlement clock adds its own capacity cost to it on a tokenized balance.

| Sunday settlement cash | Cheapest route for both clocks | Price (base) | Lendable share | Added by the settlement clock over R6, bps | Lendable share lost to it |
|---|---|---|---|---|---|
| (a) | R8 one ledger (R6 + R7, Sunday cash case (a)) | 41.84 | 0.77 | 20.81 | 0.20 |
| (b1) | R6 + R9, no shared ledger | 46.38 | 0.77 | 25.35 | 0.20 |
| (b2) | R6 + R9, no shared ledger | 46.38 | 0.77 | 25.35 | 0.20 |

Check: the R8 row reproduces R6 plus R7 less the shared-ledger saving, and its lendable share R6's less the always-on share: yes.

## 11. Sensitivities on the champion

One input at a time from the base; each case re-sizes capacity to the S5 standard (Gaussian, rho 0.30, 1%), so the price carries the cost of staying at the standard. The rho row moves the pricing correlation only; the S5 standard stays at rho 0.30 by its definition. For R6 the mutual's inputs move over the mutual model's ranges; for R5 the analogues are the vehicle's lock-up premium and frictions over the clearing-cost engine's ranges. R5's price does not move with the pricing rho: with fixed LGD and no facility, its credit and access are expectations that the correlation does not change.

R5 (strict champion):

| Input | Value | Failures covered | Capacity | Price | Gaussian short |
|---|---|---|---|---|---|
| lambda_P | 0.10% | 8 | 16% | 24.89 | 0.708% |
| lambda_P | 0.25% | 11 | 22% | 37.94 | 0.716% |
| lambda_P | 0.50% | 13 | 26% | 59.07 | 0.963% |
| lambda_P | 1.00% | 17 | 34% | 101.35 | 0.871% |
| mu | 2 | 11 | 22% | 31.02 | 0.716% |
| mu | 3 | 11 | 22% | 37.94 | 0.716% |
| mu | 4 | 11 | 22% | 44.85 | 0.716% |
| mu | 5 | 11 | 22% | 51.76 | 0.716% |
| LGD | 15% | 11 | 22% | 31.23 | 0.716% |
| LGD | 25% | 11 | 22% | 37.94 | 0.716% |
| LGD | 40% | 11 | 22% | 47.99 | 0.716% |
| rho (prices) | 0.10 | 11 | 22% | 37.94 | 0.716% |
| rho (prices) | 0.20 | 11 | 22% | 37.94 | 0.716% |
| rho (prices) | 0.30 | 11 | 22% | 37.94 | 0.716% |
| Lock-up premium s_lock | 5 bps | 11 | 22% | 36.84 | 0.716% |
| Lock-up premium s_lock | 10 bps | 11 | 22% | 37.94 | 0.716% |
| Lock-up premium s_lock | 15 bps | 11 | 22% | 39.04 | 0.716% |
| Frictions f | 10 bps | 11 | 22% | 32.94 | 0.716% |
| Frictions f | 15 bps | 11 | 22% | 37.94 | 0.716% |
| Frictions f | 20 bps | 11 | 22% | 42.94 | 0.716% |

Range of the price across each sweep, widest first:

| Input | Low | High | Spread |
|---|---|---|---|
| lambda_P | 24.89 | 101.35 | 76.46 |
| mu | 31.02 | 51.76 | 20.74 |
| LGD | 31.23 | 47.99 | 16.76 |
| Frictions f | 32.94 | 42.94 | 10.00 |
| Lock-up premium s_lock | 36.84 | 39.04 | 2.20 |
| rho (prices) | 37.94 | 37.94 | 0.00 |

R6 (champion with open items resolved):

| Input | Value | X | A | T | Mutual | Tail | All-in | Gaussian short |
|---|---|---|---|---|---|---|---|---|
| lambda_P | 0.10% | 7.0% | 3.282% | 3.718% | 10.63 | 3.48 | 14.10 | 0.99% |
| lambda_P | 0.25% | 10.0% | 3.421% | 6.579% | 14.54 | 6.50 | 21.03 | 0.99% |
| lambda_P | 0.50% | 13.1% | 3.635% | 9.465% | 20.97 | 10.79 | 31.76 | 0.98% |
| lambda_P | 1.00% | 17.1% | 4.070% | 13.030% | 33.61 | 19.89 | 53.50 | 0.99% |
| mu | 2 | 10.0% | 3.414% | 6.586% | 14.53 | 6.17 | 20.71 | 0.99% |
| mu | 3 | 10.0% | 3.421% | 6.579% | 14.54 | 6.50 | 21.03 | 0.99% |
| mu | 4 | 10.0% | 3.430% | 6.570% | 14.54 | 6.96 | 21.50 | 0.99% |
| mu | 5 | 10.0% | 3.442% | 6.558% | 14.54 | 7.57 | 22.11 | 0.99% |
| LGD | 15% | 10.0% | 3.366% | 6.634% | 12.11 | 6.19 | 18.29 | 0.98% |
| LGD | 25% | 10.0% | 3.421% | 6.579% | 14.54 | 6.50 | 21.03 | 0.99% |
| LGD | 40% | 10.0% | 3.510% | 6.490% | 18.13 | 7.39 | 25.52 | 0.99% |
| rho (prices) | 0.10 | 10.0% | 3.413% | 6.587% | 14.58 | 6.06 | 20.63 | 0.99% |
| rho (prices) | 0.20 | 10.0% | 3.421% | 6.579% | 14.54 | 6.50 | 21.03 | 0.99% |
| rho (prices) | 0.30 | 10.0% | 3.434% | 6.566% | 14.39 | 7.30 | 21.70 | 0.99% |
| Reserve opportunity cost | 50 bps | 10.0% | 3.391% | 6.609% | 13.03 | 6.51 | 19.54 | 0.99% |
| Reserve opportunity cost | 100 bps | 10.0% | 3.421% | 6.579% | 14.54 | 6.50 | 21.03 | 0.99% |
| Reserve opportunity cost | 150 bps | 10.0% | 3.450% | 6.550% | 16.04 | 6.49 | 22.52 | 0.99% |
| Mutual frictions f_m | 2 bps | 10.0% | 3.361% | 6.639% | 11.53 | 6.52 | 18.05 | 0.98% |
| Mutual frictions f_m | 5 bps | 10.0% | 3.421% | 6.579% | 14.54 | 6.50 | 21.03 | 0.99% |
| Mutual frictions f_m | 10 bps | 10.0% | 3.520% | 6.480% | 19.54 | 6.46 | 26.00 | 0.99% |

Range of the price across each sweep, widest first:

| Input | Low | High | Spread |
|---|---|---|---|
| lambda_P | 14.10 | 53.50 | 39.40 |
| Mutual frictions f_m | 18.05 | 26.00 | 7.95 |
| LGD | 18.29 | 25.52 | 7.22 |
| Reserve opportunity cost | 19.54 | 22.52 | 2.98 |
| mu | 20.71 | 22.11 | 1.40 |
| rho (prices) | 20.63 | 21.70 | 1.06 |

## 12. Conventions and limits

1. The engine prices only routes with a failure payoff. R1 to R4 carry the fee ranges of Chapter 4 (reported figures where a source is named, author assumptions otherwise) and the engine supplies what it can: the self-insured cost each route moves, lendable share and capacity.
2. Base price of a range is its midpoint; the rule ranks on base prices. Under the strict rule only model-priced routes qualify; with open items resolved, R7 and R8 compete for problem (b), and R8 contains R7, so R8 is dearer at every point of the range and the midpoint convention decides nothing in this run.
3. R5 is shown at three designs: single name (fully funded, never short), the clearing-cost engine's reference design and the clearing-cost engine's own iso-reliability row at the S5 standard, so that R5 and R6 are both sized to the same standard.
4. R6's price is per unit of covered excess (the excess not placed through the reciprocal network); the reciprocal base is R3 and is outside the model.
5. Who bears the risk is the author's reading of where the self-insured cost lands; amounts are expectations of the clearing-cost engine's credit and access terms under each measure.
6. R7's cap-binding figure treats weekends as independent and the outflow share as lognormal; Chapter 6 proposes a factor model with Gaussian and Student-t(5) factors, which is not built here.
7. Sensitivities re-size to the Gaussian standard at rho 0.30; the t(5) standard is reported beside the champion rather than re-sized in each case.
8. Fixed-cost scale effects at a small bank, FHLB activity-stock cost and the national-bank investment-power question on the mutual's capital contribution are not modelled.
9. R9's parameters sit in one labelled block: IORB, the bill rate, fees and limits are reported figures; the credit, access, loan spread and frictions ranges are author assumptions. The base follows the RTP joint account, whose balances earn IORB by a Board order specific to it; a new joint account without such an order earns nothing, shown as a sensitivity. R9 is sized at R7's 20% share for a like-for-like comparison; rejection is computed without weekend top-ups. The prefunded slice is not counted as HQLA.
