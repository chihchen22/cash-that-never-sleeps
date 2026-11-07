# Model engines for "Cash That Never Sleeps"

This folder holds the five scripts behind every number in the manual, each with its own results file:

| Script | Results file | Manual chapters | Notes |
|---|---|---|---|
| `clearing_cost.py` | `results_clearing_cost.md` | Chapter 3 | this README |
| `mutual_tail.py` | `results_mutual_tail.md` | Chapter 5 | [README_mutual_tail.md](README_mutual_tail.md) |
| `uninsured_panel.py` (data in `cache/`) | `results_panel.md` | Chapter 1 | [README_mutual_tail.md](README_mutual_tail.md), last section |
| `routes.py` | `results_routes.md` | Chapters 4 to 7 | [README_routes.md](README_routes.md) |
| `settlement.py` | `results_settlement.md` | Chapter 6 | [README_settlement.md](README_settlement.md) |

`settlement.py` imports `routes.py` by path; `routes.py` imports `clearing_cost.py` and `mutual_tail.py`; `mutual_tail.py` imports `clearing_cost.py`. Run `clearing_cost.py` first (`mutual_tail.py` reads its printed reference rows from `results_clearing_cost.md`), then `mutual_tail.py`, then `routes.py` (`settlement.py` checks its imported values against `results_routes.md`), then `settlement.py`. `routes.py` and `settlement.py` take `--s2-min BAR` to rerun at another lendable-share bar for screen S2 (default 0.90, the rule of record); the default run already reports the S2 bar sensitivity at 0.75, 0.80, 0.85 and 0.90 (`results_routes.md` Section 9b, `results_settlement.md` Table A6).

## The clearing-cost engine (`clearing_cost.py`)

`clearing_cost.py` reproduces every number in Chapter 3. It prices one year of private protection on a large uninsured corporate deposit (a contract that pays the depositor par when its bank fails and takes over the deposit claim), reads that price as the clearing cost of holding the balance uninsured, and designs and stress-tests a pooled vehicle that could sell that protection.

All parameters are illustrative. Apart from the empirical data in figure 1 (FDIC staff study, Chu et al., May 2026) and the regulatory rules cited next to individual inputs, every parameter is an author assumption, chosen to be plausible and stated openly. None is calibrated to, or an estimate for, any bank, vehicle or investor.

## What it computes

The core formula prices protection per unit of covered balance, per year, as four terms:

    c* = credit + access + standing capacity + frictions

where credit is the expected loss on the deposit claim under a risk-neutral default intensity, access is the cost of funding par until the receivership pays out, standing capacity is the cost of holding resources ready to pay, and frictions are operations, legal and margin. The depositor's own cost of bearing the risk is credit plus access; the gap to the purchased price is the transfer cost.

- **Part I (results Sections 1 to 15): one bank.** The formula for a single bank and three kinds of protection seller (a funded investor vehicle, a bank standby letter of credit, a regional mutual pool), with sensitivities, a market-implied cross-check, tranche economics, a diversified portfolio across many banks and recovery-gap financing.
- **Part II (Sections 16 to 29): a pooled vehicle.** One vehicle writing protection on 50 banks at 2% each, holding a funded T-bill buffer and, optionally, a committed liquidity facility. It covers cash needs at failure, the probability that the vehicle cannot pay par, pricing, the facility provider's cost and wrong-way risk, tranches, stress scenarios, the yield-advantage sweep, who bears the cost, and a challenge register.
- **Part III (Sections 30 to 34): who would write it.** Technology scenarios on frictions and buffer mobility, the investor's return view, and a bank's willingness to pay in a bank-sponsored variant.
- **Part IV (Sections 35 to 44): the reference design.** A risk-free-rate update, the all-funded reference design (20% buffer, no facility) beside a 10/10 buffer-and-facility hybrid, a rule for choosing buffer versus facility, reliability in the year the depositor's own bank fails (Gaussian and Student-t(5) copulas), capacity needed for a stated reliability, Year 2 after a cluster of failures and the cost of reinstatement, the three-party clearing condition, an exact cash-flow check of the formula, settlement rules at the trigger (gross par, par less the advance dividend at day seven, a junior 40% slice of the claim) with the advance dividend linked to the loss, and the banker's term-premium value as a hypothesis for the pilot.

## Requirements

Python 3.10 or later, with numpy and matplotlib. From the repository root:

    pip install -r requirements.txt

`requirements.txt` pins the versions of the reference run (numpy 2.5.2, matplotlib 3.11.1, under Python 3.12.13). Other recent versions of both libraries should reproduce the same numbers; figure rendering may differ in small details. The figures use the Inter font if it is installed and matplotlib's default font otherwise; the numbers are unaffected.

