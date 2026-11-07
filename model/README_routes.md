# The routes engine (`routes.py`, Chapters 4 to 7)

`routes.py` puts nine routes for keeping a $100 million corporate balance above the insured limit at a regional bank on one price list (bps a year per unit of the balance): pledged securities, an FHLB standby letter of credit, reciprocal placement, letting the balance go, the third-party funded vehicle of Chapter 3, the mutual with a Treasury-backed tail, an always-on collateralized netting facility, one ledger carrying both a credit tranche and a liquidity tranche, and a prefunded joint-account instant-settlement arrangement (R9).

For each route it records the lendable share, the capacity consumed and who bears the self-insured cost (credit + access) under the pricing and real-world measures. It scores every route against five pass / fail / open screens, applies a stated rule to name a champion and a challenger for each problem, re-sizes the champion's capacity to the reliability standard across one-at-a-time sensitivities, and gives annual dollar costs for a $50bn and a $5bn bank.

Routes with no failure payoff carry reported or assumed fee ranges (Chapter 4), labelled as such; they are not model numbers. Every parameter is illustrative and calibrated to no bank.

## R9: prefunded joint-account instant settlement

R9 follows the design of The Clearing House RTP network. An operator (which need not be a bank) holds a joint account at a Reserve Bank; each member prefunds a position equal to a disclosed share of its tokenized balance; weekend transfers between members settle instantly and finally against positions in central bank money; positions can be funded or defunded at any hour by FedNow liquidity management transfers (up to $500 million each) where the participant enables them; a payment beyond the sender's position is rejected, not queued.

Every R9 parameter sits in one labelled block in section 1 of the script. Reported figures: IORB (3.90 percent), the 3-month bill (4.13 percent, coupon-equivalent), the per-payment fee ($0.045 per payment sent, negligible in bps), the $10 million per-payment limit and the liquidity management transfer limit. Author assumptions, as ranges: credit, access (operator participation and membership), the loan spread over bills, frictions. The switch `R9_JA_INTEREST` is `True` in the base, following the RTP joint account, whose balances earn IORB by a Board order specific to it (effective 7 June 2023); `False` is the sensitivity for a new joint account without such an order.

R9 is priced in the same four terms as every other route. Capacity is the opportunity cost of reserves held in the joint account instead of loans, measured against bills: the prefunded share times (the loan spread over bills plus the bill yield over IORB) when the balance earns IORB, or times (the loan spread plus the whole bill yield) when it earns nothing. Lendable share is 1 minus the prefunded share (absolute convention), and the prefunded slice is not counted as HQLA. S1 is scored open: a new joint account needs Reserve Bank approval under the Board's 2017 guidelines, not yet sought, which the screen scale scores as it scores R2's and R6's unsettled approvals. The rule is run strictly and with open items resolved, and once more with the interest switch at its other setting. Rejection without weekend top-ups is computed by prefunded share.

## R7's Sunday settlement cash (memo)

At the Sunday 9:00 p.m. Fedwire Funds opening a net debtor settles in reserves, so it needs capacity of at least its cap. R7's published price assumes case (a): Reserve Bank credit against loans already pledged, within net debit cap headroom. Section 7 of the results adds memo rows for (b1) securities bought and pledged, at R7's encumbrance spread, and (b2) reserves held for the Sunday opening, on R9's reserve convention, each computed from the engine's constants, with the crossover against R9 and the shares of new reserves or bought securities at which R9 wins. Section 9 states the rule's champion for problem (b) in each case. The haircut gross-up is not charged again; it sits in frictions.

## The S2 bar

S2 is scored from each variant's lendable share at the bar `S2_MIN`, 0.90 by default, the rule of record. Section 9b of the results, computed in every run, re-scores S2 at 0.75, 0.80, 0.85 and 0.90 at the published route parameters: every route's verdict, the champion and challenger for each problem under both readings, and the largest always-on or prefunded share that passes for R7, R8 and R9. `--s2-min BAR` reruns the whole engine at another bar; the results file then records that bar in its header.

Section 10b of the results sorts the list by deposit type: a plain account above the insured limit runs on the run clock only, a tokenized balance on the settlement clock whether insured or not where its transfers are netted between banks, and a tokenized balance above the limit on both. Each row is a priced variant with the open items resolved and S2 not applied, so the table prices the risk each type carries and does not choose a route. For both clocks the hedges stack (R8 is R6 plus R7 less the shared ledger; R6 plus R9 is the pairing with no shared ledger), and the lendable shares add on the absolute convention. The engine checks that the R8 row reproduces R6 plus R7 less the saving before it writes the table.

## Run

From the repository root:

```
python -I -B model/routes.py
python -I -B model/routes.py --s2-min 0.80    # sensitivity run at another S2 bar, not the rule of record
```

Run time is about three minutes. Running the script writes `model/results_routes.md` and `figures/routes/fig-U01.png` to `fig-U10.png` (the folder is created if absent). Importing the module computes everything and writes nothing. `results_routes.md` is byte-identical across runs; seeds are listed in its header.

## Imports

Both engines are loaded by path with `importlib`, and no code is copied from either:

- `model/clearing_cost.py`: the clearing-cost engine of Chapter 3 (single-name and pooled vehicle, copulas, reliability).
- `model/mutual_tail.py`: the mutual-tail engine of Chapter 5. It imports the clearing-cost engine under the same module name, so both share one copy in memory.

Section 2 of `results_routes.md` checks every imported headline against its quoted value.
