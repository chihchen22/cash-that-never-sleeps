# Cash That Never Sleeps, Chapter 6: the settlement clock of the always-on netting facility (settlement.py results)

Every number is illustrative and calibrated to no bank, facility or member. Parameters not imported from the routes engine are author assumptions (illustrative). Units: bps a year on the whole tokenized balance unless stated; shares are of the member's tokenized balance unless stated as a share of its always-on tier. Command: `python -I -B model/settlement.py` from the repository root. The script imports the routes engine (`model/routes.py`) by path, which loads the clearing-cost and mutual-tail engines, and copies no code from them. Seed: 20261120 (same-weekend Monte Carlo, 500,000 weekends); the imported engines carry their own. Run environment: Python 3.12.13, numpy 2.5.2; the run time is printed to the console and not written here, so two runs give the same file. Readings marked [author's reading] are readings, not findings of law.

The simulated variable is each member's PEAK net debit during the closed window to all counterparties, members and non-members, as a share of its always-on tier: the lognormal is the distribution of that peak, not of the terminal net position. Per-member results (bind probability, the per-member cap ladder rows, the median boundary) are the headline, conditional on the assumed distribution. Every multi-member statistic (system queue, joint cap ladder, any-binds, a quarter or more binding, the pooled cap, the system-average secured debit) describes an OPEN debtor cohort: members drawn as net debtors whose receivers sit outside the modelled set. It is not a closed-membership result, in which signed net positions would sum to zero.

## 1. Parameters