## How to run

From the repository root:

    python -I model/clearing_cost.py

or from inside `model/` with `python -I clearing_cost.py`. Paths are resolved from the script's own location, so both work. A run takes about one minute on a single core and prints a short summary and the exact run time to the console. Importing the script as a module computes the result tables but writes nothing; files are written only when it is run.

## Outputs

- `model/results_clearing_cost.md`: every number, in tables, with the run environment in the header.
- `figures/clearing_cost/fig-01.png` to `fig-11.png` at the repository root, in the engine's own numbering (fig-10 is the conditional shortfall in the year the depositor's own bank fails; fig-11 is the Year-2 shortfall by replenishment regime). The folder is created if absent.

## Seeds, quadrature and determinism

Almost every probability is computed exactly, by quadrature over the common factor of a one-factor copula: 4,001 equally spaced points on [-8, 8] for the Gaussian copula, and a 401 x 240 grid in (z, W) for the Student-t(5) copula (W chi-square with 5 degrees of freedom, on a log grid from 1e-4 to 80). Three seeded Monte Carlo checks run alongside: seed 20261017 (Part I portfolio, 400,000 paths), and seeds 20261018 and 20261019 (Part II, 1,000,000 simulated years each, Gaussian and Student-t).

The output is deterministic: two runs on the same machine produce a byte-identical results file and byte-identical figures. The run time in the results header is rounded to the nearest minute for that reason.

## Key conventions

- Units: basis points a year on the covered balance unless stated. lambda_P is the real-world one-year default probability of a bank (base 0.25%); prices use lambda_Q = mu x lambda_P with mu = 3.
- Risk-free rate r = 4.3% (3-month Treasury bill, FRED DGS3MO 4.28% on 15 October 2026; verify before relying on it). Section 35 shows the headline values at the 3.9% used by an earlier version of the model.
- Pool: 50 banks, each 2% of covered notional; asset correlation 0.20 for prices and 0.30 for failure statistics (illustrative). All of a year's failures are assumed to fall inside one advance-dividend window (the conservative timing standard).
- Prices are under the pricing measure Q; failure probabilities, conditional reliability and Year-2 statistics are real-world (P) quantities.
- Some section titles and notes in the results file carry internal version labels (for example "What the v5 numbers say"); they record when a part of the model was added and do not affect any number.

## Section map of the results file

| Sections | Content |
|---|---|
| 1 to 3 | Parameters; base-case decomposition by provider; bank standby letter of credit (Q price, P price, capital) |
| 4 to 9 | Sensitivity grid, one-at-a-time sensitivities, market-implied cross-check, provider comparison, depositor yield advantage, the cash wedge on $1 billion |
| 10 to 15 | Single-name tranches, diversified portfolio, recovery-gap financing, a regulatory fact, summary, assumptions and decisions |
| 16 to 21 | Pooled vehicle: design and cash timing, state-dependent LGD, cash needs, buffer and facility outcomes, the vehicle's failure probability, the facility provider |
| 22 to 29 | Pooled pricing, the price-reliability trade-off, tranches, stress scenarios, yield-advantage sweep, who pays, challenge register, summary |
| 30 to 34 | Technology scenarios, investor return view, bank willingness to pay, summary |
| 35 | Risk-free rate update: headline values at r 3.9% and 4.3% |
| 36 | Reference design (all-funded 20% buffer) beside the 10/10 hybrid: price, break-even default probabilities, who pays, stress, tranches, frictions, bank willingness to pay, challenge register, weekend triggers |
| 37 | Buffer-versus-facility rule and the facility's no-credit-exposure condition |
| 38 | Reliability given the depositor's own bank fails (shortfall probability, severity, expected unpaid share, expected loss) |
| 39 | Capacity and price to meet round conditional reliability standards, and pool size |
| 40 | Year 2 after 3 and 6 failures (unreplenished, certificate financing, reinstatement), reinstatement cost, excess-of-loss layer |
| 41 | Three-party clearing: price against depositor yield advantage plus bank retention value |
| 42 | Exact cash-flow check of the four-term formula |
| 43 | Summary of the headline numbers Chapter 3 quotes |
| 44 | Settlement rules at the trigger (gross par; par less the advance dividend at day seven; junior 40% slice of the claim), state-dependent advance dividend, iso-reliability by rule, and the banker's term-premium value (pilot hypothesis) |

## Caveats

The model is a transparent pricing lens, not a calibrated risk model. The correlation, the state-dependent LGD mapping, the facility fees, the lock-up premium, the drawn margin, the certificate-financing advance rate and the reinstatement commitment fee have no observed market values; they are swept or labelled as scenarios. Nothing here is legal, regulatory or investment advice.
