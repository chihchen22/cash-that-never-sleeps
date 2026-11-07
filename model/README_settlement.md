# The settlement engine (`settlement.py`, Chapter 6)

`settlement.py` deepens the routes engine's treatment of the always-on collateralized netting facility (route R7) along the settlement clock. It runs six analyses, each with its own section in `results_settlement.md`:

- **A. Same-weekend factor model.** Cap binding under a one-factor Gaussian and a one-factor Student-t(5) copula, a cap ladder (the backing a member needs to hold its bind frequency at 1 percent of weekends or once in ten years, priced with the routes engine's `r7_price`, with an S2 verdict for each row) and a median sensitivity (Table A5: bind probability at a 10 percent cap and the cap a 1 percent per-member bind needs, for medians of 1 to 5 percent of the balance at sigma 0.5, 0.8 and 1.2). Table A6 repeats the cap-ladder boundary at each S2 bar of the routes engine's sensitivity (0.75 to 0.90): the largest median peak debit that keeps a member's cap binding in at most 1 percent of weekends at the cap the bar allows, with and without the haircut gross-up, and whether the cap test passes at the assumed 5 percent median.
- **B. Closed-window calendar.** Every closed window of the Fedwire Funds Service in 2026 and 2027, the bind probability for each window type, two sizing policies (P1 for the normal weekend, P2 for the longest window) and three schedule scenarios: the current one, the announced 22x6 schedule and a hypothetical seven-day schedule. The seven-day pass is restated as conditional (Table B6): with Fedwire Securities and repo still on weekdays it needs weekend Reserve Bank credit or reserves held against the weekend outflow. A daylight-saving check recomputes every printed calendar figure on elapsed hours.
- **C. Liquidity-buffer sensitivity.** S2 stays on the absolute convention (bills held for the always-on tier are not lendable whether or not they are a buffer). The effect of a buffer is reported separately, as incremental lending displacement relative to a bank that already holds it. Not the base case.
- **D. Sponsored non-members.** The price for a non-member that reaches the facility through a sponsoring member, and what the sponsor bears.
- **E. Monday cash.** The cash gap net creditors face when a member is closed over a weekend, on two intervals: the legal stay interval (Sunday 21:00 to Monday 17:00, 20 hours; the stay is on termination, liquidation and netting rights, not on payments in general) and the operational collateral-to-cash interval (the stay ends after the 3:15 p.m. Fedwire Securities secondary-market cutoff, so delivery waits for Tuesday 8:30 a.m., 35.5 hours). A Monday holiday lengthens neither.
- **F. Sunday settlement cash source.** Every net debtor settles at the Sunday 21:00 Fedwire Funds opening in reserves, from its own reserves or a collateralized Reserve Bank daylight overdraft. A solvent debtor repays it by Monday 12:00 from a delivery-versus-payment sale or bilateral repo of its bills settling after the 8:30 a.m. securities opening. The engine states the requirement (reserves or collateralized intraday credit capacity of at least the cap, collateral separate from the facility's bills), the lendable share under each cash source, and the overdraft fee.

## The simulated variable

Each member's weekend figure is its peak net debit during the closed window to all counterparties, members and non-members, as a share of its always-on tier. The lognormal is the distribution of that peak, not of the terminal net position. Per-member results (the bind probability, the per-member cap ladder rows, the 1.56 percent median boundary, the backing for a 1 percent cap) are the headline, conditional on the assumed distribution.

Every multi-member statistic (the system queue, the joint cap ladder, any-binds, a quarter or more binding, the pooled cap, the system-average secured debit) describes an open debtor cohort: members drawn as net debtors whose receivers sit outside the modelled set. These are not closed-membership results, in which signed net positions would sum to zero.

Section 2 re-checks every value imported from the routes engine against `results_routes.md` and runs the method checks. Every parameter not imported is labelled an author assumption (illustrative), an author convention, or a reported figure with its source. All numbers are illustrative and calibrated to no bank.

## Constants to know

- `DOD_FEE` (section 1, F): the daylight overdraft fee at the Sunday opening, 0 bps a year for collateralized overdrafts under the Federal Reserve Policy on Payment System Risk; `DOD_FEE_SET` adds the 50 bps uncollateralized fee as a sensitivity, computed on the policy's convention (Section II.C and footnote 58: a 24-hour day and a 360-day year, the daily rate truncated to 0.0000138; `PSR_YEAR_DAYS` and `PSR_DAILY_DP`). `DOD_REPAY_HOUR` (author assumption) sets the overdraft's length; the results also give the fee if the overdraft ran to 17:00.
- `SEC_OPEN_HOUR`, `SEC_CUTOFF_HOUR`: Fedwire Securities opening (8:30 a.m. ET) and secondary-market transfer cutoff (3:15 p.m. ET). The 2025 schedule expansion covers Fedwire Funds and NSS only.
- The calendar constants (Fedwire Funds hours, 2026 and 2027 Reserve Bank holidays) sit at the top of the script. Window lengths are nominal Eastern schedule hours by convention; `TZ_NY` is used only for the elapsed-hours check.

## Run

From the repository root:

```
python -I -B model/settlement.py
python -I -B model/settlement.py --s2-min 0.80    # sensitivity run at another S2 bar, not the rule of record
```

`--s2-min` (default 0.90, the rule of record) is read by `routes.py` on import, so both engines use the same bar. Run `routes.py` at the same bar first: the parity check reads `results_routes.md`.

Running the script writes `model/results_settlement.md` and `figures/settlement/fig-S01.png` to `fig-S03.png` (the folder is created if absent). It needs Python 3.9 or later for `zoneinfo`, with the America/New_York time zone available (macOS and Linux supply it; elsewhere install the `tzdata` package). Most of the run time goes to importing the routes engine, which computes its own tables.

## Seeds and determinism

The same-weekend Monte Carlo uses seed 20261120 (500,000 weekends). The imported engines carry their own seeds. `results_settlement.md` and the figures are byte-identical across runs; the run time is printed to the console only.

## Imports

`model/routes.py` is loaded by path with `importlib`, and it loads the clearing-cost and mutual-tail engines itself. Its main block is guarded, so importing it writes nothing. No code is copied from it. The engine uses its R7 parameters (share, haircut, the four terms, the outflow median and sigma set), `r7_terms`, `r7_price`, `p_bind`, the S2 threshold, and the clearing-cost engine's default intensity `LAMBDA_P`, Student-t degrees of freedom and quadrature helpers.

## Figures

- `fig-S01.png`: probability that at least k of an open cohort of 20 net debtors bind on the same weekend, by rho, under the Gaussian and t(5) factors.
- `fig-S02.png`: the closed windows of 2026 on a strip, with the bind probability for each window type under linear and square-root scaling.
- `fig-S03.png`: lendable share against always-on share on the absolute convention (the S2 metric, the same at every buffer), with 1 minus the incremental lending displacement at each buffer drawn separately as a different quantity.
