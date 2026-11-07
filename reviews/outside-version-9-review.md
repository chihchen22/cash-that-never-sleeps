# Review of outside version 9

Corrected after version 9's own code was run. Reviewer: Claude (Anthropic), working under the author's direction. Edited for publication.

Outside version 9 (a 16-page rewrite of the stage-1 draft) was produced by Gemini Argon (Google) with feedback from GPT Astra (OpenAI). It was built on the stage-1 draft's version 8 and recast the problem as an engineering optimisation over the funded buffer, a committed liquidity facility and the per-bank concentration cap. This summary records what the review found when version 9's results were recomputed with the project's own workpaper wherever its inputs allowed, and its facts were checked against their sources. The process record (`PROCESS.md`, rows A11 to A20, B1 to B5 and C22 to C24) places these findings in the full log.

## Overall finding

Version 9 rebuilt the project's pooled-vehicle model faithfully: its Gaussian-copula tables matched the workpaper to the third decimal. It contributed four ideas that the stage-1 draft adopted, rebuilt in the workpaper, plus an exact cash-flow check. Its headline results, however, rested on an unsourced parameter, a reliability target chosen so the design would pass, and a reliability claim that holds under one tail model only. It also reintroduced claims that had previously been ruled out, some of which turned out to be correct.

## Ideas adopted

| Idea | How it entered the stage-1 draft |
|---|---|
| Measure reliability when the depositor's own bank fails, not per year | Reported under both copulas in the abstract and Section 8.5 |
| A rule for when a committed facility beats a funded buffer | Stated in Section 8.2; it showed that version 8's lead design was dearer than an all-funded buffer at version 8's own spreads, so the all-funded buffer became the reference design |
| Year-2 reliability after a loss year, and replenishment | Section 8.6, rebuilt and corrected |
| A three-party clearing condition (provider price against depositor willingness to pay plus bank retention value) | Section 6, rebuilt without a rate deck |
| Exact discounting check of the four-term formula | Section 4: the formula sits within 0.016 basis points of full discounting |

## Errors found

| Claim in version 9 | Finding |
|---|---|
| 99 percent payment reliability given the depositor's own bank fails | Holds under a Gaussian copula only. Under the Student-t(5) copula, shown in version 9's own table, the shortfall probability at the same 20 percent capacity is 27.7 percent |
| A 50-bank pool is the optimum at a 1.01 percent conditional standard | The 1.01 percent target equals the design's own result (1.008 percent). At a round 1.00 percent, 50 banks need 22 percent capacity. Version 9's own code used a different target, 1.05 percent, also just above the design's 1.008 |
| A pool-size optimum at 20 percent capacity, set against a 5 percent Student-t standard as well as the Gaussian one | Not met under the t(5) copula: at 20 percent capacity the shortfall is 27.7 percent at the trigger, and 8.5 percent after the advance dividend on version 9's own figures. A 5 percent t(5) standard at the trigger needs about 50 percent capacity. Version 9's own code computed this answer (48 percent capacity at 50 banks; optimum 20 banks at 50 percent), and the write-up dropped it |
| Year-2 shortfall table | Overstated after a loss year. The code re-sized each surviving bank to an equal share of the smaller pool (one forty-seventh of the original notional after three failures) while capacity stayed a share of the original notional, so each regime came out at the next weaker regime's figure; the first version of this review diagnosed a row shift, which was wrong. Recomputed: unreplenished 1.75 / 2.21 percent after three or six failures; certificate financing 1.20 / 1.47; full restoration 0.83 / 0.68 |
| A 45 basis point premium on the funded buffer | No source given. Part of its stated rationale, exposure to first-loss credit write-downs, double-counts the credit risk premium already in the price, and its other reasons (an investor governance and illiquidity hurdle, insurers' capital charges) carry no cited figures. It is what made version 9 prefer a buffer-plus-facility design. Kept only as a sweep point |
| Operating balances clear up to a default probability of 0.96 percent | That break-even uses a yield advantage of 100 basis points, not version 9's own willingness to pay of 75, which on version 9's own price gives 0.66 percent |
| A bank breaks even if protection cuts cumulative five-year attrition by 5 points | Compares an annual rebate with a one-off present value. The workpaper gives a cut of about 4.6 points a year in the annual run probability (Section 13 of the paper) |
| 1.18 basis point reinstatement cost; 0.42 basis point excess-of-loss wrap | The 1.18 reproduces from version 9's code, but from an ad hoc expression with an unexplained factor of 0.5 times 0.10, not the cost of a commitment; the 0.42 and the five-point break-even above are computed nowhere in the code. The first version of this review called them not reproducible, which overstated it for the 1.18. The project's workpaper gives 1.1 to 2.1 basis points for reinstatement at a 10 to 20 basis point commitment fee, and, for the excess-of-loss layer at a correlation of 0.30, an expected par payout of 0.7 basis points (Gaussian) or 9.3 (t), of which 0.18 or 2.3 is credit loss |
| A companion workpaper reproduces every number | The cited file was not supplied with version 9, so the new numbers could not be rerun at review. I later obtained it and ran it: it runs clean and reproduces version 9's published tables, and its Monte Carlo (1.046 percent conditional, against 1.008 by quadrature) is roughly consistent with its claim. The faults above are of method, not arithmetic. The first version of this review said the file did not exist; that was wrong |
| Receivership certificates financed by repo at a 20 percent haircut | No evidenced repo market for receivership certificates; treated as a scenario |
| 12 CFR Part 1214 cited for bank supervisory confidentiality | That part is a Federal Housing Finance Agency rule |
| Smaller slips | "Three exposures" followed by four; two different thresholds for the same rule; one table entry inconsistent with its own formula |

## Where version 9 was right and the earlier versions were wrong

- It cited SR 26-2 (17 April 2026) as the current model risk guidance. The earlier versions cited SR 11-7 as current, although SR 26-2 had superseded it.
- Three figures from the FDIC staff study that the earlier versions had excluded as unverifiable were confirmed in the study itself: accounts drawn down by more than 90 percent held 85, 88 and 81 percent of running business deposits at the three banks; First Republic's peak single-day loss was about 23.5 percent; and the SVB bridge bank lost 40 percent of the 6 March balance in its first week.
- Its code reproduces its own published tables.
- The "663 banks" sample size in the NY Fed payments study, also excluded earlier, was confirmed in the paper.

## What version 9 dropped

The views-my-own line and the first-person AI disclosure (it kept a third-person note on its use of AI models); the policy, adverse-selection, signaling and implicit-support discussion; the open questions; and the "safe for one, not for all" framing. All were restored in the stage-1 draft.