| Parameter | Value | Label |
|---|---|---|
| Always-on share; haircut on bills | 20%; 2% | imported from routes.py |
| R7 terms: credit; access; encumbrance spread; frictions | 0.0 to 1.0; 2.0 to 5.0; 25.0 to 100.0 on the bill slice; 3.0 to 8.0 | imported from routes.py |
| Weekend peak net debit (to all counterparties, members and non-members) / always-on tier | lognormal, median 25%, sigma 0.8 (set 0.5, 0.8, 1.2); 52 weekends a year | imported from routes.py |
| S2 threshold | lendable share at least 0.9 | imported from routes.py |
| Real-world default intensity of a member (lambda_P) | 0.25% a year | imported from routes.py (the clearing-cost engine's LAMBDA_P) |
| Student-t degrees of freedom | 5 | imported (the clearing-cost engine's) |
| Members M in the open debtor cohort | 20 (also 10, 40), equal size, receivers outside the modelled set | author assumption (illustrative) |
| Median peak debit for the sensitivity, share of the balance | 1.0%, 1.5%, 2.0%, 3.0%, 5.0% | author assumption (illustrative) |
| Pairwise latent correlation rho | 0.00, 0.15, 0.30, 0.50 | author assumption (illustrative) |
| Copulas | one-factor Gaussian and one-factor Student-t(5), same lognormal marginal | author assumption (illustrative) |
| Bind frequency targets for the cap ladder | 1% of weekends; once in ten years (1 in 520 weekends) | author assumption (illustrative) |
| Fedwire Funds hours | opens 21:00 ET on the preceding calendar day (holidays included); closes 19:00 ET on business days | reported figure, Federal Reserve Financial Services, Fedwire Funds Service and NSS operating hours, accessed 3 November 2026 |
| Reserve Bank weekday closings 2026 | Jan 01; Jan 19; Feb 16; May 25; Jun 19; Sep 07; Oct 12; Nov 11; Nov 26; Dec 25 (Jul 4 is a Saturday: open Friday, no weekday closing) | reported figure, Federal Reserve Financial Services, holiday schedules, accessed 3 November 2026 |
| Reserve Bank weekday closings 2027 | Jan 01; Jan 18; Feb 15; May 31; Jul 05; Sep 06; Oct 11; Nov 11; Nov 25 (Jun 19 and Dec 25 are Saturdays: open Friday; Jul 4 is a Sunday: closed Monday Jul 5) | reported figure, Federal Reserve Financial Services, holiday schedules, accessed 3 November 2026 |
| Announced 22x6 schedule | Sunday to Friday including weekday holidays, Saturday closed (26 hours from Friday 19:00 to Saturday 21:00), implementation 2028 or 2029, not yet in effect | reported figure, 90 FR 51356, 17 November 2025 |
| Fedwire Securities: opening; secondary-market transfer cutoff | 8:30 a.m. ET; 3:15 p.m. ET (3:30 p.m. is for reversals and repo adjustments); not covered by the 2025 schedule expansion, which is Fedwire Funds and NSS only | reported figure, Federal Reserve Financial Services, Fedwire Securities Service schedule |
| Closed-window convention; elapsed-hours check | nominal Eastern schedule hours; check with America/New_York offsets (zoneinfo) | author convention |
| Stay on termination, liquidation and netting rights | no termination solely because of the receiver's appointment until 17:00 ET on the business day after it; business day excludes Saturday, Sunday and days the NYSE or the New York Reserve Bank is closed | reported figure, 12 U.S.C. 1821(e)(10)(B)(i) and (e)(10)(D) |
| Outflow over a window of h hours | median scales with h / 50 (linear); square root of h / 50 as a sensitivity; same sigma | author assumption (illustrative) |
| Liquid-asset buffer b held anyway | 0%, 5%, 10%, 20%, 40% of the tokenized balance | author assumption (illustrative) |
| Custody-and-positioning spread on bills drawn from the buffer | 0.0 to 5.0 | author assumption (illustrative) |
| Sponsor margin; sponsor's extra access cost | 2.0 to 6.0 per non-member tier dollar; 1.0 to 3.0 on the non-member's whole balance | author assumption (illustrative) |
| Overnight secured rate; bridging spread | 4.3%; 10.0 to 50.0 | author assumption (illustrative) |
| Monday cash gap hours: legal stay interval | 20, from the scheduled Fedwire opening at which settlement would have happened to the end of the stay (Sunday 21:00 to Monday 17:00; after a Monday holiday, Monday 21:00 to Tuesday 17:00) | author convention on the reported hours |
| Monday cash gap hours: operational collateral-to-cash interval | 35.5: the stay ends after the securities cutoff, so collateral is delivered against cash at the next securities opening (Sunday 21:00 to Tuesday 8:30; after a Monday holiday, Monday 21:00 to Wednesday 8:30) | author convention on the reported hours |
| Daylight overdraft fee at the Sunday opening | 0.0 bps a year, collateralized (constant DOD_FEE); 50.0 uncollateralized as a sensitivity, quoted on a 24-hour day and a 360-day year, daily rate truncated to 0.0000138 | reported figure, Federal Reserve Policy on Payment System Risk, Section II.C and footnote 58 |
| Daylight overdraft repaid | Monday 12:00 ET: a solvent debtor repays from a delivery-versus-payment sale or bilateral repo of its bills settling Monday morning after the 8:30 securities opening (15 hours from the Sunday opening) | author assumption (illustrative) |
| Closure timing; spread of the closed member's debit | every closure on the last business day before a weekend; debit spread equally over the other 19 members | author assumption (illustrative) |

## 2. Parity with the routes engine and method checks

Each imported value is read from the routes engine in memory and compared, at the precision it is recorded, with the value in `model/results_routes.md`; the row passes only when the two strings match and the recorded string is present in that file.

| Imported quantity | Imported value | Recorded value | Result |
|---|---|---|---|
| R7 price, low end, bps a year on the whole balance | 10.0 | 10.0 | PASS |
| R7 price, high end, bps | 34.0 | 34.0 | PASS |
| R7 price, base, bps | 22.0 | 22.0 | PASS |
| Per-member bind probability per weekend at sigma 0.8 | 4.156% | 4.156% | PASS |
| Per-member bind probability at sigma 0.5 | 0.278% | 0.278% | PASS |
| Per-member bind probability at sigma 1.2 | 12.399% | 12.399% | PASS |
| R7 lendable share at the 20% always-on share | 0.80 | 0.80 | PASS |
| Haircut on bills | 2% | 2% | PASS |
| Always-on share | 20% | 20% | PASS |
| Weekend outflow median / tier; sigma | 25%; 0.8 | 25%; 0.8 | PASS |
| S2 threshold (lendable share at least) | 0.9 | 0.9 | PASS |
| Real-world default intensity lambda_P | 0.25% | 0.25% | PASS |

Parity result: all rows PASS.

| Method check | This engine | Reference | Result |
|---|---|---|---|
| Inverse normal (vectorized) vs the standard library, largest absolute gap on a 2,001-point grid | 0.0000000054 | 0.0000000000 | PASS |
| t(5) upper quantile at 4.156%: closed-form cdf vs the clearing-cost engine's threshold | 2.1606458121 | 2.1606458120 | PASS |
| rho 0, Gaussian: quadrature P(at least 1 of 20) vs independent binomial | 0.5721392003 | 0.5721392003 | PASS |
| rho 0, Gaussian: quadrature P(at least 3 of 20) vs independent binomial | 0.0482331989 | 0.0482331989 | PASS |
| rho 0, Gaussian: quadrature P(at least 5 of 20) vs independent binomial | 0.0011374046 | 0.0011374046 | PASS |
| Window of 50 hours at 20% backing vs the routes engine's per-member bind probability | 0.0415595709 | 0.0415595709 | PASS |
| Calendar: closed hours + 22 x business days vs hours between the year's bounding closes (largest gap) | 0.0000000000 | 0.0000000000 | PASS |
| Buffer 0: facility price vs the routes engine's r7_price (largest gap, bps) | 0.0000000000 | 0.0000000000 | PASS |

Method checks: all PASS. The Monte Carlo check of the factor model is in Section 3 (largest absolute z-score 2.31).

## 3. Same-weekend factor model (analysis A)

Member i's weekend peak net debit (the largest net debit it runs during the closed window, to all counterparties) as a share of its always-on tier is X_i = 0.25 exp(sigma Z_i), the routes engine's marginal. The M members form an open debtor cohort: each is drawn as a net debtor and its receivers sit outside the modelled set. Dependence enters through a one-factor copula: Z_i = sqrt(rho) F + sqrt(1 - rho) e_i (Gaussian), or the same latent divided by sqrt(W / 5), W chi-square(5), and mapped back to a standard normal through the t cdf (Student-t), so each member keeps the lognormal marginal. The cap binds at a member when X_i exceeds 1. Counts come from quadrature over the factor (and W for the t copula); the queued amount, the peak debit above the cap summed over the cohort as a share of the cohort's always-on tier, comes from the Monte Carlo. Weekends are independent of each other, so the 99th percentile over a year is the weekly quantile at 0.99^(1/52).

Table A1. Open debtor cohort of M 20, sigma 0.8: bind counts per weekend and the queued amount (share of the cohort's always-on tier). Not a closed-membership result.

| Copula | rho | P(at least 1 binds) | P(at least 3) | P(at least 5, a quarter) | Expected number binding | Queued, mean | Queued, 99th pct weekend | Queued, 99th pct over a year |
|---|---|---|---|---|---|---|---|---|
| Gaussian | 0.00 | 57.2% | 4.82% | 0.114% | 0.831 | 1.894% | 14.98% | 36.37% |
| Gaussian | 0.15 | 47.7% | 8.66% | 1.51% | 0.831 | 1.902% | 18.67% | 47.90% |
| Gaussian | 0.30 | 39.6% | 10.3% | 3.36% | 0.831 | 1.902% | 23.72% | 74.78% |
| Gaussian | 0.50 | 30.0% | 10.7% | 5.16% | 0.831 | 1.900% | 31.38% | 128.97% |
| Student-t(5) | 0.00 | 41.5% | 10.5% | 2.76% | 0.831 | 1.884% | 25.13% | 106.80% |
| Student-t(5) | 0.15 | 36.0% | 10.9% | 4.12% | 0.831 | 1.888% | 28.82% | 142.70% |
| Student-t(5) | 0.30 | 30.8% | 10.9% | 5.10% | 0.831 | 1.892% | 32.41% | 179.29% |
| Student-t(5) | 0.50 | 24.1% | 10.3% | 5.89% | 0.831 | 1.896% | 38.03% | 225.75% |

Each member's cap binds in 4.156% of weekends whatever the copula, so the expected number binding is 0.831 in every row; dependence changes how the binds arrive. With independent members the cap binds somewhere in the open cohort in 57.2% of weekends and at a quarter of members in 0.114%. At rho 0.30 the Gaussian factor lowers the chance that any member binds to 39.6% but raises the chance that a quarter bind together to 3.36%, and the Student-t(5) factor raises it to 5.10% (5.89% at rho 0.50). The queued amount on the 99th-percentile weekend of a year is 74.78% of the cohort's always-on tier under the Gaussian factor at rho 0.30 and 179.29% under the t factor. The t(5) copula at rho 0 is uncorrelated but not independent: the common W still makes binds arrive together.

Table A2. Sensitivity, open debtor cohort: P(at least 1 binds), P(at least a quarter bind) and the queued amount on the 99th-percentile weekend of a year, by cohort size (sigma 0.8) and by sigma (M 20).

| M | sigma | Copula | rho | Per-member P(bind) | P(at least 1) | A quarter is | P(at least a quarter) | Queued, 99th pct over a year |
|---|---|---|---|---|---|---|---|---|
| 10 | 0.8 | Gaussian | 0.00 | 4.156% | 34.6% | 3 | 0.691% | 59.76% |
| 10 | 0.8 | Gaussian | 0.15 | 4.156% | 30.7% | 3 | 2.07% | 70.03% |
| 10 | 0.8 | Gaussian | 0.30 | 4.156% | 26.7% | 3 | 3.48% | 92.51% |
| 10 | 0.8 | Gaussian | 0.50 | 4.156% | 21.4% | 3 | 4.91% | 141.05% |
| 10 | 0.8 | Student-t(5) | 0.00 | 4.156% | 28.0% | 3 | 3.06% | 123.25% |
| 10 | 0.8 | Student-t(5) | 0.15 | 4.156% | 24.9% | 3 | 4.08% | 161.05% |
| 10 | 0.8 | Student-t(5) | 0.30 | 4.156% | 22.0% | 3 | 4.86% | 188.54% |
| 10 | 0.8 | Student-t(5) | 0.50 | 4.156% | 18.0% | 3 | 5.53% | 236.79% |
| 40 | 0.8 | Gaussian | 0.00 | 4.156% | 81.7% | 10 | 0.000413% | 22.14% |
| 40 | 0.8 | Gaussian | 0.15 | 4.156% | 66.1% | 10 | 0.676% | 37.59% |
| 40 | 0.8 | Gaussian | 0.30 | 4.156% | 53.7% | 10 | 2.42% | 67.70% |
| 40 | 0.8 | Gaussian | 0.50 | 4.156% | 39.4% | 10 | 4.44% | 124.31% |
| 40 | 0.8 | Student-t(5) | 0.00 | 4.156% | 55.7% | 10 | 1.65% | 100.28% |
| 40 | 0.8 | Student-t(5) | 0.15 | 4.156% | 47.7% | 10 | 3.19% | 135.73% |
| 40 | 0.8 | Student-t(5) | 0.30 | 4.156% | 40.2% | 10 | 4.33% | 171.97% |
| 40 | 0.8 | Student-t(5) | 0.50 | 4.156% | 30.7% | 10 | 5.34% | 221.98% |
| 20 | 0.5 | Gaussian | 0.00 | 0.278% | 5.42% | 5 | below 0.0001% | 5.61% |
| 20 | 0.5 | Gaussian | 0.15 | 0.278% | 5.11% | 5 | 0.000967% | 6.09% |
| 20 | 0.5 | Gaussian | 0.30 | 0.278% | 4.57% | 5 | 0.0204% | 7.69% |
| 20 | 0.5 | Gaussian | 0.50 | 0.278% | 3.60% | 5 | 0.121% | 12.52% |
| 20 | 0.5 | Student-t(5) | 0.00 | 0.278% | 3.66% | 5 | 0.0892% | 13.93% |
| 20 | 0.5 | Student-t(5) | 0.15 | 0.278% | 3.21% | 5 | 0.164% | 18.42% |
| 20 | 0.5 | Student-t(5) | 0.30 | 0.278% | 2.75% | 5 | 0.238% | 21.87% |
| 20 | 0.5 | Student-t(5) | 0.50 | 0.278% | 2.13% | 5 | 0.324% | 27.87% |
| 20 | 1.2 | Gaussian | 0.00 | 12.399% | 92.9% | 5 | 9.25% | 219.94% |
| 20 | 1.2 | Gaussian | 0.15 | 12.399% | 82.0% | 5 | 16.4% | 276.31% |
| 20 | 1.2 | Gaussian | 0.30 | 12.399% | 71.6% | 5 | 19.0% | 423.79% |
| 20 | 1.2 | Gaussian | 0.50 | 12.399% | 57.9% | 5 | 19.8% | 675.90% |
| 20 | 1.2 | Student-t(5) | 0.00 | 12.399% | 83.0% | 5 | 16.2% | 570.69% |
| 20 | 1.2 | Student-t(5) | 0.15 | 12.399% | 74.0% | 5 | 18.8% | 751.62% |
| 20 | 1.2 | Student-t(5) | 0.30 | 12.399% | 65.2% | 5 | 19.7% | 921.48% |
| 20 | 1.2 | Student-t(5) | 0.50 | 12.399% | 53.4% | 5 | 19.8% | 1147.36% |

A larger open cohort makes some bind on most weekends but makes a quarter binding together rarer: under the Gaussian factor at rho 0.30, P(at least a quarter) is 3.48% with 10 members and 2.42% with 40. Sigma moves everything: at sigma 0.5 the per-member rate is 0.278% and at 1.2 it is 12.399%.

Table A3. Monte Carlo check of the quadrature, M 20, sigma 0.8 (500,000 weekends, seed 20261120); z is (Monte Carlo minus quadrature) / standard error; the per-member standard error is that of the weekly share of members binding, so it allows for dependence within a weekend. The rows share one set of draws, so their errors move together.

| Copula | rho | Per-member rate, Monte Carlo (z) | P(at least 1), quadrature / Monte Carlo (z) | P(at least 3) (z) | P(at least 5) (z) |
|---|---|---|---|---|---|
| Gaussian | 0.00 | 4.163% (+1.13) | 57.2% / 57.3% (+0.82) | 4.82% / 4.84% (+0.39) | 0.114% / 0.112% (-0.37) |
| Gaussian | 0.15 | 4.169% (+1.54) | 47.7% / 47.8% (+0.98) | 8.66% / 8.73% (+1.75) | 1.51% / 1.53% (+0.73) |
| Gaussian | 0.30 | 4.172% (+1.52) | 39.6% / 39.7% (+1.00) | 10.3% / 10.4% (+1.64) | 3.36% / 3.38% (+0.76) |
| Gaussian | 0.50 | 4.179% (+1.72) | 30.0% / 30.1% (+1.60) | 10.7% / 10.8% (+2.31) | 5.16% / 5.21% (+1.67) |
| Student-t(5) | 0.00 | 4.165% (+0.92) | 41.5% / 41.6% (+1.60) | 10.5% / 10.5% (+0.92) | 2.76% / 2.76% (+0.12) |
| Student-t(5) | 0.15 | 4.165% (+0.80) | 36.0% / 36.1% (+1.65) | 10.9% / 11.0% (+0.13) | 4.12% / 4.11% (-0.38) |
| Student-t(5) | 0.30 | 4.168% (+0.93) | 30.8% / 30.9% (+2.23) | 10.9% / 10.9% (+0.07) | 5.10% / 5.09% (-0.45) |
| Student-t(5) | 0.50 | 4.166% (+0.61) | 24.1% / 24.2% (+1.89) | 10.3% / 10.3% (+0.09) | 5.89% / 5.88% (-0.45) |

At rho 0 the Gaussian quadrature reproduces the independent binomial exactly (Section 2) and the Monte Carlo per-member rate is 4.163% against 4.156%. The largest absolute z-score in the table is 2.31.

### Cap ladder

The backing a member must hold (its always-on share, with the cap equal to the share) so that a bind frequency meets a target, with the weekend peak debit itself unchanged: median 25% of a 20% tier, that is 5.0% of the tokenized balance, sigma 0.8. The cap multiple is the cap over the median peak debit (4.0 in the routes engine). The per-member criterion does not depend on the copula or rho, because each member keeps its marginal; the joint criteria do, and describe the open debtor cohort, not a closed membership. Prices use the routes engine's r7_price at the new share; lendable share is 1 minus the share, as in the routes engine.

| Target | Criterion | Copula | rho | Per-member P(bind) needed | Cap multiple | Backing (always-on share) | Price, whole balance | Lendable share | S2 |
|---|---|---|---|---|---|---|---|---|---|
| 1% of weekends | per member | any | any | 1.00% | 6.43 | 32.2% | 13.0 to 46.2 | 0.678 | fail |
| 1% of weekends | at least 1 of 20 | Gaussian | 0.00 | 0.0502% | 13.89 | 69.5% | 22.4 to 83.5 | 0.305 | fail |
| 1% of weekends | at least 1 of 20 | Gaussian | 0.15 | 0.0513% | 13.83 | 69.1% | 22.3 to 83.1 | 0.309 | fail |
| 1% of weekends | at least 1 of 20 | Gaussian | 0.30 | 0.0544% | 13.64 | 68.2% | 22.1 to 82.2 | 0.318 | fail |
| 1% of weekends | at least 1 of 20 | Gaussian | 0.50 | 0.0661% | 13.05 | 65.3% | 21.3 to 79.3 | 0.347 | fail |
| 1% of weekends | at least 1 of 20 | Student-t(5) | 0.00 | 0.0730% | 12.76 | 63.8% | 20.9 to 77.8 | 0.362 | fail |
| 1% of weekends | at least 1 of 20 | Student-t(5) | 0.15 | 0.0832% | 12.37 | 61.9% | 20.5 to 75.9 | 0.381 | fail |
| 1% of weekends | at least 1 of 20 | Student-t(5) | 0.30 | 0.0971% | 11.93 | 59.7% | 19.9 to 73.7 | 0.403 | fail |
| 1% of weekends | at least 1 of 20 | Student-t(5) | 0.50 | 0.126% | 11.21 | 56.0% | 19.0 to 70.0 | 0.440 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Gaussian | 0.00 | 6.88% | 3.28 | 16.4% | 9.1 to 30.4 | 0.836 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Gaussian | 0.15 | 3.51% | 4.26 | 21.3% | 10.3 to 35.3 | 0.787 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Gaussian | 0.30 | 2.10% | 5.09 | 25.5% | 11.4 to 39.5 | 0.745 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Gaussian | 0.50 | 1.23% | 6.05 | 30.2% | 12.6 to 44.2 | 0.698 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Student-t(5) | 0.00 | 2.02% | 5.16 | 25.8% | 11.4 to 39.8 | 0.742 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Student-t(5) | 0.15 | 1.35% | 5.87 | 29.4% | 12.3 to 43.4 | 0.706 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Student-t(5) | 0.30 | 1.03% | 6.38 | 31.9% | 13.0 to 45.9 | 0.681 | fail |
| 1% of weekends | at least a quarter (5 of 20) | Student-t(5) | 0.50 | 0.810% | 6.85 | 34.2% | 13.6 to 48.2 | 0.658 | fail |
| once in ten years (1 in 520 weekends) | per member | any | any | 0.192% | 10.10 | 50.5% | 17.6 to 64.5 | 0.495 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Gaussian | 0.00 | 0.00962% | 19.75 | 98.7% | 29.7 to 112.7 | 0.013 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Gaussian | 0.15 | 0.00969% | 19.72 | 98.6% | 29.7 to 112.6 | 0.014 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Gaussian | 0.30 | 0.00996% | 19.61 | 98.1% | 29.5 to 112.1 | 0.019 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Gaussian | 0.50 | 0.0113% | 19.12 | 95.6% | 28.9 to 109.6 | 0.044 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Student-t(5) | 0.00 | 0.0137% | 18.38 | 91.9% | 28.0 to 105.9 | 0.081 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Student-t(5) | 0.15 | 0.0155% | 17.91 | 89.5% | 27.4 to 103.5 | 0.105 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Student-t(5) | 0.30 | 0.0180% | 17.35 | 86.8% | 26.7 to 100.8 | 0.132 | fail |
| once in ten years (1 in 520 weekends) | at least 1 of 20 | Student-t(5) | 0.50 | 0.0233% | 16.44 | 82.2% | 25.6 to 96.2 | 0.178 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Gaussian | 0.00 | 4.68% | 3.82 | 19.1% | 9.8 to 33.1 | 0.809 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Gaussian | 0.15 | 1.84% | 5.31 | 26.6% | 11.6 to 40.6 | 0.734 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Gaussian | 0.30 | 0.869% | 6.70 | 33.5% | 13.4 to 47.5 | 0.665 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Gaussian | 0.50 | 0.382% | 8.45 | 42.2% | 15.6 to 56.2 | 0.578 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Student-t(5) | 0.00 | 0.540% | 7.69 | 38.4% | 14.6 to 52.4 | 0.616 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Student-t(5) | 0.15 | 0.321% | 8.85 | 44.2% | 16.1 to 58.2 | 0.558 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Student-t(5) | 0.30 | 0.228% | 9.67 | 48.4% | 17.1 to 62.4 | 0.516 | fail |
| once in ten years (1 in 520 weekends) | at least a quarter (5 of 20) | Student-t(5) | 0.50 | 0.168% | 10.44 | 52.2% | 18.1 to 66.2 | 0.478 | fail |

Rows that pass S2: 0 of 34, none. Holding a member's own cap to binding in 1% of weekends needs a cap multiple of 6.43 and a backing of 32.2% of the balance, priced 13.0 to 46.2 with a lendable share of 0.68; once in ten years needs 50.5%, priced 17.6 to 64.5. S2 allows a backing of at most 10% (a cap multiple of 2.0 at this outflow), at which a member's cap binds in 19.3% of weekends.

Table A4. The largest median weekend peak debit, as a share of the tokenized balance, at which a member can meet the per-member target with a backing that passes S2 (backing at most 10%); the routes engine assumes 5.0%.

| sigma | Per-member target | Largest median peak debit compatible with S2 | Per-member P(bind) at a 10% backing, median 5% |
|---|---|---|---|
| 0.5 | 1% of weekends | 3.12% | 8.28% |
| 0.5 | once in ten years (1 in 520 weekends) | 2.36% | 8.28% |
| 0.8 | 1% of weekends | 1.56% | 19.3% |
| 0.8 | once in ten years (1 in 520 weekends) | 0.99% | 19.3% |
| 1.2 | 1% of weekends | 0.61% | 28.2% |
| 1.2 | once in ten years (1 in 520 weekends) | 0.31% | 28.2% |

At sigma 0.8 the facility meets S2 and a 1% per-member bind rate together only if the median weekend peak debit is at most 1.56% of the tokenized balance, under a third of the routes engine's 5%. The lendable screen and a rare cap cannot both hold at the routes engine's outflow assumption.

Table A5. Median sensitivity, per member: bind probability per weekend at a cap of 10% of the balance (the largest backing S2 allows), and the cap a 1%-of-weekends bind needs, with the S2 verdict on that cap.

| sigma | Median peak debit, share of the balance | P(bind) at a 10% cap | Cap for a 1% per-member bind | Lendable share at that cap | S2 |
|---|---|---|---|---|---|
| 0.5 | 1.0% | 0.000206% | 3.20% | 0.968 | pass |
| 0.5 | 1.5% | 0.00740% | 4.80% | 0.952 | pass |
| 0.5 | 2.0% | 0.0643% | 6.40% | 0.936 | pass |
| 0.5 | 3.0% | 0.802% | 9.60% | 0.904 | pass |
| 0.5 | 5.0% | 8.28% | 16.00% | 0.840 | fail |
| 0.8 | 1.0% | 0.200% | 6.43% | 0.936 | pass |
| 0.8 | 1.5% | 0.886% | 9.65% | 0.904 | pass |
| 0.8 | 2.0% | 2.21% | 12.86% | 0.871 | fail |
| 0.8 | 3.0% | 6.62% | 19.29% | 0.807 | fail |
| 0.8 | 5.0% | 19.3% | 32.15% | 0.678 | fail |
| 1.2 | 1.0% | 2.75% | 16.31% | 0.837 | fail |
| 1.2 | 1.5% | 5.69% | 24.46% | 0.755 | fail |
| 1.2 | 2.0% | 8.99% | 32.61% | 0.674 | fail |
| 1.2 | 3.0% | 15.8% | 48.92% | 0.511 | fail |
| 1.2 | 5.0% | 28.2% | 81.54% | 0.185 | fail |

At sigma 0.8 the verdict turns between medians of 1.5% and 2%: a 1% bind needs a cap of 9.65% at 1.5% (pass) and 12.86% at 2% (fail). No public source reports participant-level peak debits on tokenized balances, so the median is the input to observe in a pilot.

### S2 bar sensitivity of the cap-ladder boundary

Table A6. At each S2 bar of the routes engine's sensitivity (results_routes.md, Section 9b), the largest cap S2 allows, c = 1 minus the bar, and the largest median weekend peak debit, as a share of the tokenized balance, that keeps a member's cap binding in at most 1% of weekends: c / exp(sigma x 2.3263). The second boundary counts the grossed-up bills as non-lendable, so the cap is c x 0.98 (Section 9). The cap test passes when the boundary is at least the assumed median of 5.0%. The rule of record is the 0.9 bar.

| S2 bar | Largest cap c | sigma | Largest median for a 1% bind, cap c | Cap test at the 5.0% median, cap c | Largest median, cap c x 0.98 (grossed-up bills) | Cap test at the 5.0% median, grossed-up bills | Per-member P(bind) at cap c, median 5.0% |
|---|---|---|---|---|---|---|---|
| 0.75 | 25% | 0.5 | 7.81% | pass | 7.66% | pass | 0.0643% |
| 0.75 | 25% | 0.8 | 3.89% | fail | 3.81% | fail | 2.21% |
| 0.75 | 25% | 1.2 | 1.53% | fail | 1.50% | fail | 8.99% |
| 0.80 | 20% | 0.5 | 6.25% | pass | 6.12% | pass | 0.278% |
| 0.80 | 20% | 0.8 | 3.11% | fail | 3.05% | fail | 4.16% |
| 0.80 | 20% | 1.2 | 1.23% | fail | 1.20% | fail | 12.4% |
| 0.85 | 15% | 0.5 | 4.69% | fail | 4.59% | fail | 1.40% |
| 0.85 | 15% | 0.8 | 2.33% | fail | 2.29% | fail | 8.48% |
| 0.85 | 15% | 1.2 | 0.92% | fail | 0.90% | fail | 18.0% |
| 0.90 | 10% | 0.5 | 3.12% | fail | 3.06% | fail | 8.28% |
| 0.90 | 10% | 0.8 | 1.56% | fail | 1.52% | fail | 19.3% |
| 0.90 | 10% | 1.2 | 0.61% | fail | 0.60% | fail | 28.2% |

At sigma 0.8 the boundary is 3.89% at 0.75, 3.11% at 0.80, 2.33% at 0.85, 1.56% at 0.90 (3.81%, 3.05%, 2.29%, 1.52% counting the grossed-up bills): the cap test fails at the assumed 5.0% median at every bar. It passes only at sigma 0.5, bar 0.75; sigma 0.5, bar 0.80.

## 4. Closed-window calendar (analysis B)

Fedwire Funds opens at 21:00 ET on the calendar day before each business day and closes at 19:00 ET (Federal Reserve Financial Services, Fedwire Funds Service and NSS operating hours, accessed 3 November 2026), so a closed window between business days a and b lasts 24 x (days from a to b) - 22 hours. Holidays are the Reserve Banks' weekday closings (Federal Reserve Financial Services, holiday schedules, accessed 3 November 2026). Each business day is preceded by one window, and a window belongs to the year of the business day that ends it. Window lengths are nominal schedule hours (the convention); the elapsed-hours check at the end of this section adds the daylight-saving offsets. The constants sit at the top of the script.

Table B1. Closed windows by type.

| Year | Window type | Hours | Count | Total closed hours |
|---|---|---|---|---|
| 2026 | Weekday evening gap | 2 | 196 | 392 |
| 2026 | Midweek holiday | 26 | 3 | 78 |
| 2026 | Normal weekend | 50 | 45 | 2250 |
| 2026 | Three-day weekend | 74 | 7 | 518 |
| 2026 | All windows |  | 251 | 3238 |
| 2027 | Weekday evening gap | 2 | 198 | 396 |
| 2027 | Midweek holiday | 26 | 2 | 52 |
| 2027 | Normal weekend | 50 | 45 | 2250 |
| 2027 | Three-day weekend | 74 | 7 | 518 |
| 2027 | All windows |  | 252 | 3216 |

2026 has 251 business days and 3,238 closed hours; its 52 weekends split into 45 normal weekends of 50 hours and 7 three-day weekends of 74 hours, and 3 midweek holidays add 26-hour windows. 2027 has 252 business days and 3,216 closed hours. No window longer than 74 hours occurs in either year.

Table B2. Policy P1 (cap sized for the normal weekend, backing 20%, all year): bind probability per window.

| Window type | Hours | P(bind), linear scaling | P(bind), square-root scaling | Relative to a normal weekend, linear | Relative, square root |
|---|---|---|---|---|---|
| Weekday evening gap | 2 | below 0.0001% | 0.00903% | 0.00 | 0.00 |
| Midweek holiday | 26 | 0.538% | 1.61% | 0.13 | 0.39 |
| Normal weekend | 50 | 4.16% | 4.16% | 1.00 | 1.00 |
| Three-day weekend | 74 | 10.7% | 6.84% | 2.57 | 1.65 |

Under P1 a three-day weekend binds 2.57 times as often as a normal weekend with linear scaling (10.7% against 4.156%) and 1.65 times as often with square-root scaling; a midweek holiday binds 0.13 times as often (linear). The weekday evening gap is negligible under either scaling.

Table B3. Expected binds a year for one member under P1, calendar against the routes engine.

| Basis | Scaling | Expected binds a year | P(at least one bind in the year) |
|---|---|---|---|
| Routes engine (52 independent weekends) |  | 2.16 | 89.0% |
| Calendar 2026, P1 | linear | 2.64 | 93.4% |
| Calendar 2026, P1 | sqrt | 2.41 | 91.6% |
| Calendar 2027, P1 | linear | 2.63 | 93.4% |
| Calendar 2027, P1 | sqrt | 2.40 | 91.4% |

The calendar adds 0.47 expected binds a year to the routes engine's 2.16 in 2026 under linear scaling (2.64 in all), almost all of it from the 7 three-day weekends.

Table B4. Policies: P1 sizes the cap for the normal weekend all year; P2 sizes the backing so the longest window binds no more often than a normal weekend does under P1, and holds it all year.

| Year | Scaling | Policy | Backing | Price, whole balance | Lendable share | S2 | Expected binds a year |
|---|---|---|---|---|---|---|---|
| 2026 | linear | P1 | 20.0% | 10.0 to 34.0 | 0.800 | fail | 2.64 |
| 2026 | linear | P2 (longest window 74 h) | 29.6% | 12.4 to 43.6 | 0.704 | fail | 0.88 |
| 2026 | sqrt | P1 | 20.0% | 10.0 to 34.0 | 0.800 | fail | 2.41 |
| 2026 | sqrt | P2 (longest window 74 h) | 24.3% | 11.1 to 38.3 | 0.757 | fail | 1.40 |
| 2027 | linear | P1 | 20.0% | 10.0 to 34.0 | 0.800 | fail | 2.63 |
| 2027 | linear | P2 (longest window 74 h) | 29.6% | 12.4 to 43.6 | 0.704 | fail | 0.88 |
| 2027 | sqrt | P1 | 20.0% | 10.0 to 34.0 | 0.800 | fail | 2.40 |
| 2027 | sqrt | P2 (longest window 74 h) | 24.3% | 11.1 to 38.3 | 0.757 | fail | 1.39 |

P2 needs a backing of 29.6% under linear scaling (24.3% under square root), priced 12.4 to 43.6 against P1's 10.0 to 34.0, with a lendable share of 0.70: it fails S2 by more than P1 does, and cuts expected binds to 0.88 a year.

Table B5. Schedule scenarios (2026 calendar). Two sizing criteria: the longest window binds no more often than a normal weekend does under P1 (4.156%), or the member's expected binds a year equal the routes engine's 2.16 (52 weekends at 4.156%). Price and lendable share at the linear backing.

| Schedule | Closed windows | Sized to | Backing, linear | Backing, square root | Price, linear | Lendable, linear | S2 | Expected binds a year at that backing (linear) | Expected binds a year at a 20% backing (linear) |
|---|---|---|---|---|---|---|---|---|---|
| Current: Monday to Friday, Reserve Bank holidays closed | 196 of 2 h; 3 of 26 h; 45 of 50 h; 7 of 74 h | longest window (74 h) at 4.156% | 29.6% | 24.3% | 12.4 to 43.6 | 0.704 | fail | 0.88 | 2.64 |
| Current: Monday to Friday, Reserve Bank holidays closed |  | 2.16 expected binds a year | 21.6% | 20.8% | 10.4 to 35.6 | 0.784 | fail | 2.16 |  |
| Announced 22x6 schedule (90 FR 51356, 17 November 2025), not yet in effect: Sunday to Friday, weekday holidays open | 261 of 2 h; 52 of 26 h | longest window (26 h) at 4.156% | 10.4% | 14.4% | 7.6 to 24.4 | 0.896 | fail | 2.16 | 0.28 |
| Announced 22x6 schedule (90 FR 51356, 17 November 2025), not yet in effect: Sunday to Friday, weekday holidays open |  | 2.16 expected binds a year | 10.4% | 14.7% | 7.6 to 24.4 | 0.896 | fail | 2.16 |  |
| Seven days (hypothetical): every day open | 365 of 2 h | longest window (2 h) at 4.156% | 0.8% | 4.0% | 5.2 to 14.8 | 0.992 | pass | 15.17 | 0.00 |
| Seven days (hypothetical): every day open |  | 2.16 expected binds a year | 1.5% | 7.5% | 5.4 to 15.5 | 0.985 | pass | 2.16 |  |

Under the announced 22x6 schedule, which opens weekday holidays as well as Sundays, the longest window is the 26-hour Saturday closure, so the backing that holds P1's normal-weekend bind rate on every window falls from 29.6% today to 10.4% under linear scaling (14.4% under square root), priced 7.6 to 24.4 against today's 12.4 to 43.6. The standing-capacity term falls by 48% against P1's 20% on the hours alone, but the lendable share is 0.896, which still misses S2 by 0.004; under square-root scaling it misses by 0.044. Held to the routes engine's 2.16 binds a year instead, today's calendar needs 21.6% and the 22x6 schedule 10.4%. Seven-day operation, a hypothetical, leaves 365 two-hour gaps: sized so each binds no more often than a normal weekend today, the backing is 0.8% (linear) or 4.0% (square root) but the member then binds 15.2 times a year; held to 2.16 binds a year it is 1.5% (linear) or 7.5% (square root), priced 5.4 to 15.5, of which access and frictions are nearly all.

The seven-day pass is conditional. With seven-day Fedwire Funds but Fedwire Securities and the repo market still on weekdays, each weekend net debit settles in reserves before any bill can be repoed or sold, so the pass needs either weekend Reserve Bank credit against collateral or reserves held against the weekend outflow (analysis F). Reserves held count as not lendable under the absolute convention.

Table B6. Seven-day schedule (hypothetical), sized to the routes engine's binds a year: lendable share with weekend Reserve Bank credit, and with reserves held against the weekend peak debit at the routes engine's bind rate.

| Scaling | Weekend cash source | Bills backing the facility | Reserves held | Lendable share (absolute) | S2 |
|---|---|---|---|---|---|
| linear | weekend Reserve Bank credit (no reserves held) | 1.5% | 0 | 0.985 | pass |
| sqrt | weekend Reserve Bank credit (no reserves held) | 7.5% | 0 | 0.925 | pass |
| linear | reserves held, sized over the normal-weekend window, 50 hours (the outflow's calibration window) | 1.5% | 20.0% | 0.785 | fail |
| linear | reserves held, sized over the Friday securities cutoff to Monday securities opening, 65.25 hours | 1.5% | 26.1% | 0.724 | fail |
| sqrt | reserves held, sized over the normal-weekend window, 50 hours (the outflow's calibration window) | 7.5% | 20.0% | 0.725 | fail |
| sqrt | reserves held, sized over the Friday securities cutoff to Monday securities opening, 65.25 hours | 7.5% | 22.8% | 0.697 | fail |

Seven-day operation passes S2 only with weekend Reserve Bank credit; with reserves held against the weekend outflow it fails under every row, because the reserves cost the lendable share the facility's bills had saved.

### Elapsed hours: the daylight-saving check

The convention is nominal Eastern schedule hours. Computed with America/New_York offsets and differenced in UTC, the windows that span a daylight-saving change are:

| Year | Closed window | Nominal hours | Elapsed hours |
|---|---|---|---|
| 2026 | Fri 06 Mar 19:00 to Sun 08 Mar 21:00 | 50 | 49 |
| 2026 | Fri 30 Oct 19:00 to Sun 01 Nov 21:00 | 50 | 51 |
| 2027 | Fri 12 Mar 19:00 to Sun 14 Mar 21:00 | 50 | 49 |
| 2027 | Fri 05 Nov 19:00 to Sun 07 Nov 21:00 | 50 | 51 |

Annual closed hours are unchanged (2026: 3,238, 2027: 3,216 elapsed). The announced 22x6 and seven-day schedules close on Saturday evening or every evening, so no window spans the 2:00 a.m. Sunday change: 0 and 0 windows differ. Each printed figure of this section recomputed on elapsed hours, compared at its printed precision:

| Figure | Nominal hours (printed) | Elapsed hours | Same at printed precision |
|---|---|---|---|
| Calendar 2026, P1, expected binds a year (linear) | 2.64 | 2.64 | yes |
| Calendar 2026, P1, P(at least one bind in the year) (linear) | 93.4% | 93.4% | yes |
| Calendar 2026, P2 backing (linear) | 29.6% | 29.6% | yes |
| Calendar 2026, P1, expected binds a year (sqrt) | 2.41 | 2.42 | NO |
| Calendar 2026, P1, P(at least one bind in the year) (sqrt) | 91.6% | 91.6% | yes |
| Calendar 2026, P2 backing (sqrt) | 24.3% | 24.3% | yes |
| Calendar 2027, P1, expected binds a year (linear) | 2.63 | 2.63 | yes |
| Calendar 2027, P1, P(at least one bind in the year) (linear) | 93.4% | 93.4% | yes |
| Calendar 2027, P2 backing (linear) | 29.6% | 29.6% | yes |
| Calendar 2027, P1, expected binds a year (sqrt) | 2.40 | 2.40 | yes |
| Calendar 2027, P1, P(at least one bind in the year) (sqrt) | 91.4% | 91.4% | yes |
| Calendar 2027, P2 backing (sqrt) | 24.3% | 24.3% | yes |
| Current, sized to the longest window, backing (linear) | 29.6% | 29.6% | yes |
| Current, sized to the longest window, lendable (linear) | 0.704 | 0.704 | yes |
| Current, sized to the longest window, backing (sqrt) | 24.3% | 24.3% | yes |
| Current, sized to the longest window, lendable (sqrt) | 0.757 | 0.757 | yes |
| Current, sized to binds a year, backing (linear) | 21.6% | 21.6% | yes |
| Current, sized to binds a year, lendable (linear) | 0.784 | 0.784 | yes |
| Current, sized to binds a year, backing (sqrt) | 20.8% | 20.8% | yes |
| Current, sized to binds a year, lendable (sqrt) | 0.792 | 0.792 | yes |
| Announced 22x6 schedule, sized to the longest window, backing (linear) | 10.4% | 10.4% | yes |
| Announced 22x6 schedule, sized to the longest window, lendable (linear) | 0.896 | 0.896 | yes |
| Announced 22x6 schedule, sized to the longest window, backing (sqrt) | 14.4% | 14.4% | yes |
| Announced 22x6 schedule, sized to the longest window, lendable (sqrt) | 0.856 | 0.856 | yes |
| Announced 22x6 schedule, sized to binds a year, backing (linear) | 10.4% | 10.4% | yes |
| Announced 22x6 schedule, sized to binds a year, lendable (linear) | 0.896 | 0.896 | yes |
| Announced 22x6 schedule, sized to binds a year, backing (sqrt) | 14.7% | 14.7% | yes |
| Announced 22x6 schedule, sized to binds a year, lendable (sqrt) | 0.853 | 0.853 | yes |
| Seven days, sized to the longest window, backing (linear) | 0.8% | 0.8% | yes |
| Seven days, sized to the longest window, lendable (linear) | 0.992 | 0.992 | yes |
| Seven days, sized to the longest window, backing (sqrt) | 4.0% | 4.0% | yes |
| Seven days, sized to the longest window, lendable (sqrt) | 0.960 | 0.960 | yes |
| Seven days, sized to binds a year, backing (linear) | 1.5% | 1.5% | yes |
| Seven days, sized to binds a year, lendable (linear) | 0.985 | 0.985 | yes |
| Seven days, sized to binds a year, backing (sqrt) | 7.5% | 7.5% | yes |
| Seven days, sized to binds a year, lendable (sqrt) | 0.925 | 0.925 | yes |

1 printed figure(s) change: Calendar 2026, P1, expected binds a year (sqrt) 2.41 to 2.42. The square-root 22x6 case, which misses S2 by 0.044 on nominal hours, misses by 0.044 on elapsed hours.

## 5. Liquidity-buffer test (analysis C, a sensitivity, never the base case)

The bank holds a liquid-asset buffer b of the tokenized balance anyway, and the facility's backing is drawn from it up to b. S2 stays on the absolute convention: bills or reserves held for the always-on tier are not lendable whether or not they are a pre-existing buffer, so the lendable share is 1 minus the share at every buffer and a buffer cannot lift S2 above that. Reported separately, and not the S2 metric, is the incremental lending displacement relative to a bank that already holds the buffer, max(0, share - b); 1 minus it is the figure an earlier version of this engine reported as the lendable share. The standing-capacity term on the covered part uses a custody-and-positioning spread of 0.0 to 5.0 in place of the 25.0 to 100.0 encumbrance spread [author assumption (illustrative)]. At b 0 the price equals the routes engine's.

Table C1. Lendable share and S2 on the absolute convention, and, separately, 1 minus the incremental lending displacement relative to a bank that already holds the buffer (not the S2 metric), by always-on share and buffer.

| Always-on share | Lendable share, absolute (every b) | S2 | b 0%: 1 - incremental displacement | b 5%: 1 - incremental displacement | b 10%: 1 - incremental displacement | b 20%: 1 - incremental displacement | b 40%: 1 - incremental displacement | Smallest b with displacement at most 0.1 |
|---|---|---|---|---|---|---|---|---|
| 5% | 0.950 | pass | 0.950 | 1.000 | 1.000 | 1.000 | 1.000 | 0.00% |
| 7% | 0.930 | pass | 0.930 | 0.980 | 1.000 | 1.000 | 1.000 | 0.00% |
| 10% | 0.900 | pass | 0.900 | 0.950 | 1.000 | 1.000 | 1.000 | 0.00% |
| 20% | 0.800 | fail | 0.800 | 0.850 | 0.900 | 1.000 | 1.000 | 10.00% |
| 35% | 0.650 | fail | 0.650 | 0.700 | 0.750 | 0.850 | 1.000 | 25.00% |
| 50% | 0.500 | fail | 0.500 | 0.550 | 0.600 | 0.700 | 0.900 | 40.00% |

Table C2. Price range, bps a year on the whole balance, by always-on share and buffer.

| Always-on share | b 0% | b 5% | b 10% | b 20% | b 40% |
|---|---|---|---|---|---|
| 5% | 6.3 to 19.0 | 5.0 to 14.3 | 5.0 to 14.3 | 5.0 to 14.3 | 5.0 to 14.3 |
| 7% | 6.8 to 21.0 | 5.5 to 16.3 | 5.0 to 14.4 | 5.0 to 14.4 | 5.0 to 14.4 |
| 10% | 7.5 to 24.0 | 6.3 to 19.3 | 5.0 to 14.5 | 5.0 to 14.5 | 5.0 to 14.5 |
| 20% | 10.0 to 34.0 | 8.8 to 29.3 | 7.5 to 24.5 | 5.0 to 15.0 | 5.0 to 15.0 |
| 35% | 13.8 to 49.0 | 12.5 to 44.3 | 11.3 to 39.5 | 8.8 to 30.0 | 5.0 to 15.8 |
| 50% | 17.5 to 64.0 | 16.3 to 59.3 | 15.0 to 54.5 | 12.5 to 45.0 | 7.5 to 26.0 |

At a 20% always-on share the lendable share is 0.800 at every buffer: S2 fails. Relative to a bank that already holds the buffer, the facility displaces 10% of the balance from lending with a 10% buffer and 0% with a 20% buffer (1 minus displacement 0.900 and 1.000); that is the lending the facility costs on top of the buffer, not the share of the balance that funds loans. Prices: 7.5 to 24.5 with a 10% buffer and 5.0 to 15.0 with a 20% buffer.

Table C3. The double call: share of the buffer left for Monday outflows after the weekend's net debit is settled in central bank money at Sunday's opening, at a 20% always-on share. The 99th-percentile weekend of the open debtor cohort (A, Gaussian, rho 0.30, M 20) has a cohort-average secured debit of 70.8% of the tier, 14.17% of the balance; a member at its cap has settled the full tier, 20% of its balance.

| Buffer b | Left for Monday, cohort-average member on the 99th-percentile weekend | Left for Monday, member at its cap |
|---|---|---|
| 5% | 0.0% | 0.0% |
| 10% | 0.0% | 0.0% |
| 20% | 29.2% | 0.0% |
| 40% | 64.6% | 50.0% |

Counting the buffer for both the facility and the bank's own Monday outflows double-counts it: with a 20% buffer the cohort-average member has 29.2% of the buffer left after the 99th-percentile weekend, and a member whose cap bound has 0.0%.

## 6. Non-members through a sponsoring member (analysis D)

A non-member reaches the facility through a member that carries the non-member's net debit on its own cap, backed by bills the non-member pledges to the sponsor in a back-to-back repo. The non-member pays the R7 terms, a sponsor margin of 2.0 to 6.0 per always-on tier dollar and the sponsor's extra access cost of 1.0 to 3.0 on its whole balance [author assumption (illustrative)].

Table D1. Price for a sponsored non-member.

| Always-on share | Member price, whole balance | Non-member price, whole balance | Non-member, per tier dollar | Sponsorship adds, whole balance |
|---|---|---|---|---|
| 5% | 6.3 to 19.0 | 7.4 to 22.3 | 147.0 to 446.0 | 1.1 to 3.3 |
| 10% | 7.5 to 24.0 | 8.7 to 27.6 | 87.0 to 276.0 | 1.2 to 3.6 |
| 20% | 10.0 to 34.0 | 11.4 to 38.2 | 57.0 to 191.0 | 1.4 to 4.2 |

Sponsorship adds 1.4 to 4.2 on the whole balance at a 20% share, taking the non-member to 11.4 to 38.2; at 5% it adds 1.1 to 3.3, to 7.4 to 22.3, or 147 to 446 per tier dollar, because the extra access cost is fixed and the tier is small.

What the sponsor bears [author's reading]: cap room, not credit, when the back-to-back repo is full. The non-member's net debit counts against the sponsor's cap, so every dollar of it is a dollar the sponsor's own depositors cannot use that weekend; the sponsor's credit exposure to the non-member is the haircut-breach risk on the pledged bills and the timing gap if the non-member is closed (analysis E), the same as a net creditor's. If the sponsor adds the non-member's bills to its own cap, the pooled cap binds less often than two separate caps would, but the sponsor's depositors then queue behind the non-member's: for two equal tiers drawn as net debtors (an open pair, receivers outside it) under the Gaussian factor at rho 0.30, the pooled cap binds in 2.61% of weekends against 7.80% for either separate cap binding (Monte Carlo), so a sponsor would want a sub-limit for the non-member.

## 7. Monday cash for net creditors when a member is closed (analysis E)

If a member is closed on the last business day before a weekend, its net creditors hold its pledged bills. Two provisions apply [12 U.S.C. 1821(e)(8)(G)(ii) and (e)(10)(B); author's reading, Chapter 6]: (e)(10)(B) stays termination, liquidation and netting rights until 17:00 ET on the next business day (business day as in (e)(10)(D)); (e)(8)(G)(ii) suspends payment and delivery under the contract itself during that period. Neither suspends payments in general. Two intervals follow. The legal stay interval runs from the scheduled Fedwire opening at which settlement would have happened to the end of the stay: 20 hours on a normal weekend (Sunday 21:00 to Monday 17:00). The operational collateral-to-cash interval runs to the first time the collateral can be delivered against cash: the stay ends after the Fedwire Securities secondary-market cutoff (3:15 p.m. ET), so delivery waits for the next securities opening, Tuesday 8:30 a.m., 35.5 hours after Sunday 21:00. The creditor bridges the gap by borrowing against its own bills at 4.3% plus 10.0 to 50.0. A member is closed in a year with probability lambda_P = 0.25% (the routes engine's LAMBDA_P). The closed member's net debit is spread equally over the other 19 members; per creditor the gap lies between that and the whole debit, if one creditor received it all.

Table E0. The two intervals, normal weekend and Monday holiday (nominal Eastern clock).

| Case | Settlement would have happened | Stay ends | Collateral delivered against cash | Legal stay interval, hours | Operational interval, hours |
|---|---|---|---|---|---|
| Normal weekend (Friday 6 March 2026) | Sun 08 Mar 21:00 | Mon 09 Mar 17:00 | Tue 10 Mar 08:30 | 20 | 35.5 |
| Monday holiday (Friday 16 January 2026, Martin Luther King Jr. Day) | Mon 19 Jan 21:00 | Tue 20 Jan 17:00 | Wed 21 Jan 08:30 | 20 | 35.5 |

A Monday holiday lengthens neither interval, because the opening moves with the holiday.

Table E1. The Monday cash gap and its cost, on the legal stay interval and on the operational interval.

| Closed member's net debit | Debit, share of its balance | Gap per creditor, share of its balance | Expected cost, bps a year on the whole balance, 20 h (rate + spread) | Same, 35.5 h | Memo: spread only, 20 h | Memo: spread only, 35.5 h | Cost per event to one creditor, bps of its balance, 20 h | Same, 35.5 h |
|---|---|---|---|---|---|---|---|---|
| Closed member at its cap (the full always-on tier) | 20.00% | 1.053% | 0.00050 to 0.00055 | 0.00089 to 0.00097 | 0.00001 to 0.00006 | 0.00002 to 0.00010 | 0.0106 to 0.0115 | 0.0188 to 0.0205 |
| Cohort-average member on the 99th-percentile weekend (open debtor cohort, A, Gaussian, rho 0.30, M 20) | 14.17% | 0.746% | 0.00036 to 0.00039 | 0.00063 to 0.00069 | 0.00001 to 0.00004 | 0.00001 to 0.00007 | 0.0075 to 0.0082 | 0.0133 to 0.0145 |
| Median weekend peak debit | 5.00% | 0.263% | 0.00013 to 0.00014 | 0.00022 to 0.00024 | 0.00000 to 0.00001 | 0.00001 to 0.00003 | 0.0026 to 0.0029 | 0.0047 to 0.0051 |

At most, with the closed member at its cap, the expected bridging cost is 0.00050 to 0.00055 bps a year on the whole balance over the legal interval and 0.00089 to 0.00097 over the operational one: the Monday gap is not a price term. It is a size: 20% of the closed member's balance, 1.05% of each creditor's if spread evenly, all of it at one creditor that received the whole debit, held for up to 35.5 hours. On the 99th-percentile weekend of the open debtor cohort of analysis A the cohort-average net debit is 14.17% of the balance, 0.746% per creditor. The arithmetic does not establish that a bridge is available; the creditor's claim accrues the usage charge at the overnight secured rate while it waits, so the spread-only memo is the closer reading of the net cost.

## 8. The Sunday settlement cash source (analysis F)

Every net debtor, not only a failed one, settles at the Sunday 21:00 Fedwire Funds opening in reserves. Its pledged bills are not reserves and Fedwire Securities is closed until Monday 8:30 a.m., so the debtor pays from its own reserve balance or a collateralized Reserve Bank daylight overdraft, repaid on Monday after the bills are repoed or sold. The requirement: at the Sunday opening the debtor holds reserves or collateralized intraday credit capacity of at least its cap, 20% of the balance, with the collateral pledged at the Reserve Bank separate from the bills pledged to the facility. The facility's price (Section 1 terms) does not include this capacity; the daylight overdraft fee sits in one constant, DOD_FEE, 0.0 bps a year for collateralized overdrafts [reported figure, Federal Reserve Policy on Payment System Risk], with 50.0 bps for uncollateralized overdrafts as a sensitivity. The fee follows the policy's convention (Section II.C and footnote 58): the annual rate is quoted on a 24-hour day and a 360-day year, the effective daily rate is the annual rate over 360, truncated (0.0000138 at 50.0 bps), and it is charged on the average overdraft over the minutes of the 24-hour day, before the $150 fee waiver per reserve-maintenance period. The overdraft is repaid by Monday 12:00 ET: a solvent debtor repays from a delivery-versus-payment sale or bilateral repo of its bills settling Monday morning after the 8:30 a.m. securities opening [author assumption (illustrative)].

| Daylight overdraft fee, bps a year | Expected secured debit settled each Sunday, share of the balance | Overdraft hours | Expected fee, bps a year on the whole balance |
|---|---|---|---|
| 0.0 | 6.509% | 15 | 0.0000 |
| 50.0 | 6.509% | 15 | 0.2919 |

Repaid only at Monday 17:00 (20 hours), the uncollateralized fee would be 0.3892 bps a year; the collateralized fee stays 0.0000.

| Sunday cash source | Requirement | Lendable share (absolute) | S2 |
|---|---|---|---|
| Collateralized Reserve Bank daylight overdraft, Reserve Bank collateral already on the book as loans | Reserve Bank collateral with lendable value of at least the cap (20% of the balance), separate from the bills pledged to the facility | 0.80 | fail |
| Collateralized Reserve Bank daylight overdraft, collateral bought for the purpose | securities pledged at the Reserve Bank of at least the cap (20% of the balance) | 0.60 | fail |
| Reserves held against the weekend outflow | reserves of at least the cap (20% of the balance) | 0.60 | fail |

The fee is negligible either way; the requirement is not. A collateralized overdraft keeps the lendable share at 0.80 only if the Reserve Bank collateral is loans the bank already holds; reserves held, or securities bought to pledge, take it to 0.60. For the seven-day schedule, see Table B6.

## 9. Conventions and limits

- Each member's figure is its peak net debit during the closed window to all counterparties, members and non-members, not its terminal net position; payment paths and the release of queued payments are not modelled. Members are equal in size and form an open debtor cohort whose receivers sit outside the modelled set, so every multi-member statistic describes that cohort, not a closed membership in which signed net positions sum to zero.
- Weekends are independent of each other; the factor is redrawn every weekend. Serial dependence across weekends would change annual incidence, annual maxima and run lengths in ways the engine does not model; at fixed weekly marginals it leaves the expected count of binds unchanged.
- The linear and square-root scalings of the outflow with window hours are illustrative; neither is estimated.
- The calendar constants (Fedwire hours, 2026 and 2027 weekday closings) are reported figures (Federal Reserve Financial Services, Fedwire Funds Service and NSS operating hours, accessed 3 November 2026; Federal Reserve Financial Services, holiday schedules, accessed 3 November 2026) and sit at the top of the script. The 22x6 scenario is announced (90 FR 51356, 17 November 2025), voluntary for participants and not yet in effect. The QFC business-day definition (12 U.S.C. 1821(e)(10)(D)) also excludes days the New York Stock Exchange is closed, Good Friday among them; the Monday-cash hours here use the Reserve Bank calendar only.
- The cap ladder holds the weekend peak debit in balance terms fixed and moves the backing. Lendable share is 1 minus the always-on share throughout, the routes engine's absolute convention, including analysis C, where the buffer's effect is reported only as incremental lending displacement.
- Window lengths are nominal Eastern schedule hours; the elapsed-hours check in Section 4 shows the daylight-saving effect on every printed calendar figure.
- Counting the grossed-up bills (share / 0.98) as non-lendable instead, the S2 boundary is a 9.8 percent always-on share, not 10. The 22x6 lendable share is 0.896 under the routes engine's convention and 0.894 counting the bills, a 0.2-point move; the buffer at which a 20% share's incremental displacement falls to 0.1 is 10.00% under the first and 10.41% under the second, a 0.41-point move (the gross-up on a 20% share).
- Everything is illustrative and calibrated to no bank, facility or member.
