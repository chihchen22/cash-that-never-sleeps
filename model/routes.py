"""
routes.py (Cash That Never Sleeps, Chapters 4 to 7): one price list for keeping a large uninsured commercial
deposit at a regional bank.

What it does
    Puts nine routes for keeping a $100 million corporate balance above the insured limit at a regional bank on
    one price list (bps a year per unit of the balance), records for each its lendable share, the capacity it
    consumes and who bears the risk the balance carries, scores each against five pass / fail / open screens, and
    names a champion and a challenger by a stated rule. Model numbers come from the two engines imported below.
    Routes the engines cannot price, because they have no failure payoff (R1 to R4), carry the fee ranges of
    Chapter 4, labelled as reported figures or author assumptions, not model numbers. R9, a prefunded joint-account
    instant-settlement arrangement, is priced from author assumptions held in one labelled block (section 1).

Imports (by path with importlib, never copied)
    model/clearing_cost.py   the clearing-cost engine (Chapter 3)
    model/mutual_tail.py     the mutual-tail engine (Chapter 5; it imports the clearing-cost engine under the same
                             module name, so both share one copy)
Outputs  model/results_routes.md; figures/routes/fig-U01.png to fig-U10.png.
         Importing this module computes every table and writes nothing.
Run      python -I -B model/routes.py   (from the repository root)
         --s2-min BAR reruns the whole engine with the lendable-share screen S2 at BAR (default 0.90, the rule of
         record); the results file then records the bar it was run at. The S2 bar sensitivity (results Section 9b)
         is computed in every run at 0.75, 0.80, 0.85 and 0.90, so the default run needs no second run.
Seeds    20261110 (weekend outflow Monte Carlo check), 20261111 (illustrative weekend path in fig-U08). The imported
         engines carry their own seeds. Results are deterministic; the run time is printed to the console only.

All parameters are illustrative and calibrated to no bank. Each is labelled [author assumption] or
[reported figure, source] in the results file.
"""

import sys
import time
import math
import argparse
import importlib.util
from pathlib import Path

_T_START = time.perf_counter()
sys.dont_write_bytecode = True                       # importing the engines must leave nothing in their folders

HERE = Path(__file__).resolve().parent               # model/
ROOT = HERE.parent                                   # repository root
RESULTS_MD = HERE / "results_routes.md"
FIGURES = ROOT / "figures" / "routes"                # created at run time if absent
SCRIPT_NAME = "routes.py"
N_FIGS = 10
FIG = lambda n: FIGURES / f"fig-U{n:02d}.png"


def _load(name, path):
    """Import a module from its file path, once."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":                           # validate the command line before the engines load
    _ap = argparse.ArgumentParser(description="Cash That Never Sleeps: one price list for the large uninsured deposit.")
    _ap.add_argument("--s2-min", type=float, default=None, help="lendable-share bar of screen S2 (default 0.90, the rule "
                     "of record)")
    _ap.parse_args()

cc = _load("clearing_cost", HERE / "clearing_cost.py")
mt = _load("mutual_tail", HERE / "mutual_tail.py")
if mt.cc is not cc:
    raise RuntimeError("the mutual engine did not reuse the imported clearing-cost engine")
import numpy as np                                   # noqa: E402

# =============================================================================
# 1. PARAMETERS (each defined once; rates as decimals, 1 bp = 0.0001)
# =============================================================================
BP = cc.BP
# --- base case, imported from the clearing-cost engine's parameter block [author assumptions there] --------------------
LAMBDA_P, MU, LGD, ADV, D_YEARS = cc.LAMBDA_P, cc.MU, cc.LGD_DEP, cc.ADV_DIV, cc.D_YEARS
R_FREE, S_B = cc.R_FREE, cc.S_B
RHO_PRICE, RHO_REL = cc.V5_RHO_MID, cc.V5_RHO_FAIL    # 0.20 for prices, 0.30 for reliability
NU = cc.V5_T_NU
BALANCE = 100e6                                      # the corporate balance above the insured limit [author assumption]
# --- screens [author assumption: thresholds of the comparison] ----------------------------------------------
S2_MIN_DEFAULT = 0.90                                # lendable share at least 0.9: the rule of record


def _s2_min_arg(argv=None):
    """The S2 bar from the command line (--s2-min), read on import so that every table, and every engine importing this
    one with the same command line, uses it; default S2_MIN_DEFAULT."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--s2-min", type=float, default=S2_MIN_DEFAULT)
    bar = ap.parse_known_args(sys.argv[1:] if argv is None else argv)[0].s2_min
    if not 0.0 < bar <= 1.0:
        raise SystemExit(f"--s2-min must lie in (0, 1], got {bar}")
    return bar


S2_MIN = _s2_min_arg()                               # S2 bar of this run (default 0.90)
S2_DEFAULT_RUN = abs(S2_MIN - S2_MIN_DEFAULT) < 1e-12
S2_BARS = [0.75, 0.80, 0.85, 0.90]                   # S2 bar sensitivity (Section 9b), computed in every run
S5_STD = 0.01                                        # P(not paid in full given own bank fails) at most 1%, Gaussian, rho 0.30
# --- R1 pledged securities ----------------------------------------------------------------------------------
R1_OVERCOLL = 1.10                                   # [reported figure, Cal. Gov. Code 53651 and 53652, via a secondary source]
R1_HELD = (10 * BP, 30 * BP)                         # pledged from securities already held [author assumption, Chapter 4]
R1_SPREAD = (150 * BP, 300 * BP)                     # loan-to-security spread if bought [author assumption, Chapter 4]
# --- R2 FHLB standby letter of credit -----------------------------------------------------------------------
R2_FEE = (10.5 * BP, 18.0 * BP)                      # [reported figure, FHLBank Des Moines 2026; FHLBank San Francisco 2025;
                                                     #  FHLBank Boston 2022; FHLBank Topeka 2023]
R2_FEE_VAR, R2_FEE_OTHER = 35 * BP, 20 * BP          # variable-balance letters at one district; other purposes at one district
R2_STOCK = 10 * BP                                   # activity stock, 10 bps of the letter [reported figure, FHLBank Des Moines 2026]
# --- R3 reciprocal placement --------------------------------------------------------------------------------
R3_FEE = 12.5 * BP                                   # [reported figure, Chain Bridge Bancorp 2026] (one bank's disclosure)
R3_UPLIFT_SET = [0.0, 10 * BP, 25 * BP]              # rate the network's takers require [author assumption]
R3_UPLIFT = 10 * BP                                  # base of the sweep [author assumption]
# --- R4 let it go and replace the funding ---------------------------------------------------------------------
R4_SPREAD = (50 * BP, 300 * BP)                      # [author assumption, Chapter 3]
# --- R7 always-on collateralized netting facility (Chapter 6) [author assumptions] ---------------
R7_SHARE = 0.20                                      # always-on share of the tokenized balance
R7_HAIRCUT = 0.02                                    # haircut on bills
R7_CREDIT = (0.0, 1 * BP)
R7_ACCESS = (2 * BP, 5 * BP)
R7_ENC = (25 * BP, 100 * BP)                         # encumbrance spread on the bill slice
R7_FRIC = (3 * BP, 8 * BP)
R7_SHARE_SET = [0.05, 0.07, 0.10, 0.20, 0.35, 0.50]
R7_OUT_MED = 0.25                                    # weekend net outflow, median share of the always-on tier (illustrative)
R7_OUT_SIG = 0.8                                     # lognormal sigma (illustrative)
R7_OUT_SIG_SET = [0.5, 0.8, 1.2]
R7_WEEKENDS = 52
R7_MC_N, R7_MC_SEED, R7_PATH_SEED = 1_000_000, 20261110, 20261111
# --- R8 one ledger, two tranches [author assumptions] ---------------------------------------------------------
R8_ACC_SHARE = 0.5                                   # share of the smaller structure's access term saved
R8_FRIC_SAVE = 1 * BP                                # frictions saved by one agent, one ledger
R8_SHARE_SET = [0.0, 0.5, 1.0]                       # 0 = no saving; 1 = full access term saved (plus the 1 bp)
# --- R9 prefunded joint-account instant settlement (the design of The Clearing House RTP network) ---------------
#     An operator holds a joint account at a Reserve Bank; each member prefunds a position, a disclosed share of its
#     tokenized balance, during Fedwire hours; weekend transfers between members settle instantly and finally against
#     positions in central bank money; positions can be topped up at any hour by FedNow liquidity management transfers
#     from the member's master account; a payment beyond the sender's position is rejected, not queued.
#     Each value is labelled: reported figures carry their source (accessed 3 November 2026); the rest are author
#     assumptions (illustrative), given as ranges.
R9_SHARE = 0.20                                      # prefunded position, share of the tokenized balance (= R7's always-on share)
R9_SHARE_SET = list(R7_SHARE_SET)
R9_CREDIT = (0.0, 0.5 * BP)                          # prefunded, final central bank money: about zero [author assumption]
R9_ACCESS = (2 * BP, 6 * BP)                         # operator participation and membership [author assumption]; the
                                                     # per-payment fee ($0.045 per payment sent, nothing to receive) is
                                                     # negligible in bps [reported figure, The Clearing House RTP fees]
R9_LOAN_SPREAD = (25 * BP, 100 * BP)                 # loan yield over the 3-month bill [author assumption: R7's
                                                     # encumbrance spread on the bill slice]
R9_IORB = 0.0390                                     # interest on reserve balances since 17 Sep 2026 [reported figure,
                                                     # Board of Governors]
R9_BILL = 0.0413                                     # 3-month bill, coupon-equivalent [reported figure, US Treasury]
R9_JA_INTEREST = True                                # base: joint-account balances earn IORB, the RTP precedent (Board order
                                                     # effective 7 June 2023, specific to RTP); False is the sensitivity
                                                     # for a new joint account without such an order
R9_FRIC = (2 * BP, 6 * BP)                           # top-up and defunding operations [author assumption]
R9_LMT_MAX = 500e6                                   # FedNow liquidity management transfer limit per transfer [reported
                                                     # figure, FedNow Service operating procedures v3.7, 13 Oct 2026]
# --- banks [author assumptions] -------------------------------------------------------------------------------
BANKS = [("$50bn bank", 50e9), ("$5bn community bank", 5e9)]
LIAB_RATIO = 0.90
COVERED_SHARE = 0.20
RECIP_TIERS = [(1e9, 0.50), (9e9, 0.40), (math.inf, 0.30)]   # [reported figure, 12 CFR 337.6(e); FDIC 2026]
RECIP_MAX = 30e9
S_REP_SET = mt.S_REP_SET                             # replacement funding spread 20 to 80 [author assumption, mutual model]
WTP_CELLS = mt.WTP_CELLS                             # retention cells (V, dP_run) [author assumption, mutual model]
ANNUITY = mt.ANNUITY
# --- sensitivities on the champion (each re-sizes capacity to the S5 standard) -----------------------------
SENS_LP = [0.0010, 0.0025, 0.0050, 0.0100]
SENS_MU = [2.0, 3.0, 4.0, 5.0]
SENS_LGD = [0.15, 0.25, 0.40]
SENS_RHO = [0.10, 0.20, 0.30]
SENS_OPP = list(mt.OPP_SET)                          # 50, 100, 150
SENS_FM = list(mt.F_M_SET)                           # 2, 5, 10
SENS_SLOCK = [5 * BP, 10 * BP, 15 * BP]              # R5 vehicle's lock-up premium (its analogue of reserve carry)
SENS_F = [10 * BP, 15 * BP, 20 * BP]                 # R5 vehicle's frictions range

# =============================================================================
# 2. THE RISK THE BALANCE CARRIES (self-insured cost: credit + access)
# =============================================================================
SI_Q = cc.components(k=0.0, f=0.0)
SI_P = cc.components(mu=1.0, k=0.0, f=0.0)
SELF = {"Q": SI_Q["credit"] + SI_Q["access"], "P": SI_P["credit"] + SI_P["access"]}
ACC_UNIT = (1.0 - ADV - LGD) * (R_FREE + S_B) * D_YEARS     # access per unit of failed balance (clearing-cost engine's rule)

# =============================================================================
# 3. ROUTE ECONOMICS
# =============================================================================
# --- R5: the clearing-cost engine's funded vehicle -----------------------------------------------------------------------
R5_SINGLE = cc.components(k=cc.FUND_K, f=cc.FUND_F)
R5_REF = cc.ref8
R5_REF_T = cc.pool_price(**{**cc.V8_REF, "copula": "t"})["c_star"]
K_REF = int(round(cc.V8_REF["theta"] * cc.V5_N))
K_STD = cc._k_from_curve(cc.rel8_curve["gauss"], S5_STD)
K_STD_T = cc._k_from_curve(cc.rel8_curve["t"], cc.V8_N_STD["t"])
R5_STD = cc.pool_price(**{**cc.V8_REF, "theta": K_STD / cc.V5_N})
R5_STD_T = cc.pool_price(**{**cc.V8_REF, "theta": K_STD / cc.V5_N, "copula": "t"})["c_star"]
R5_TSTD = cc.pool_price(**{**cc.V8_REF, "theta": K_STD_T / cc.V5_N})
R5_SF = {("ref", c): cc.rel8_curve[c][K_REF] for c in ("gauss", "t")}
R5_SF.update({("std", c): cc.rel8_curve[c][K_STD] for c in ("gauss", "t")})
R5_SF.update({("tstd", c): cc.rel8_curve[c][K_STD_T] for c in ("gauss", "t")})

# --- R6: the mutual with a tail -------------------------------------------------------------------------------
R6 = {"ref": mt.base["ref"], "alt": mt.base["alt"]}
R6_B = mt.base_B["ref"]
R6_T = {"ref": mt.price(cop="t", X=mt.X_REF)["pi"], "alt": mt.price(cop="t", X=mt.X_ALT)["pi"]}
R6_SF = {(k, c): mt.rel[(c, RHO_REL, "median", k)]["short"] for k in ("ref", "alt") for c in ("gauss", "t")}
R6_LEND = 1.0 - mt.THETA_M                            # member's capital contribution sits in bills at the mutual
R6_ACCESS = R6["ref"]["acc_mut"] + R6["ref"]["acc_tail"]

# --- R7: always-on netting facility -----------------------------------------------------------------------------
def r7_terms(share=R7_SHARE, end=0):
    """The four terms at the low (end 0) or high (end 1) inputs, bps a year on the whole tokenized balance."""
    return dict(credit=R7_CREDIT[end], access=R7_ACCESS[end], capacity=share * R7_ENC[end], frictions=R7_FRIC[end])


def r7_price(share=R7_SHARE, end=0):
    return sum(r7_terms(share, end).values())


R7_LO, R7_HI = r7_price(end=0), r7_price(end=1)
R7_BASE = 0.5 * (R7_LO + R7_HI)
R7_BILLS = R7_SHARE / (1.0 - R7_HAIRCUT)              # bills positioned per unit of tokenized balance
R7_LEND = 1.0 - R7_SHARE
R7_SHARE_MAX_S2 = 1.0 - S2_MIN                        # largest always-on share that passes S2
R7_SHARE_ROWS = [(s, r7_price(s, 0), r7_price(s, 1), 1.0 - s) for s in R7_SHARE_SET]
# moved loss if the bank is closed after a weekend in which the capped outflow left (upper bound: every failure
# preceded by a full-cap weekend outflow) = share x self-insured cost [author's reading]
R7_MOVED = {m: R7_SHARE * SELF[m] for m in ("P", "Q")}


def p_bind(sig, med=R7_OUT_MED):
    """P(weekend net outflow > always-on tier), outflow / tier lognormal with median med and sigma sig."""
    return 1.0 - cc._ND.cdf(math.log(1.0 / med) / sig)


_rng7 = np.random.default_rng(R7_MC_SEED)
_z7 = _rng7.standard_normal(R7_MC_N)
R7_BIND = []
for sg in R7_OUT_SIG_SET:
    p = p_bind(sg)
    mc = float((R7_OUT_MED * np.exp(sg * _z7) > 1.0).mean())
    se = math.sqrt(mc * (1 - mc) / R7_MC_N)
    R7_BIND.append(dict(sig=sg, p=p, year=1.0 - (1.0 - p) ** R7_WEEKENDS, n=R7_WEEKENDS * p, mc=mc, se=se,
                        z=(mc - p) / se if se > 0 else 0.0))
del _z7

# --- R8: one ledger, two tranches -----------------------------------------------------------------------------
A_SMALL = min(R6_ACCESS, R7_ACCESS[0])                # the smaller structure's access term (clearing-cost engine's four-term sense)


def r8_saving(s, a_small=A_SMALL):
    return 0.0 if s <= 0 else s * a_small + R8_FRIC_SAVE


R8_SAVE = {s: r8_saving(s) for s in R8_SHARE_SET}
R8_LO = R6["ref"]["pi"] + R7_LO - R8_SAVE[1.0]
R8_HI = R6["ref"]["pi"] + R7_HI - R8_SAVE[0.0]
R8_BASE = R6["ref"]["pi"] + R7_BASE - R8_SAVE[R8_ACC_SHARE]
R8_SAVE_ALT = {s: r8_saving(s, R7_ACCESS[0]) for s in R8_SHARE_SET}      # memo: R7's membership access as the term
R8_SAVE_ALT_HI = {s: r8_saving(s, R7_ACCESS[1]) for s in R8_SHARE_SET}
R8_LEND = 1.0 - mt.THETA_M - R7_SHARE
R8_SHARE_MAX_S2 = 1.0 - S2_MIN - mt.THETA_M

# --- R9: prefunded joint-account instant settlement ------------------------------------------------------------
def r9_terms(share=R9_SHARE, end=0, interest=R9_JA_INTEREST):
    """The four terms at the low (end 0) or high (end 1) inputs, bps a year on the whole tokenized balance. Capacity is
    the opportunity cost of reserves held in the joint account instead of loans, measured against bills: the loan
    spread over bills plus the bill yield over IORB when the balance earns IORB, plus the whole bill yield when it earns
    nothing."""
    lost = R9_LOAN_SPREAD[end] + R9_BILL - (R9_IORB if interest else 0.0)   # loan yield less what the balance earns
    return dict(credit=R9_CREDIT[end], access=R9_ACCESS[end], capacity=share * lost, frictions=R9_FRIC[end])


def r9_price(share=R9_SHARE, end=0, interest=R9_JA_INTEREST):
    return sum(r9_terms(share, end, interest).values())


R9_LO, R9_HI = r9_price(end=0), r9_price(end=1)
R9_BASE = 0.5 * (R9_LO + R9_HI)
R9_LEND = 1.0 - R9_SHARE                              # absolute convention: the prefunded position is not lendable
R9_SHARE_MAX_S2 = 1.0 - S2_MIN
R9_ALT = not R9_JA_INTEREST                          # the other setting of the interest switch
R9_ALT_LO, R9_ALT_HI = r9_price(end=0, interest=R9_ALT), r9_price(end=1, interest=R9_ALT)
R9_ALT_BASE = 0.5 * (R9_ALT_LO + R9_ALT_HI)
R9_SHARE_ROWS = [(s, r9_price(s, 0), r9_price(s, 1), r9_price(s, 0, R9_ALT), r9_price(s, 1, R9_ALT), 1.0 - s)
                 for s in R9_SHARE_SET]
# R9 against R7 at the same share: base prices are linear in the share, so they cross once
_r9b = lambda sh: 0.5 * (r9_price(sh, 0) + r9_price(sh, 1))
_r7b = lambda sh: 0.5 * (r7_price(sh, 0) + r7_price(sh, 1))
R9_BE_SHARE = (_r7b(0.0) - _r9b(0.0)) / ((_r9b(1.0) - _r9b(0.0)) - (_r7b(1.0) - _r7b(0.0)))
# rejection, not queueing: a weekend payment beyond the position is rejected. Without a weekend top-up the
# position is exceeded when the weekend peak debit (lognormal, median R7_OUT_MED x R7_SHARE of the balance, the
# routes engine's outflow) exceeds the share; the rejected amount is the excess
_R9_PEAK_MED = R7_OUT_MED * R7_SHARE


def r9_reject(share, sig=R7_OUT_SIG):
    """P(a payment is rejected on a weekend) and E[rejected amount], share of the balance, no weekend top-up."""
    d2 = math.log(_R9_PEAK_MED / share) / sig
    p = cc._ND.cdf(d2)
    e = _R9_PEAK_MED * math.exp(sig * sig / 2) * cc._ND.cdf(d2 + sig) - share * p
    return p, e


R9_REJ = [(sh, *r9_reject(sh)) for sh in R9_SHARE_SET]

# --- R7's Sunday 9:00 p.m. settlement cash, memo (the published R7 price is case a) ------------------------------
#     At the Sunday opening a net debtor settles in reserves; the capacity it needs (the cap, the always-on share) comes
#     from (a) Reserve Bank daylight credit against loans already pledged, within net debit cap headroom: no extra term,
#     the published case; (b1) securities bought and pledged at the Reserve Bank: R7's encumbrance spread on a further
#     share; (b2) reserves held for the Sunday opening: R9's reserve convention, the loan spread over bills plus the bill
#     yield over IORB. The bills' haircut gross-up (share / (1 - haircut)) is not charged again: it sits in frictions.
R7_SUN_LABEL = {
    "a": "(a) Reserve Bank credit against loans already pledged, within net debit cap headroom (published)",
    "b1": "(b1) Securities bought and pledged at the Reserve Bank, at R7's encumbrance spread",
    "b2": "(b2) Reserves held for the Sunday opening, on R9's reserve convention (loan spread over bills + bill over IORB)"}


def r7_sunday_extra(case, share=R7_SHARE, end=0):
    """Extra standing-capacity term for the Sunday settlement cash, bps a year on the whole tokenized balance."""
    if case == "a":
        return 0.0
    if case == "b1":
        return share * R7_ENC[end]
    if case == "b2":
        return share * (R9_LOAN_SPREAD[end] + R9_BILL - R9_IORB)
    raise ValueError(case)


def r7_sunday_price(case, share=R7_SHARE, end=0):
    return r7_price(share, end) + r7_sunday_extra(case, share, end)


def _lin_base(f):
    """Intercept and slope in the share of a base price that is linear in the share."""
    return f(0.0), f(1.0) - f(0.0)


R7_SUN = {}
_r9_ic, _r9_sl = _lin_base(_r9b)
for _c in R7_SUN_LABEL:
    _lo, _hi = r7_sunday_price(_c, end=0), r7_sunday_price(_c, end=1)
    _ex = 0.5 * (r7_sunday_extra(_c, end=0) + r7_sunday_extra(_c, end=1))
    _ic, _sl = _lin_base(lambda sh, c=_c: 0.5 * (r7_sunday_price(c, sh, 0) + r7_sunday_price(c, sh, 1)))
    if _r9_ic <= _ic and _r9_sl <= _sl:
        _cross = None                                 # R9 cheaper at every share
    else:
        _cross = (_ic - _r9_ic) / (_r9_sl - _sl)
    R7_SUN[_c] = dict(lo=_lo, hi=_hi, base=0.5 * (_lo + _hi), lend=1.0 - R7_SHARE * (1 if _c == "a" else 2),
                      ex_base=_ex, ic=_ic, sl=_sl, cross=_cross)
R7_SUN_CHECK = abs(R7_SUN["a"]["base"] - R7_BASE) + (0.0 if R7_SUN["a"]["cross"] is None      # R9 cheaper at every share
                                                       else abs(R7_SUN["a"]["cross"] - R9_BE_SHARE))
# the share of the Sunday capacity from new reserves (b2) or bought securities (b1), the rest from loans already
# pledged, at which R9's base equals R7's at the published 20% share
R7_SUN_TIE = {c: (R9_BASE - R7_BASE) / R7_SUN[c]["ex_base"] for c in ("b1", "b2")}

# --- R2 and R3 economics ------------------------------------------------------------------------------------------
R2_MOVED = dict(SELF)                                 # loss moved to the fund through the super-lien
R3_PRICES = [(u, R3_FEE + u) for u in R3_UPLIFT_SET]
R1_BOUGHT = (R1_OVERCOLL * R1_SPREAD[0], R1_OVERCOLL * R1_SPREAD[1])

# =============================================================================
# 4. WHO BEARS THE RISK (credit + access), under Q and under P [author's reading]
# =============================================================================
BEARERS = ["Depositor", "Bank's own encumbered collateral", "Deposit insurance fund", "FHLB super-lien",
           "Private buffer", "Mutual members", "Leaves with the balance"]


def _bearer_row(**kw):
    return {b: kw.get(b, 0.0) for b in BEARERS}


def pool_bearers(cap, measure):
    """The clearing-cost engine's pooled vehicle (50 equal names, gross par at T+0): buffer pays up to cap, the depositor the rest."""
    pd = LAMBDA_P if measure == "P" else MU * LAMBDA_P
    D = mt.dist(mt.P50, pd, RHO_PRICE, "gauss")
    s = mt.stack(D, "gross", 0.0, 0.0, cap)
    unpaid = float((D["D"] * np.clip(mt.SG - cap, 0.0, None)[None, :]).sum())
    return _bearer_row(**{"Private buffer": s["el_tail"] + s["acc_tail"], "Depositor": s["el_pub"] + unpaid * ACC_UNIT})


_DPQ = mt.price_D(mt.PB)


def r6_bearers(d, measure):
    """Mutual stack: members to A, tail investors to X, depositor above X; rule-M access sits with the receivership."""
    D = _DPQ[0] if measure == "P" else _DPQ[1]
    o = mt.stackq(D, d["q"], d["theta"], d["mpi"], d["T"], adv=d["adv"])
    acc_unit = (1.0 - mt.A_BASE - LGD) * mt.ACC
    acc_b = (1.0 - d["q"]) * o["e_S"] * acc_unit
    acc_m = d["q"] * o["e_S"] * acc_unit
    return _bearer_row(**{"Mutual members": o["el_mut"] + o["acc_mut"], "Private buffer": o["el_tail"] + o["acc_tail"],
                          "Depositor": o["el_pub"] + max(0.0, acc_b - o["acc_mut"] - o["acc_tail"]),
                          "Deposit insurance fund": acc_m})


BEAR = {}
for m in ("Q", "P"):
    BEAR[("R1", m)] = _bearer_row(**{"Bank's own encumbered collateral": SELF[m]})
    BEAR[("R2", m)] = _bearer_row(**{"FHLB super-lien": SELF[m]})
    BEAR[("R3", m)] = _bearer_row(**{"Deposit insurance fund": SELF[m]})
    BEAR[("R4", m)] = _bearer_row(**{"Leaves with the balance": SELF[m]})
    BEAR[("R5 single", m)] = _bearer_row(**{"Private buffer": SELF[m]})
    BEAR[("R5 pooled", m)] = pool_bearers(cc.V8_REF["theta"], m)
    BEAR[("R5 sized", m)] = pool_bearers(K_STD / cc.V5_N, m)
    BEAR[("R6", m)] = r6_bearers(R6["ref"], m)
    BEAR[("R6 alt", m)] = r6_bearers(R6["alt"], m)
    BEAR[("R7", m)] = _bearer_row(**{"Depositor": SELF[m]})
    BEAR[("R8", m)] = BEAR[("R6", m)]
    BEAR[("R9", m)] = _bearer_row(**{"Depositor": SELF[m]})
BEAR_CHECK = max(abs(sum(v.values()) - SELF[m]) for (k, m), v in BEAR.items())
BEAR_FIG = [("R1", "R1"), ("R2", "R2"), ("R3", "R3"), ("R4", "R4"), ("R5", "R5 pooled"), ("R6", "R6"), ("R7", "R7"),
            ("R8", "R8"), ("R9", "R9")]

# =============================================================================
# 5. ROUTES, VARIANTS AND SCREENS
# =============================================================================
ROUTES = [
    ("R1", "Pledged securities at 110 percent (public-unit template)"),
    ("R2", "FHLB standby letter of credit"),
    ("R3", "Reciprocal placement"),
    ("R4", "Let it go and replace the funding"),
    ("R5", "Third-party funded vehicle (Chapter 3)"),
    ("R6", "Mutual with a Treasury-backed tail over a reciprocal base (Chapter 5)"),
    ("R7", "Always-on collateralized netting facility (liquidity, not credit)"),
    ("R8", "One ledger, two tranches (R6 credit tranche + R7 liquidity tranche, no shared reserve)"),
    ("R9", "Prefunded joint-account instant settlement (liquidity, not credit)"),
]
RNAME = dict(ROUTES)
RSHORT = {"R1": "Pledged securities at 110%", "R2": "FHLB standby letter of credit", "R3": "Reciprocal placement",
          "R4": "Let it go, replace the funding", "R5": "Third-party funded vehicle", "R6": "Mutual with a Treasury-backed tail",
          "R7": "Always-on netting facility", "R8": "One ledger, two tranches", "R9": "Joint-account prefunding"}
SCREENS = [("S1", "Open to a private corporate depositor at a national bank"),
           ("S2", f"Lendable share at least {S2_MIN:g}"),
           ("S3", "Cover continues, and can grow, below well capitalized or at CAMELS 4"),
           ("S4", "No hidden public subsidy"),
           ("S5", "Pays in full with probability at least 99% in the year the depositor's own bank fails (Gaussian, rho 0.30)")]
APPLY = {"a": ["S1", "S2", "S3", "S4", "S5"], "b": ["S1", "S3", "S4"], "ab": ["S1", "S2", "S3", "S4", "S5"]}
PROBLEMS = [("a", "(a) keep the balance as stable lendable funding through a failure"),
            ("b", "(b) move it outside funding-market hours"),
            ("ab", "(a) and (b) together")]


def b2(x):
    return f"{x / BP + 1e-12:.2f}"


def b1(x):
    return f"{x / BP + 1e-12:.1f}"


def pcs(x, nd=2):
    return f"{x * 100:.{nd}f}%"


def rng_b(lo, hi, nd=1):
    f = b2 if nd == 2 else b1
    return f"{f(lo)} to {f(hi)}"


def sf_txt(x):
    return "0 (fully funded)" if x == 0 else (pcs(x, 2) if x >= 1e-3 else pcs(x, 3))


_SRC_N1 = "Chapter 4"
_SC = {}
_SC["R1"] = dict(
    S1=("fail", "National banks lack the power to pledge assets to secure a private deposit; the exceptions cover public "
                "funds, tribes and trust funds", "Chapter 4 (Texas and Pacific Railway Co. v. Pottorff, 291 "
                "U.S. 245 (1934); 12 U.S.C. 90; 12 U.S.C. 92a(d))"),
    S2=("fail", "Lendable share about 0: the deposit funds its own collateral", _SRC_N1),
    S3=("pass", "A perfected pledge does not lapse when the bank's capital category or rating falls [author's reading]",
        "author's reading"),
    S4=("open", "The pledge puts the depositor ahead of the fund; at a lendable share of 0 the deposit funds its own "
                "collateral and the fund loses nothing net, but a pledge from securities already held subordinates it "
                "[author's reading]", "Chapters 4 and 5"),
    S5=("n/a", "No failure payoff for the engine to price; the pledge pays from collateral at 110 percent", _SRC_N1))
_SC["R2"] = dict(
    S1=("open", "The regulation does not restrict the beneficiary; the FHLBanks' public-unit product terms do, and a "
                "letter backed by the member's pledged assets raises the Pottorff question",
        "Chapter 4 (12 CFR 1269.2; FHLBank Boston 2022; Pottorff)"),
    S2=("pass", "Lendable share about 1: the deposit stays on the balance sheet and funds loans", _SRC_N1),
    S3=("open", "An issued letter runs to its term; a new or larger letter for a weakened member turns on the FHLBank's "
                "credit and collateral terms, which tighten as the member weakens [author's reading]",
        "author's reading; Chapter 4 (12 CFR 1269.2(b))"),
    S4=("fail", f"The FHLBank's lien outranks the receiver, so the letter's risk lands on the deposit insurance fund, "
                f"unpriced in the fee: {b1(R2_MOVED['P'])} bps a year under P, {b1(R2_MOVED['Q'])} under Q",
        "Chapter 4 (12 U.S.C. 1430(e))"),
    S5=("n/a", "Pays in full while the FHLBank's collateral holds; no failure payoff for the engine to price", _SRC_N1))
_SC["R3"] = dict(
    S1=("pass", "Open to a private corporation; the account becomes a set of insured accounts at other banks", _SRC_N1),
    S2=("pass", "Lendable share about 1: matched placement returns an equal balance", _SRC_N1),
    S3=("fail", "Below well capitalized or at CAMELS 4 the bank keeps what it holds up to a special cap but may not grow; "
                "growth past it makes every reciprocal deposit brokered; the rate cap applies",
        "Chapter 5 (12 U.S.C. 1831f(i); 12 CFR 337.6; 12 CFR 337.7)"),
    S4=("pass", "A priced public cover: FDIC insurance against the assessments the banks pay, not a hidden subsidy; the "
                "fund's exposure to large corporate balances grows with the layer", "Chapter 5"),
    S5=("pass", "FDIC-insured within the cap: pays in full by construction", "Chapter 4 (12 CFR 337.6(e))"))
_SC["R4"] = dict(
    S1=("pass", "Always open: the depositor sweeps to a fund, a tokenized Treasury fund or a stablecoin", _SRC_N1),
    S2=("fail", "Lendable share 0: the dollar has left", "Chapter 4"),
    S3=("n/a", "No cover to continue; the balance has left", "Chapter 4"),
    S4=("pass", "No public party bears the risk; the cost falls on borrowers or shareholders through the replacement spread",
        "Chapters 3 and 4"),
    S5=("n/a", "No failure payoff; the balance is no longer at the bank", "Chapter 4"))
_SC["R5"] = dict(
    S1=("pass", "Open in principle in the depositor-paid wrapper, where the bank is not a party; the licensing and "
                "dealer-registration questions are general, not charter-specific; no such vehicle exists",
        "Chapters 3 and 4"),
    S2=("pass", "Lendable share 1: the buffer is the provider's", _SRC_N1),
    S3=("pass", "Annual contract; pre-agreed step-ups move a weakening bank up the pricing grid rather than cutting it off",
        "Chapter 3 (term sheet)"),
    S4=("pass", "No public party bears the loss; the buffer is paid for by the premium", "Chapter 4"))
_SC["R6"] = dict(
    S1=("open", "The design sets no charter limit and nothing is pledged, so Pottorff does not bite; whether a national bank "
                "may make the entry capital contribution to a state-licensed mutual insurer is an open counsel "
                "question [author's reading]", "Chapter 5"),
    S2=("pass", f"Lendable share {R6_LEND:.2f}: the member's {pcs(mt.THETA_M, 0)} capital contribution sits in Treasury "
                f"bills at the mutual [author's reading]", "Chapter 5; mutual_tail.py parameters"),
    S3=("pass", "Cover turns on the mutual's own covenants, not the member's capital category; covered excess grows within "
                "the tiered per-member cap and the growth covenant while the reciprocal base under it stops",
        "Chapter 5"),
    S4=("pass", f"Members and tail investors pay for the risk to X; rule M asks the receivership to carry the recovery of "
                f"the excess at closure ({b2(BEAR[('R6', 'Q')]['Deposit insurance fund'])} bps a year under Q), a timing "
                f"cost the FDIC carries in any all-deposit purchase and assumption; expected loss above X "
                f"{b2(R6['ref']['el_pub_p'])} bps [author's reading]", "Chapter 5; mutual_tail.py"))
_SC["R7"] = dict(
    S1=("pass", "The bank pledges bills to other member banks for its own net debits, not to secure the deposit; a "
                "corporation reaches the facility through its member bank [author's reading]", "Chapter 6"),
    S2=("fail", f"Lendable share {R7_LEND:.2f}: each always-on tier dollar is matched by a bill the bank cannot lend; S2 "
                f"holds only at an always-on share of {pcs(R7_SHARE_MAX_S2, 0)} or less", "Chapter 6"),
    S3=("pass", "The cap rests on the member's own pledged bills, with no capital condition; the design expects a weak "
                "bank to use it and slows it through the cap", "Chapter 6"),
    S4=("open", f"Safe-harbored repo puts net creditors ahead of the receiver for the capped weekend outflow: an upper "
                f"bound of {b2(R7_MOVED['P'])} bps a year under P, {b2(R7_MOVED['Q'])} under Q, on the whole balance; a "
                f"weekday run through Fedwire moves the same loss with no cap [author's reading]",
        "Chapter 6 (12 U.S.C. 1821(e)(8) to (10))"),
    S5=("n/a", "Liquidity, not credit: the facility does nothing for the balance if the bank fails", "Chapter 6"))
_SC["R8"] = dict(
    S1=("open", "Inherits R6's open question on the capital contribution", "R6"),
    S2=("fail", f"Lendable share {R8_LEND:.2f} ({pcs(mt.THETA_M, 0)} capital contribution plus the {pcs(R7_SHARE, 0)} "
                f"always-on tier); S2 holds only at an always-on share of {pcs(R8_SHARE_MAX_S2, 0)} or less", "R6; R7"),
    S3=("pass", "Both tranches pass", "R6; R7"),
    S4=("open", "Inherits R7's open question on the safe-harbored repo", "R7"),
    S5=("pass", f"The credit tranche is R6's reference design and no reserve is shared: {pcs(R6_SF[('ref', 'gauss')])} short",
        "Chapter 6; mutual_tail.py"))
_SRC_R9 = ("Board guidelines for evaluating joint account requests (82 FR 41951, 2017); FedNow Operating Circular 8, "
           "Section 9.7.1")
_SC["R9"] = dict(
    S1=("open", "A corporation reaches the arrangement through its member bank and nothing is pledged for the deposit, so "
                "Pottorff does not bite, and the operator need not be a bank; but a new joint account needs Reserve "
                "Bank approval under the Board's 2017 guidelines, not yet sought. Scored open, the scale's verdict for "
                "an approval or opinion the sources do not settle, as for R2's and R6's S1 [author's reading]", _SRC_R9),
    S2=("fail", f"Lendable share {R9_LEND:.2f}: each prefunded dollar is a reserve balance in the joint account the bank "
                f"cannot lend, and in the base it is not counted as HQLA either (no public statement on its liquidity "
                f"coverage treatment); S2 holds only at a prefunded share of {pcs(R9_SHARE_MAX_S2, 0)} or less",
        "this engine; absolute convention"),
    S3=("pass", "The position is the member's own prefunded central bank money, with no capital condition in the design; "
                "a Reserve Bank's account-risk controls on a troubled member bind every route that settles in central "
                "bank money, R7 included [author's reading]", "author's reading"),
    S4=("pass", "Prefunded and final in central bank money: no secured priority over the receiver and no Reserve Bank "
                "credit; if a member is closed, its unspent position passes to the receiver [author's reading]",
        "author's reading"),
    S5=("n/a", "Liquidity, not credit: the arrangement does nothing for the balance if the bank fails", "this engine"))


def _s5(sf):
    ok = 1.0 - sf >= 1.0 - S5_STD - 1e-12
    return ("pass" if ok else "fail",
            f"P(not paid in full given own bank fails) {sf_txt(sf)}: paid in full {pcs(1.0 - sf, 2)}", "computed (clearing_cost.py "
            "or mutual_tail.py)")


def s2_verdict(lend, bar=None):
    """S2 on the absolute convention: pass if the lendable share is at least the bar (default: this run's S2_MIN)."""
    return "pass" if lend >= (S2_MIN if bar is None else bar) - 1e-12 else "fail"


def V(key, route, label, lo, base, hi, t_price, t_note, basis, source, lendable, capacity, sf_g=None, sf_t=None,
      problems=("a",), s5=None):
    sc = dict(_SC[route])
    if s5 is not None:
        sc["S5"] = s5
    # S2 is computed from the lendable share at this run's bar; at the bar of record it must equal the recorded verdict
    s2v = s2_verdict(lendable)
    if S2_DEFAULT_RUN and s2v != sc["S2"][0]:
        raise RuntimeError(f"S2 verdict for {key} computed {s2v}, recorded {sc['S2'][0]}")
    sc["S2"] = (s2v,) + tuple(sc["S2"][1:])
    return dict(key=key, route=route, label=label, lo=lo, base=base, hi=hi, t_price=t_price, t_note=t_note, basis=basis,
                source=source, lendable=lendable, capacity=capacity, sf_g=sf_g, sf_t=sf_t, problems=problems, screens=sc)


R5S_PRICE = R5_SINGLE["c_star"]
VARIANTS = [
    V("R1 held", "R1", "Pledged from securities already held", R1_HELD[0], 0.5 * sum(R1_HELD), R1_HELD[1], None,
      "no failure payoff", "author assumption", "Chapter 4", 0.0,
      f"${R1_OVERCOLL * BALANCE / 1e6:.0f}m of high-quality liquid assets, encumbered"),
    V("R1 bought", "R1", f"Securities bought for the purpose ({b1(R1_SPREAD[0])} to {b1(R1_SPREAD[1])} spread on "
      f"{R1_OVERCOLL:.0%})", R1_BOUGHT[0], 0.5 * sum(R1_BOUGHT), R1_BOUGHT[1], None, "no failure payoff",
      "author assumption", "Chapter 4", 0.0, f"${R1_OVERCOLL * BALANCE / 1e6:.0f}m of securities bought and pledged"),
    V("R2", "R2", "Public-unit fee by district, standard structures", R2_FEE[0], 0.5 * sum(R2_FEE), R2_FEE[1], None,
      "no failure payoff", "reported figure",
      "FHLBank Des Moines 2026; FHLBank San Francisco 2025; FHLBank Boston 2022; FHLBank Topeka 2023", 1.0,
      f"${BALANCE / 1e6:.0f}m of FHLB borrowing capacity, and the collateral behind it"),
    V("R3", "R3", f"Placement fee plus rate uplift (base {b1(R3_UPLIFT)})", R3_FEE + R3_UPLIFT_SET[0], R3_FEE + R3_UPLIFT,
      R3_FEE + R3_UPLIFT_SET[-1], None, "insured by the FDIC", "reported figure (fee); author assumption (uplift)",
      "Chain Bridge Bancorp 2026", 1.0, "The non-brokered allowance (tiered, up to $30bn)", sf_g=0.0, sf_t=0.0),
    V("R4", "R4", "Replacement spread on each dollar replaced", R4_SPREAD[0], 0.5 * sum(R4_SPREAD), R4_SPREAD[1], None,
      "no failure payoff", "author assumption", "Chapter 3", 0.0, "None (the balance has left)"),
    V("R5 single", "R5", "Single-name funded vehicle", R5S_PRICE, R5S_PRICE, R5S_PRICE, R5S_PRICE, "no copula",
      "model number", "clearing_cost.py", 1.0, "The provider's buffer, 100% of the balance; none of the bank's", sf_g=0.0,
      sf_t=0.0, s5=("pass", "Fully funded single name: pays par in every state (shortfall 0)", "clearing_cost.py")),
    V("R5 pooled", "R5", f"Pooled all-funded reference design (theta {pcs(cc.V8_REF['theta'], 0)}, 50 banks)",
      R5_REF["c_star"], R5_REF["c_star"], R5_REF["c_star"], R5_REF_T, "same design under t(5)", "model number",
      "clearing_cost.py", 1.0, f"The provider's buffer, {pcs(cc.V8_REF['theta'], 0)} of covered notional; none of the bank's",
      sf_g=R5_SF[("ref", "gauss")], sf_t=R5_SF[("ref", "t")], s5=_s5(R5_SF[("ref", "gauss")])),
    V("R5 sized", "R5", f"Pooled, capacity sized to the S5 standard ({K_STD} failures, theta {pcs(K_STD / cc.V5_N, 0)}; "
      f"results_clearing_cost.md, Section 38)", R5_STD["c_star"], R5_STD["c_star"], R5_STD["c_star"], R5_STD_T,
      "same design under t(5)", "model number", "clearing_cost.py", 1.0,
      f"The provider's buffer, {pcs(K_STD / cc.V5_N, 0)} of covered notional; none of the bank's",
      sf_g=R5_SF[("std", "gauss")], sf_t=R5_SF[("std", "t")], s5=_s5(R5_SF[("std", "gauss")])),
    V("R6", "R6", f"Reference design: X {pcs(mt.X_REF, 1)} for the Gaussian 1% standard, q_acq {mt.Q_ACQ}",
      R6["ref"]["pi"], R6["ref"]["pi"], R6["ref"]["pi"], R6_T["ref"], "same design under t(5)", "model number",
      "mutual_tail.py", R6_LEND, f"{pcs(mt.THETA_M, 0)} capital contribution and a call of up to {mt.M_SA} x the "
      f"assessment; the reciprocal allowance for the base", sf_g=R6_SF[("ref", "gauss")], sf_t=R6_SF[("ref", "t")],
      s5=_s5(R6_SF[("ref", "gauss")])),
    V("R6 alt", "R6", f"Alternative design: X {pcs(mt.X_ALT, 1)} for the Student-t(5) 5% standard", R6["alt"]["pi"],
      R6["alt"]["pi"], R6["alt"]["pi"], R6_T["alt"], "same design under t(5)", "model number", "mutual_tail.py", R6_LEND,
      f"{pcs(mt.THETA_M, 0)} capital contribution and a call of up to {mt.M_SA} x the assessment",
      sf_g=R6_SF[("alt", "gauss")], sf_t=R6_SF[("alt", "t")], s5=_s5(R6_SF[("alt", "gauss")])),
    V("R7", "R7", f"Facility at a {pcs(R7_SHARE, 0)} always-on share, {pcs(R7_HAIRCUT, 0)} haircut", R7_LO, R7_BASE,
      R7_HI, None, "no failure payoff", "author assumption (illustrative)", "Chapter 6", R7_LEND,
      f"${R7_BILLS * BALANCE / 1e6:.1f}m of Treasury bills positioned each weekend", problems=("b",)),
    V("R8", "R8", "R6 reference design + R7 less the shared-infrastructure saving", R8_LO, R8_BASE, R8_HI,
      R6_T["ref"] + R7_BASE - R8_SAVE[R8_ACC_SHARE], "R6 under t(5) + R7", "model number + author assumption",
      "mutual_tail.py; Chapter 6", R8_LEND, "Both of the above",
      sf_g=R6_SF[("ref", "gauss")], sf_t=R6_SF[("ref", "t")], problems=("a", "b", "ab")),
    V("R9", "R9", f"Joint-account position at a {pcs(R9_SHARE, 0)} prefunded share, balance "
      f"{'earning' if R9_JA_INTEREST else 'earning no'} interest", R9_LO, R9_BASE, R9_HI, None, "no failure payoff",
      "author assumption (illustrative)", "this engine (section 1, R9 block)", R9_LEND,
      f"${R9_SHARE * BALANCE / 1e6:.1f}m of reserves held in the joint account at all times", problems=("b",)),
]
VBY = {v["key"]: v for v in VARIANTS}
R9_ALT_V = V("R9 alt", "R9", f"Memo: joint-account position, balance {'earning' if R9_ALT else 'earning no'} interest",
             R9_ALT_LO, R9_ALT_BASE, R9_ALT_HI, None, "no failure payoff", "author assumption (illustrative)",
             "this engine (section 1, R9 block)", R9_LEND, "as R9", problems=("b",))


def qualifies(v, screens, lenient=False):
    for s in screens:
        verdict = v["screens"][s][0]
        if verdict in ("pass", "n/a") or (lenient and verdict == "open"):
            continue
        return False
    return True


def apply_rule(problem, lenient=False, variants=None, screens=None):
    """Champion = cheapest base price among routes whose best variant passes every applicable screen;
    challenger = the next cheapest route. Variants of one route compete inside the route first."""
    variants = VARIANTS if variants is None else variants
    screens = APPLY[problem] if screens is None else screens
    best = {}
    for v in variants:
        if problem in v["problems"] and qualifies(v, screens, lenient):
            if v["route"] not in best or v["base"] < best[v["route"]]["base"]:
                best[v["route"]] = v
    ranked = sorted(best.values(), key=lambda v: (v["base"], v["key"]))
    passing_variants = sorted([v for v in variants if problem in v["problems"] and qualifies(v, screens, lenient)],
                              key=lambda v: (v["base"], v["key"]))
    return dict(champion=ranked[0] if ranked else None, challenger=ranked[1] if len(ranked) > 1 else None,
                ranked=ranked, variants=passing_variants)


RULE = {(p, l): apply_rule(p, l) for p, _ in PROBLEMS for l in (False, True)}
RULE_S2B = {l: [v for v in VARIANTS if "b" in v["problems"] and qualifies(v, APPLY["b"] + ["S2"], l)] for l in (False, True)}
RULE_R9_ALT = {l: apply_rule("b", l, [v for v in VARIANTS if v["route"] != "R9"] + [R9_ALT_V]) for l in (False, True)}
CHAMP_STRICT = RULE[("a", False)]["champion"]
CHAMP_OPEN = RULE[("a", True)]["champion"]


# --- memo: problem (b) with R7's Sunday settlement cash in case b1 or b2 (R8 contains R7 and carries the same term) ------
def _with_sunday(case):
    out = []
    for v in VARIANTS:
        if v["route"] in ("R7", "R8"):
            ex = [r7_sunday_extra(case, end=e) for e in (0, 1)]
            v = {**v, "lo": v["lo"] + ex[0], "hi": v["hi"] + ex[1], "base": v["base"] + 0.5 * (ex[0] + ex[1]),
                 "lendable": v["lendable"] - (0.0 if case == "a" else R7_SHARE)}
        out.append(v)
    return out


def _key(v):
    return None if v is None else v["key"]


def _same_rule(r1, r2):
    return _key(r1["champion"]) == _key(r2["champion"]) and _key(r1["challenger"]) == _key(r2["challenger"])


RULE_SUN = {(c, l): apply_rule("b", l, _with_sunday(c)) for c in R7_SUN_LABEL for l in (False, True)}
if not all(_same_rule(RULE_SUN[("a", l)], RULE[("b", l)]) for l in (False, True)):
    raise RuntimeError("case (a) of the Sunday memo must reproduce the published rule for problem (b)")
if R7_SUN_CHECK > 1e-12:
    raise RuntimeError("case (a) of the Sunday memo must reproduce R7's published price and crossover")


# --- by deposit type (Section 10b): which clock a deposit runs on, and what the list's routes cost for it -----------------
#     A plain account above the insured limit runs on the run clock only. A tokenized balance runs on the settlement clock
#     whether it is insured or not. A tokenized balance above the limit runs on both. Each row is a priced variant of this
#     list, open items resolved and S2 not applied, so the rows price the risk and do not choose a route. For both clocks
#     the routes stack: R8 is R6 plus R7 less the shared ledger; R6 plus R9 is the pairing with no shared ledger, so no
#     saving is priced for it. Lendable shares on the absolute convention: the encumbrances add.
def _dt(deposit, clocks, hedge, base, lo, hi, lend, basis):
    return dict(deposit=deposit, clocks=clocks, hedge=hedge, base=base, lo=lo, hi=hi, lend=lend, basis=basis)


_R6P, _R5S = VBY["R6"], VBY["R5 sized"]
_R7V, _R8V, _R9V = VBY["R7"], VBY["R8"], VBY["R9"]
DT_ROWS = [
    _dt("Insured, plain account", "neither", "none needed", 0.0, 0.0, 0.0, 1.0, "the FDIC insures it"),
    _dt("Uninsured, plain account", "run", "R6 mutual with tail, reference design", _R6P["base"], _R6P["lo"], _R6P["hi"],
        _R6P["lendable"], "Table 9, open items resolved"),
    _dt("Uninsured, plain account", "run", "R5 pooled vehicle sized to S5 (strict champion)", _R5S["base"], _R5S["lo"],
        _R5S["hi"], _R5S["lendable"], "Table 9, strict"),
    _dt("Insured, tokenized", "settlement", "R7 facility, Sunday cash case (a)", _R7V["base"], _R7V["lo"], _R7V["hi"],
        _R7V["lendable"], "Table 9, open items resolved"),
    _dt("Insured, tokenized", "settlement", "R9 joint account", _R9V["base"], _R9V["lo"], _R9V["hi"], _R9V["lendable"],
        "Table 9, challenger"),
    _dt("Insured, tokenized", "settlement", "R7 facility, Sunday cash case (b1)", R7_SUN["b1"]["base"],
        R7_SUN["b1"]["lo"], R7_SUN["b1"]["hi"], R7_SUN["b1"]["lend"], "Section 7 memo"),
    _dt("Insured, tokenized", "settlement", "R7 facility, Sunday cash case (b2)", R7_SUN["b2"]["base"],
        R7_SUN["b2"]["lo"], R7_SUN["b2"]["hi"], R7_SUN["b2"]["lend"], "Section 7 memo"),
    _dt("Uninsured, tokenized", "both", "R8 one ledger (R6 + R7, Sunday cash case (a))", _R8V["base"], _R8V["lo"],
        _R8V["hi"], _R8V["lendable"], "Table 6"),
    _dt("Uninsured, tokenized", "both", "R6 + R9, no shared ledger", _R6P["base"] + _R9V["base"],
        _R6P["lo"] + _R9V["lo"], _R6P["hi"] + _R9V["hi"], 1.0 - mt.THETA_M - R9_SHARE, "this section"),
    _dt("Uninsured, tokenized", "both", "R8 one ledger, Sunday cash case (b1)",
        _R8V["base"] + R7_SUN["b1"]["ex_base"], _R8V["lo"] + r7_sunday_extra("b1", end=0),
        _R8V["hi"] + r7_sunday_extra("b1", end=1), _R8V["lendable"] - R7_SHARE, "this section"),
    _dt("Uninsured, tokenized", "both", "R8 one ledger, Sunday cash case (b2)",
        _R8V["base"] + R7_SUN["b2"]["ex_base"], _R8V["lo"] + r7_sunday_extra("b2", end=0),
        _R8V["hi"] + r7_sunday_extra("b2", end=1), _R8V["lendable"] - R7_SHARE, "this section"),
]
# the second clock's cost and lendable loss on an uninsured balance, at the cheapest pairing in each Sunday cash case
DT_BOTH = {"a": min(DT_ROWS[7], DT_ROWS[8], key=lambda r: r["base"]),
           "b1": min(DT_ROWS[9], DT_ROWS[8], key=lambda r: r["base"]),
           "b2": min(DT_ROWS[10], DT_ROWS[8], key=lambda r: r["base"])}
DT_EXTRA = {c: (r["base"] - _R6P["base"], _R6P["lendable"] - r["lend"]) for c, r in DT_BOTH.items()}
if abs(_R8V["base"] - (R6["ref"]["pi"] + R7_BASE - R8_SAVE[R8_ACC_SHARE])) > 1e-12 or \
        abs(_R8V["lendable"] - (_R6P["lendable"] - R7_SHARE)) > 1e-12:
    raise RuntimeError("the deposit-type table must reproduce R8 as R6 plus R7 less the shared-ledger saving")


# --- S2 bar sensitivity: every route's S2 verdict and the rule at each bar in S2_BARS, published route parameters ------
def variants_at_bar(bar, variants=None):
    """Copies of the variants with S2 re-scored at the bar; everything else unchanged."""
    out = []
    for v in (VARIANTS if variants is None else variants):
        sc = dict(v["screens"])
        sc["S2"] = (s2_verdict(v["lendable"], bar),) + tuple(sc["S2"][1:])
        out.append({**v, "screens": sc})
    return out


S2_PROBLEMS = [("a", "(a) stable lendable funding", None), ("b", "(b) movement outside funding-market hours", None),
               ("b+S2", "(b) with S2 also applied", APPLY["b"] + ["S2"]), ("ab", "(a) and (b) together", None)]
S2_SENS = {}
for _bar in S2_BARS:
    _vb = variants_at_bar(_bar)
    for _pk, _pn, _scr in S2_PROBLEMS:
        for _l in (False, True):
            S2_SENS[(_bar, _pk, _l)] = apply_rule("b" if _pk == "b+S2" else _pk, _l, _vb, _scr)
S2_SENS_MAX = {_bar: {"R7": 1.0 - _bar, "R8": 1.0 - _bar - mt.THETA_M, "R9": 1.0 - _bar} for _bar in S2_BARS}
# at this run's bar, the sensitivity must reproduce Section 9 (a check, printed in Section 9b)
S2_SENS_SELF = None
for _bar in S2_BARS:
    if abs(_bar - S2_MIN) < 1e-12:
        S2_SENS_SELF = (all(_same_rule(S2_SENS[(_bar, p, l)], RULE[(p, l)]) for p, _ in PROBLEMS for l in (False, True))
                        and all([v["key"] for v in S2_SENS[(_bar, "b+S2", l)]["variants"]]
                                == [v["key"] for v in sorted(RULE_S2B[l], key=lambda v: (v["base"], v["key"]))]
                                for l in (False, True)))

# =============================================================================
# 6. RELIABILITY BESIDE THE PRICE (S5 and what the Gaussian standard hides)
# =============================================================================
REL_ROWS = [("R5 single", "R5 single-name", 0.0, 0.0, R5S_PRICE, R5S_PRICE),
            ("R5 pooled", "R5 pooled reference (20%)", R5_SF[("ref", "gauss")], R5_SF[("ref", "t")], R5_REF["c_star"], R5_REF_T),
            ("R5 sized", f"R5 pooled sized to S5 ({pcs(K_STD / cc.V5_N, 0)})", R5_SF[("std", "gauss")], R5_SF[("std", "t")],
             R5_STD["c_star"], R5_STD_T),
            ("R5 tstd", f"Memo: R5 pooled sized to t(5) 5% ({pcs(K_STD_T / cc.V5_N, 0)})", R5_SF[("tstd", "gauss")],
             R5_SF[("tstd", "t")], R5_TSTD["c_star"], R5_TSTD["c_star"]),
            ("R6", f"R6 reference (X {pcs(mt.X_REF, 1)})", R6_SF[("ref", "gauss")], R6_SF[("ref", "t")], R6["ref"]["pi"], R6_T["ref"]),
            ("R6 alt", f"R6 alternative (X {pcs(mt.X_ALT, 1)})", R6_SF[("alt", "gauss")], R6_SF[("alt", "t")], R6["alt"]["pi"],
             R6_T["alt"]),
            ("R8", "R8 (credit tranche = R6 reference)", R6_SF[("ref", "gauss")], R6_SF[("ref", "t")], R8_BASE,
             VBY["R8"]["t_price"])]

# =============================================================================
# 7. DOLLARS FOR TWO BANKS
# =============================================================================
def recip_cap(liab):
    cap, lo = 0.0, 0.0
    for width, share in RECIP_TIERS:
        cap += share * min(max(liab - lo, 0.0), width)
        lo += width
    return min(cap, RECIP_MAX)


def marginal_tier(liab):
    lo = 0.0
    for width, share in RECIP_TIERS:
        if liab <= lo + width:
            return share
        lo += width
    return RECIP_TIERS[-1][1]


BANK_ROWS = []
for nm, assets in BANKS:
    liab = LIAB_RATIO * assets
    cov = COVERED_SHARE * liab
    cap = recip_cap(liab)
    BANK_ROWS.append(dict(name=nm, assets=assets, liab=liab, cov=cov, cap=cap, cap_share=cap / liab, tier=marginal_tier(liab),
                          headroom=cap - cov, capital=mt.THETA_M * cov,
                          cost={v["key"]: (v["lo"] * cov, v["base"] * cov, v["hi"] * cov) for v in VARIANTS}))
CLEAR_PRICES = []
for v in (CHAMP_STRICT, CHAMP_OPEN, VBY["R5 single"]):
    if v is not None and v["key"] not in [k for k, _ in CLEAR_PRICES]:
        CLEAR_PRICES.append((v["key"], v["base"]))
CLEAR_ROWS = []
for s_rep in S_REP_SET:
    for Vr, dp in WTP_CELLS:
        wtp = dp * Vr * ANNUITY
        row = dict(s_rep=s_rep, V=Vr, dp=dp, wtp=wtp, full=wtp + s_rep, wtd=wtp + dp * s_rep * ANNUITY)
        for k, c in CLEAR_PRICES:
            row[("full", k)] = max(0.0, c - row["full"])
            row[("wtd", k)] = max(0.0, c - row["wtd"])
        CLEAR_ROWS.append(row)

# =============================================================================
# 8. SENSITIVITIES ON THE CHAMPION, CAPACITY RE-SIZED TO THE S5 STANDARD EACH TIME
# =============================================================================
def r6_sized(pd=LAMBDA_P, mu=MU, lgd=LGD, rho=RHO_PRICE, opp=mt.OPP, f_m=mt.F_M):
    """Mutual with a tail, X re-sized to the Gaussian 1% conditional standard (median member, rho 0.30, state-dependent
    LGD), the mutual model's sizing logic with every pricing input exposed."""
    prof = mt.PB
    Dc = mt.dist(prof, pd, RHO_REL, "gauss", prof.median, "corr")
    Du = mt.dist(prof, pd, RHO_REL, "gauss", None, "corr")
    Dp, Dq = mt.price_D(prof, pd, rho, "gauss", lgd, mu)
    des = lambda X: mt.solve(Dp, Dq, mt.Q_ACQ, X=X, opp=opp, f_m=f_m)
    short = lambda X: mt.reliab(Dc, Du, des(X))["short"]
    lo, hi = 0.0, 1.0
    if short(hi) > S5_STD:
        return None
    while hi - lo > 2e-5:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if short(mid) > S5_STD else (lo, mid)
    X = math.ceil(hi * 1e3 - 1e-9) / 1e3
    d = des(X)
    return dict(X=X, A=d["A"], T=d["T"], mutual=d["mutual"], tail=d["tail"], pi=d["pi"], short=short(X))


def r5_sized(pd=LAMBDA_P, mu=MU, lgd=LGD, rho=RHO_PRICE, s_lock=cc.V5_S_LOCK, f=cc.V5_FRIC):
    """The clearing-cost engine's all-funded pool, capacity re-sized (whole failures of 2% each) to the Gaussian 1% conditional standard
    (rho 0.30, state-dependent LGD), priced at fixed LGD as the clearing-cost engine prices."""
    with cc._trim_cache():
        k = cc.k_needed(cc.pool(pd, RHO_REL, "corr"), S5_STD)
        sf = cc.ref_cond(cc.pool(pd, RHO_REL, "corr"), lambda n, PP, k_=k: (n > k_ + 1e-9).astype(float))
        pr = cc.pool_price(pd=pd, rho=rho, mode=("fixed" if lgd == LGD else lgd), theta=k / cc.V5_N, F=0.0, mu=mu,
                           s_lock=s_lock, f=f)
    return dict(k=k, theta=k / cc.V5_N, pi=pr["c_star"], short=sf)


SENS_SPEC = {
    "R6": [("lambda_P", "lambda_P", SENS_LP, lambda x: f"{x * 100:.2f}%"), ("mu", "mu", SENS_MU, lambda x: f"{x:.0f}"),
           ("LGD", "lgd", SENS_LGD, lambda x: f"{x:.0%}"), ("rho (prices)", "rho", SENS_RHO, lambda x: f"{x:.2f}"),
           ("Reserve opportunity cost", "opp", SENS_OPP, lambda x: f"{x / BP:.0f} bps"),
           ("Mutual frictions f_m", "f_m", SENS_FM, lambda x: f"{x / BP:.0f} bps")],
    "R5": [("lambda_P", "pd", SENS_LP, lambda x: f"{x * 100:.2f}%"), ("mu", "mu", SENS_MU, lambda x: f"{x:.0f}"),
           ("LGD", "lgd", SENS_LGD, lambda x: f"{x:.0%}"), ("rho (prices)", "rho", SENS_RHO, lambda x: f"{x:.2f}"),
           ("Lock-up premium s_lock", "s_lock", SENS_SLOCK, lambda x: f"{x / BP:.0f} bps"),
           ("Frictions f", "f", SENS_F, lambda x: f"{x / BP:.0f} bps")],
}
SENS = {}
SENS_BASE = {"R6": r6_sized(), "R5": r5_sized()}
for route in sorted({v["route"] for v in (CHAMP_STRICT, CHAMP_OPEN) if v is not None} & set(SENS_SPEC)):
    rows = []
    for label, arg, vals, fmt in SENS_SPEC[route]:
        for x in vals:
            kw = {("pd" if (route == "R6" and arg == "lambda_P") else arg): x}
            r = (r6_sized(**kw) if route == "R6" else r5_sized(**kw))
            rows.append((label, fmt(x), x, r))
    SENS[route] = rows
TORNADO = {}
for route, rows in SENS.items():
    tor = {}
    for label, _, _, r in rows:
        if r is None:
            continue
        lo, hi = tor.get(label, (9.0, -9.0))
        tor[label] = (min(lo, r["pi"]), max(hi, r["pi"]))
    TORNADO[route] = sorted(tor.items(), key=lambda kv: kv[1][1] - kv[1][0])

# =============================================================================
# 9. PARITY WITH THE IMPORTED HEADLINES
# =============================================================================
PARITY = [
    ("Single-name funded vehicle c*, bps (clearing_cost.py)", R5S_PRICE / BP, "45.74"),
    ("Pooled all-funded reference design c*, bps (clearing_cost.py)", R5_REF["c_star"] / BP, "37.7"),
    ("Self-insured cost, credit + access under Q, bps (clearing_cost.py)", SELF["Q"] / BP, "21"),
    ("Conditional shortfall at 20% capacity, own bank fails, Gaussian rho 0.30, % (clearing_cost.py)",
     cc.rel8[("gauss", LAMBDA_P, RHO_REL, cc.V8_CAP)]["sf"] * 100, "1.0"),
    ("Conditional shortfall at 20% capacity, own bank fails, Student-t(5) rho 0.30, % (clearing_cost.py)",
     cc.rel8[("t", LAMBDA_P, RHO_REL, cc.V8_CAP)]["sf"] * 100, "27.7"),
    ("All-in, reference design (X 10.0%, Gaussian 1%, q_acq 0.5, mixed rule), bps (mutual)", R6["ref"]["pi"] / BP, "21.03"),
    ("All-in, alternative design (X 21.8%, t(5) 5%), bps (mutual)", R6["alt"]["pi"] / BP, "31.01"),
    ("All-in, reference X, rule B only, bps (mutual)", R6_B["pi"] / BP, "21.39"),
    ("Mutual own layer, reference design, bps (mutual)", R6["ref"]["mutual"] / BP, "14.54"),
    ("Tail premium, reference design, bps (mutual)", R6["ref"]["tail"] / BP, "6.50"),
    ("Reference design short given median member fails, Gaussian rho 0.30, % (mutual)", R6_SF[("ref", "gauss")] * 100, "0.99"),
    ("Reference design short given median member fails, Student-t(5) rho 0.30, % (mutual)", R6_SF[("ref", "t")] * 100, "20.19"),
    ("Exhaustion point X, reference, % (mutual)", mt.X_REF * 100, "10.0"),
    ("Exhaustion point X, alternative, % (mutual)", mt.X_ALT * 100, "21.8"),
]


def _match(x, target):
    nd = len(target.split(".")[1]) if "." in target else 0
    return f"{x + 1e-12:.{nd}f}" == target


PARITY_ROWS = [(nm, x, t, _match(x, t)) for nm, x, t in PARITY]
PARITY_OK = all(r[3] for r in PARITY_ROWS)
METHOD_CHECKS = [
    ("R6 sizing wrapper at base vs the mutual model's iso_x: X", SENS_BASE["R6"]["X"], mt.X_REF),
    ("R6 sizing wrapper at base vs the mutual model's reference all-in, bps", SENS_BASE["R6"]["pi"] / BP, R6["ref"]["pi"] / BP),
    ("R5 sizing wrapper at base vs the clearing-cost engine's iso-reliability row: failures covered", float(SENS_BASE["R5"]["k"]),
     float(cc.iso8[("gauss", S5_STD)]["k"])),
    ("R5 sizing wrapper at base vs the clearing-cost engine's iso-reliability row: price, bps", SENS_BASE["R5"]["pi"] / BP,
     cc.iso8[("gauss", S5_STD)]["ref"] / BP),
    ("Bearer split sums to the self-insured cost: largest absolute gap, bps", BEAR_CHECK / BP, 0.0),
]
METHOD_OK = all(abs(a - b) < 1e-9 for _, a, b in METHOD_CHECKS)


# =============================================================================
# 10. RESULTS FILE
# =============================================================================
def table(header, rows):
    """The clearing-cost engine's markdown table helper, with any pipe inside a cell escaped so columns never break."""
    esc = lambda c: str(c).replace("|", "\\|")
    return cc.table([esc(h) for h in header], [[esc(c) for c in r] for r in rows])


def vrow_price(v):
    if v["lo"] == v["hi"]:
        return b2(v["base"])
    return f"{b1(v['lo'])} to {b1(v['hi'])} (base {b1(v['base'])})"


def describe(v):
    if v is None:
        return "none"
    return f"{v['route']} ({v['label']}) at {b2(v['base'])} bps"


def _short(v):
    return "none" if v is None else f"{v['key']} at {b2(v['base'])}"


def write_results():
    L = []
    w = L.append
    w("# Cash That Never Sleeps, Chapters 4 to 7: one price list for the large uninsured deposit (routes.py results)")
    w("")
    w("Every number is illustrative and calibrated to no bank, vehicle, mutual, facility or investor. Parameters are "
      "author assumptions unless labelled as a reported figure with its source; reported figures are not model numbers. "
      "Units: bps a year per unit of a $100 million corporate balance above the insured limit, unless stated. Command: "
      f"`python -I -B model/{SCRIPT_NAME}{'' if S2_DEFAULT_RUN else f' --s2-min {S2_MIN:g}'}` from the repository root. The "
      "script imports the clearing-cost engine (`model/clearing_cost.py`) and the mutual engine "
      "(`model/mutual_tail.py`) by path and copies no code from either. Seeds: "
      f"{R7_MC_SEED} (weekend outflow Monte Carlo check), {R7_PATH_SEED} (illustrative weekend path, fig-U08); the "
      f"imported engines carry their own. Run environment: Python {sys.version.split()[0]}, numpy {np.__version__}; the "
      "run time is printed to the console and not written here, so two runs give the same file. Attributions of who "
      "bears the risk and the screen verdicts marked [author's reading] are readings, not findings of law.")
    w("")
    if not S2_DEFAULT_RUN:
        w(f"Run at an S2 bar of {S2_MIN:g}, not the rule of record ({S2_MIN_DEFAULT:.2f}). Tables, screen verdicts and the "
          "rule use this bar; sentences that name a verdict were written for the rule of record, so read the tables.")
        w("")
    # ---- 1. parameters
    w("## 1. Parameters")
    w("")
    P_ROWS = [
        ("Balance above the insured limit", "$100 million", "author assumption"),
        ("lambda_P; mu; LGD; a; D", f"{LAMBDA_P:.2%}; {MU:.0f}; {LGD:.0%}; {ADV:.0%} (linked to LGD, a = (2/3)(1 - LGD)); "
         f"{D_YEARS:.0f} years", "author assumption (the clearing-cost engine's base)"),
        ("r; s_b", f"{R_FREE:.1%}; {S_B:.1%}", "author assumption (the clearing-cost engine's base; r rounded from a reported "
                                              "3-month bill rate, as the clearing-cost engine states)"),
        ("rho", f"{RHO_PRICE:.2f} for prices, {RHO_REL:.2f} for reliability; Gaussian copula, Student-t(5) disclosed",
         "author assumption (the clearing-cost engine's)"),
        ("Screen S2 threshold; screen S5 standard", f"lendable share >= {S2_MIN:g}; P(not paid in full | own bank "
         f"fails) <= {S5_STD:.0%}, Gaussian, rho {RHO_REL:.2f}", "author assumption"),
        ("R1 over-collateralization", f"{R1_OVERCOLL:.0%} of the deposit", "reported figure, Cal. Gov. Code 53651 and "
                                                                         "53652 (via a secondary source)"),
        ("R1 cost, pledged from securities held; if bought", f"{rng_b(*R1_HELD)}; {b1(R1_SPREAD[0])} to "
         f"{b1(R1_SPREAD[1])} loan-to-security spread on {R1_OVERCOLL:.0%}", "author assumption, Chapter 4"),
        ("R2 public-unit letter fee by district", f"{rng_b(*R2_FEE)}; to {b1(R2_FEE_VAR)} variable-balance and "
         f"{b1(R2_FEE_OTHER)} other purposes at one district; activity stock {b1(R2_STOCK)} bps of the letter where "
         f"required (not priced here)", "reported figure, FHLBank Des Moines 2026; FHLBank San Francisco 2025; FHLBank "
                                       "Boston 2022; FHLBank Topeka 2023"),
        ("R3 placement fee", b1(R3_FEE), "reported figure, Chain Bridge Bancorp 2026 (one bank's disclosure)"),
        ("R3 rate uplift", ", ".join(b1(u) for u in R3_UPLIFT_SET) + f" (base {b1(R3_UPLIFT)})", "author assumption"),
        ("R4 replacement spread", rng_b(*R4_SPREAD), "author assumption, Chapter 3"),
        ("R7 always-on share; haircut", f"{R7_SHARE:.0%}; {R7_HAIRCUT:.0%} on bills", "author assumption, Chapter 6"),
        ("R7 terms: credit; access; encumbrance spread; frictions", f"{rng_b(*R7_CREDIT)}; {rng_b(*R7_ACCESS)}; "
         f"{rng_b(*R7_ENC)} on the bill slice; {rng_b(*R7_FRIC)}", "author assumption, Chapter 6"),
        ("R7 weekend net outflow / always-on tier", f"lognormal, median {R7_OUT_MED:.0%}, sigma {R7_OUT_SIG} (sweep "
         + ", ".join(str(s) for s in R7_OUT_SIG_SET) + f"); {R7_WEEKENDS} weekends a year, independent",
         "author assumption (illustrative)"),
        ("R8 shared-infrastructure saving", f"{R8_ACC_SHARE:.0%} of the smaller structure's access term plus "
         f"{b1(R8_FRIC_SAVE)} bp of frictions; swept from none to the full access term", "author assumption"),
        ("R9 prefunded share of the tokenized balance", f"{R9_SHARE:.0%} (by share: "
         + ", ".join(f"{x:.0%}" for x in R9_SHARE_SET) + ")", "author assumption, R9 block"),
        ("R9 joint-account balance earns IORB", f"{'yes' if R9_JA_INTEREST else 'no'} in the base (the other setting is "
         "shown as a sensitivity)", "reported figure for the RTP joint account, Board order effective 7 June 2023; no "
         "general rule for other joint accounts"),
        ("R9 IORB; 3-month bill (coupon-equivalent)", f"{R9_IORB:.2%}; {R9_BILL:.2%}", "reported figures, Board of "
         "Governors (IORB since 17 September 2026) and US Treasury, accessed 3 November 2026"),
        ("R9 terms: credit; access; loan spread over bills; frictions", f"{rng_b(*R9_CREDIT)}; {rng_b(*R9_ACCESS)}; "
         f"{rng_b(*R9_LOAN_SPREAD)} on the position; {rng_b(*R9_FRIC)}", "author assumption, R9 block"),
        ("R9 per-payment fee; per-payment limit; liquidity management transfer limit", "$0.045 per payment sent, nothing "
         f"to receive (negligible in bps); $10 million; ${R9_LMT_MAX / 1e6:.0f} million per transfer",
         "reported figures, The Clearing House RTP; FedNow Service operating procedures v3.7, 13 October 2026"),
        ("Banks: assets; liabilities / assets; covered excess / liabilities", "$50bn and $5bn; "
         f"{LIAB_RATIO:.0%}; {COVERED_SHARE:.0%}", "author assumption"),
        ("Reciprocal allowance (non-brokered)", "50% of the first $1bn of liabilities, 40% of the next $9bn, 30% above, "
         "at most $30bn; agent well capitalized, CAMELS 1 to 3", "reported figure, 12 CFR 337.6(e); FDIC 2026"),
        ("Replacement spread s_rep; retention cells", ", ".join(b1(s) for s in S_REP_SET) + "; none, V 100 with dP_run 1%,"
         " V 150 with dP_run 5%", "author assumption (the mutual model's)"),
        ("Mutual design (R6)", f"N {mt.N_BASE}, theta_m {mt.THETA_M:.0%} paid in, m {mt.M_SA}, reserve opportunity cost "
         f"{b1(mt.OPP)}, f_m {b1(mt.F_M)}, q_acq {mt.Q_ACQ}", "author assumption (the mutual model's)"),
    ]
    w(table(["Parameter", "Value", "Label"], [(a, b, f"[{c}]") for a, b, c in P_ROWS]))
    w("")
    # ---- 2. parity
    w("## 2. Parity with the imported engines")
    w("")
    w("Each headline is read from the imported engine in memory (no number is typed in) and compared at the precision the "
      "headline is quoted.")
    w("")
    w(table(["Headline", "Imported value", "Quoted", "Match"],
               [(nm, f"{x:.4f}", t, "pass" if ok else "FAIL") for nm, x, t, ok in PARITY_ROWS]))
    w("")
    w(f"Parity result: {'all rows pass' if PARITY_OK else 'at least one row fails'}.")
    w("")
    w(table(["Method check", "This model", "Engine", "Match"],
               [(nm, f"{a:.6f}", f"{b:.6f}", "pass" if abs(a - b) < 1e-9 else "FAIL") for nm, a, b in METHOD_CHECKS]))
    w("")
    # ---- 3. the risk
    w("## 3. The risk the balance carries")
    w("")
    w("Self-insured cost of the uninsured balance, the clearing-cost engine's credit + access terms (no transfer cost):")
    w("")
    w(table(["Measure", "Credit", "Access", "Self-insured (credit + access)"],
               [("Q (mu 3), pricing", b2(SI_Q["credit"]), b2(SI_Q["access"]), b2(SELF["Q"])),
                ("P (mu 1), real world", b2(SI_P["credit"]), b2(SI_P["access"]), b2(SELF["P"]))]))
    w("")
    w("Every route below either prices this risk, moves it to someone who does not charge for it, or removes the balance.")
    w("")
    # ---- 4. price list
    w("## 4. The price list")
    w("")
    w("One row per priced variant. 'Basis' says whether the figure is a model number or a reported or assumed range; "
      "reported figures are not model numbers. The t(5) column re-prices the same design under the Student-t(5) copula.")
    w("")
    rows = []
    for v in VARIANTS:
        t_ = b2(v["t_price"]) if v["t_price"] is not None else "n/a"
        rows.append((v["route"], v["label"], vrow_price(v), t_ + (f" ({v['t_note']})" if v["t_price"] is not None
                                                                  else f" ({v['t_note']})"), v["basis"], v["source"]))
    w(table(["Route", "Variant", "Price (bps a year)", "t(5) price", "Basis", "Source"], rows))
    w("")
    w(f"Reading the reported routes: R2's fee leaves the risk unpriced; fee plus the risk the super-lien moves to the fund "
      f"is {b1(R2_FEE[0] + R2_MOVED['Q'])} to {b1(R2_FEE[1] + R2_MOVED['Q'])} under Q ({b1(R2_FEE[0] + R2_MOVED['P'])} to "
      f"{b1(R2_FEE[1] + R2_MOVED['P'])} under P) [author's reading]. R3 by uplift: "
      + "; ".join(f"uplift {b1(u)} gives {b1(p)}" for u, p in R3_PRICES)
      + ". R4's spread applies to each dollar replaced, on the whole balance if it all leaves. R7 is a different product "
        "(liquidity outside funding-market hours), shown on the same scale for comparison only.")
    w("")
    w("R9 is a second liquidity product, priced from the author assumptions of the R9 block and shown on the same scale "
      "for comparison only.")
    w("")
    # ---- 5. lendable share and capacity
    w("## 5. Lendable share and capacity consumed")
    w("")
    w(table(["Route", "Variant", "Lendable share", "Capacity consumed ($100m balance)"],
               [(v["route"], v["label"], f"{v['lendable']:.2f}", v["capacity"]) for v in VARIANTS]))
    w("")
    w(f"R6's lendable share counts the member's {pcs(mt.THETA_M, 0)} capital contribution, held in bills at the mutual, as "
      f"not lendable; R7's counts the always-on tier, matched one for one by bills, as not lendable [author's reading].")
    w("")
    w(f"R9's counts the prefunded position, reserves held in the joint account, as not lendable (lendable share 1 minus "
      f"the prefunded share, {R9_LEND:.2f}); a top-up from the master account draws reserves the bank also cannot lend.")
    w("")
    # ---- 6. who bears
    w("## 6. Who bears the risk")
    w("")
    w("Where each route puts the self-insured cost of Section 3, bps a year on the balance, under Q and under P. All "
      "attributions are the author's reading. R6's rule-M access sits with the receivership, which carries the recovery "
      "of the excess when an acquirer takes every deposit at closure; R5 pooled's depositor share is the expected loss "
      "and access on par the buffer cannot pay.")
    w("")
    for m in ("Q", "P"):
        w(f"Under {m}:")
        w("")
        keys = ["R1", "R2", "R3", "R4", "R5 single", "R5 pooled", "R5 sized", "R6", "R6 alt", "R7", "R8", "R9"]
        w(table(["Route variant"] + BEARERS + ["Total"],
                   [[k] + [b2(BEAR[(k, m)][b]) for b in BEARERS] + [b2(sum(BEAR[(k, m)].values()))] for k in keys]))
        w("")
    w(f"Who pays when the risk is moved rather than priced: R2 moves {b2(R2_MOVED['P'])} bps a year under P "
      f"({b2(R2_MOVED['Q'])} under Q) to the deposit insurance fund through the FHLB super-lien; R7 moves up to "
      f"{b2(R7_MOVED['P'])} under P ({b2(R7_MOVED['Q'])} under Q) through the safe-harbored repo, an upper bound that "
      f"assumes every failure follows a weekend in which the capped outflow left; R4 moves the cost to borrowers or "
      f"shareholders through the replacement spread. R3 puts the risk on the fund against assessments, a priced public "
      f"cover.")
    w("")
    # ---- 7. route detail
    w("## 7. Route detail")
    w("")
    w("R7, the four terms at the illustrative inputs (bps a year on the whole tokenized balance; per tier dollar = "
      "divided by the always-on share):")
    w("")
    lo_t, hi_t = r7_terms(end=0), r7_terms(end=1)
    w(table(["Term", "Low", "High"], [(k.capitalize(), b1(lo_t[k]), b1(hi_t[k])) for k in lo_t]
               + [("Facility price, whole balance", b1(R7_LO), b1(R7_HI)),
                  ("Facility price, per always-on tier dollar", b1(R7_LO / R7_SHARE), b1(R7_HI / R7_SHARE)),
                  ("Memo: bank committed facility cost floor on the undrawn amount (Chapter 3)",
                   b1(cc.BANK_FEE_LO), b1(cc.BANK_FEE_HI))]))
    w("")
    w(f"Bills positioned: {pcs(R7_BILLS, 2)} of the tokenized balance (the {pcs(R7_SHARE, 0)} share grossed up for the "
      f"{pcs(R7_HAIRCUT, 0)} haircut). The usage charge between net debtors and net creditors nets to zero across "
      f"members and is not in the price.")
    w("")
    w("R7 by always-on share (the standing-capacity term scales with the share, the others do not):")
    w("")
    w(table(["Always-on share", "Price, whole balance", "Per tier dollar", "Lendable share", "S2"],
               [(pcs(s, 0), rng_b(lo, hi), rng_b(lo / s, hi / s), f"{ln:.2f}", "pass" if ln >= S2_MIN - 1e-12 else "fail")
                for s, lo, hi, ln in R7_SHARE_ROWS]))
    w("")
    w(f"How often the cap binds (illustrative): weekend net outflow as a share of the always-on tier, lognormal with "
      f"median {R7_OUT_MED:.0%}; the cap binds when the outflow exceeds the tier. Per year assumes {R7_WEEKENDS} "
      f"independent weekends; serial dependence across weekends is not modelled. Monte Carlo check: {R7_MC_N:,} draws, seed {R7_MC_SEED}.")
    w("")
    w(table(["sigma", "P(cap binds) per weekend", "Weekends a year it binds (mean)", "P(binds at least once a year)",
                "Monte Carlo per weekend (z)"],
               [(f"{r['sig']:.1f}", pcs(r["p"], 3), f"{r['n']:.2f}", pcs(r["year"], 1), f"{pcs(r['mc'], 3)} ({r['z']:+.2f})")
                for r in R7_BIND]))
    w("")
    w(f"R8, the shared-infrastructure saving. The smaller structure's access term is the smaller of R6's access "
      f"({b2(R6_ACCESS)}, the clearing-cost engine's four-term access) and R7's ({b1(R7_ACCESS[0])} to {b1(R7_ACCESS[1])}), so "
      f"{b2(A_SMALL)} [author assumption]. The credit tranche and the liquidity tranche share a ledger and no reserve.")
    w("")
    w(table(["Share of the access term saved", "Saving", "R8 price, whole balance", "Memo: saving if R7's membership access "
                                                                                       f"({b1(R7_ACCESS[0])} to {b1(R7_ACCESS[1])}) is the term"],
               [(f"{s:.0%}" if s > 0 else "none (no frictions saved either)", b2(R8_SAVE[s]),
                 rng_b(R6["ref"]["pi"] + R7_LO - R8_SAVE[s], R6["ref"]["pi"] + R7_HI - R8_SAVE[s]),
                 f"{b2(R8_SAVE_ALT[s])} to {b2(R8_SAVE_ALT_HI[s])}") for s in R8_SHARE_SET]))
    w("")
    w(f"R8 range reported: {rng_b(R8_LO, R8_HI)} (base {b1(R8_BASE)}); under t(5), R6's price becomes {b2(R6_T['ref'])}.")
    w("")
    w("R9, prefunded joint-account instant settlement (the design of The Clearing House RTP network), the four terms at "
      f"the illustrative inputs of the R9 block, at a {pcs(R9_SHARE, 0)} prefunded share (bps a year on the whole "
      f"tokenized balance). An operator holds a joint account at a Reserve Bank; each member prefunds its position during "
      f"Fedwire hours; weekend transfers between members settle instantly and finally against positions in central bank "
      f"money; positions can be topped up at any hour by FedNow liquidity management transfers from the member's master "
      f"account (RTP Operating Rules effective 1 November 2026 allow weekend funding by liquidity management transfer "
      f"where the participant enables it, and defunding by the same route while Fedwire is closed; FedNow Operating "
      f"Circular 8, Section 9.7.1, allows such transfers for an instant payment system backed by a joint account); a "
      f"payment beyond the sender's position is rejected, not queued. Capacity is the opportunity cost of reserves held "
      f"in the joint account instead of loans, measured against bills: the prefunded share times the loan spread over "
      f"bills ({rng_b(*R9_LOAN_SPREAD)}) plus the bill yield over IORB ({b1(R9_BILL - R9_IORB)} at {R9_BILL:.2%} and "
      f"{R9_IORB:.2%}) when the balance earns IORB, or plus the whole bill yield when it earns nothing. Base: the "
      f"balance {'earns' if R9_JA_INTEREST else 'earns no'} IORB (the RTP joint account's treatment). The prefunded "
      f"slice is not counted as HQLA in the base.")
    w("")
    lo9, hi9 = r9_terms(end=0), r9_terms(end=1)
    lo9a, hi9a = r9_terms(end=0, interest=R9_ALT), r9_terms(end=1, interest=R9_ALT)
    w(table(["Term", "Low", "High", f"Memo: low, balance {'earning' if R9_ALT else 'earning no'} interest",
             "Memo: high"],
            [(k.capitalize(), b1(lo9[k]), b1(hi9[k]), b1(lo9a[k]), b1(hi9a[k])) for k in lo9]
            + [("Price, whole balance", b1(R9_LO), b1(R9_HI), b1(R9_ALT_LO), b1(R9_ALT_HI)),
               ("Price, per prefunded dollar", b1(R9_LO / R9_SHARE), b1(R9_HI / R9_SHARE), b1(R9_ALT_LO / R9_SHARE),
                b1(R9_ALT_HI / R9_SHARE))]))
    w("")
    w("R9 by prefunded share (lendable share 1 minus the share, the absolute convention):")
    w("")
    w(table(["Prefunded share", "Price, whole balance", f"Memo: balance {'earning' if R9_ALT else 'earning no'} interest",
             "Lendable share", "S2"],
            [(pcs(s_, 0), rng_b(lo, hi), rng_b(alo, ahi), f"{ln:.2f}", "pass" if ln >= S2_MIN - 1e-12 else "fail")
             for s_, lo, hi, alo, ahi, ln in R9_SHARE_ROWS]))
    w("")
    w(f"At a {pcs(R9_SHARE, 0)} prefunded share R9's base price is {b2(R9_BASE)} with the balance "
      f"{'earning' if R9_JA_INTEREST else 'earning no'} interest and {b2(R9_ALT_BASE)} with it "
      f"{'earning' if R9_ALT else 'earning no'} interest, against R7's {b2(R7_BASE)}. At equal shares R9's base is below "
      f"R7's only at a share below {pcs(R9_BE_SHARE, 1)}, because the bill yield over IORB adds to the loan spread.")
    w("")
    w(f"Memo: R7's Sunday settlement cash. At the Sunday 21:00 Fedwire Funds opening a net debtor settles in reserves "
      f"and needs capacity of at least its cap, the {pcs(R7_SHARE, 0)} always-on share. R7's published price assumes case "
      "(a); cases (b1) and (b2) add the cost of that capacity, on this engine's own constants. The bills' haircut "
      f"gross-up ({R7_SHARE:.2f} / {1 - R7_HAIRCUT:.2f}) is not charged again: it sits in frictions.")
    w("")
    _crs = lambda c: ("R9 cheaper at every share" if R7_SUN[c]["cross"] is None
                      else f"R9 cheaper below a share of {pcs(R7_SUN[c]['cross'], 2)}")
    w(table(["R7 Sunday settlement cash", "Range, whole balance", "Base", "Lendable share (absolute)",
             "Base by share s (bps)", "Against R9 at equal shares"],
            [(R7_SUN_LABEL[c], rng_b(d["lo"], d["hi"]), b2(d["base"]), f"{d['lend']:.2f}",
              f"{b2(d['ic'])} + {b1(d['sl'])}s", _crs(c)) for c, d in R7_SUN.items()]
            + [("R9 (published)", rng_b(R9_LO, R9_HI), b2(R9_BASE), f"{R9_LEND:.2f}", f"{b2(_r9_ic)} + {b1(_r9_sl)}s", "")]))
    w("")
    w((f"In case (a) R9 crosses R7 at a share of {pcs(R7_SUN['a']['cross'], 2)}, as above. "
       if R7_SUN["a"]["cross"] is not None else "In case (a) R9 is cheaper at every share at these inputs. ")
      + f"In cases (b1) and (b2) R7 has "
      f"the higher intercept and the steeper slope, so R9 is cheaper at every share. At the published "
      f"{pcs(R7_SHARE, 0)} share R9's base ({b2(R9_BASE)}) is below R7's once {pcs(R7_SUN_TIE['b2'], 1)} of the Sunday "
      f"capacity comes from new reserves, or {pcs(R7_SUN_TIE['b1'], 1)} from bought securities, the rest from loans "
      "already pledged at the Reserve Bank.")
    w("")
    w(f"Rejection, not queueing. Without a weekend top-up a payment is rejected when the member's weekend peak debit "
      f"(lognormal, median {pcs(_R9_PEAK_MED, 1)} of the balance, sigma {R7_OUT_SIG}, the routes engine's outflow) passes "
      f"its position. A top-up by liquidity management transfer (up to ${R9_LMT_MAX / 1e6:.0f} million each) lowers the "
      f"rejection rate only by drawing master-account reserves the bank also cannot lend.")
    w("")
    w(table(["Prefunded share", "P(a payment is rejected) per weekend", "Expected rejected amount, share of the balance",
             "Lendable share"],
            [(pcs(sh, 0), pcs(pr, 3), pcs(er, 4), f"{1 - sh:.2f}") for sh, pr, er in R9_REJ]))
    w("")
    # ---- 8. screens
    w("## 8. Screens")
    w("")
    w("Verdicts are pass, fail, open (a question the sources do not settle) or n/a, each with a one-line reason and its "
      "source. S5 is computed for R5, R6 and R8, passes by construction for R3 and is n/a where the route has no failure "
      "payoff.")
    w("")
    w(table(["Screen", "Definition"], SCREENS))
    w("")
    grid_keys = ["R1 held", "R2", "R3", "R4", "R5 single", "R5 pooled", "R5 sized", "R6", "R6 alt", "R7", "R8", "R9"]
    w(table(["Variant"] + [s for s, _ in SCREENS],
               [[k] + [VBY[k]["screens"][s][0] for s, _ in SCREENS] for k in grid_keys]))
    w("")
    w("Reasons and sources (R1 bought shares R1 held's verdicts):")
    w("")
    rr = []
    for k in grid_keys:
        v = VBY[k]
        for s, _ in SCREENS:
            if k in ("R5 pooled", "R5 sized", "R6 alt") and s != "S5":
                continue
            vd, reason, src = v["screens"][s]
            rr.append((k, s, vd, reason, src))
    w(table(["Variant", "Screen", "Verdict", "Reason", "Source"], rr))
    w("")
    # ---- 9. the rule
    w("## 9. The rule: champion and challenger")
    w("")
    w("Rule [author assumption, stated before the numbers]: among routes passing every applicable screen, the champion is "
      "the cheapest all-in price (base of the route's range) and the challenger the next cheapest route; variants of one "
      "route compete inside the route first. An 'open' verdict is not a pass. The rule is also run with every open item "
      "resolved in the route's favor, to show what the open items decide. Applicable screens: S1 to S5 for problem (a) "
      "and for both together; S1, S3 and S4 for problem (b), whose objective is movement, not lendable funding or "
      "failure cover (convention for the author to confirm; the result with S2 also applied to (b) is shown).")
    w("")
    rows = []
    for p, pn in PROBLEMS:
        for l in (False, True):
            r = RULE[(p, l)]
            c, h = r["champion"], r["challenger"]
            nxt = [v for v in r["variants"] if c is not None and v["key"] != c["key"]]
            rows.append((pn, "open items resolved in the route's favor" if l else "strict (open is not a pass)",
                         describe(c), describe(h), describe(nxt[0]) if nxt else "none"))
    w(table(["Problem", "Reading", "Champion", "Challenger (next route)", "Next-cheapest passing variant"], rows))
    w("")
    w("With S2 also applied to problem (b): " + ("; ".join(f"{'open resolved' if l else 'strict'}: "
      + (", ".join(v["key"] for v in RULE_S2B[l]) or "no route passes") for l in (False, True))) + ".")
    w("")
    w(f"R9 in the rule: it applies to problem (b) only. Its S1 is open (Reserve Bank approval of a new joint account, under the Board's 2017 guidelines, not yet "
      f"sought), so it does not qualify under the strict reading; with open items resolved it competes at its base "
      f"{b2(R9_BASE)}. With the interest switch at its other setting (balance "
      f"{'earning' if R9_ALT else 'earning no'} interest, base {b2(R9_ALT_BASE)}), problem (b) gives: "
      + "; ".join(f"{'open resolved' if l else 'strict'}: champion {describe(RULE_R9_ALT[l]['champion'])}, challenger "
                  f"{describe(RULE_R9_ALT[l]['challenger'])}" for l in (False, True)) + ".")
    w("")
    _sun_txt = lambda l: "; ".join(f"case ({c}): champion {_short(RULE_SUN[(c, l)]['champion'])}, challenger "
                                   f"{_short(RULE_SUN[(c, l)]['challenger'])}" for c in R7_SUN_LABEL)
    w("Memo, R7's Sunday settlement cash (Section 7; R8, which contains R7, carries the same extra term), problem (b): "
      f"strict: {_sun_txt(False)}. Open items resolved: {_sun_txt(True)}. Under the open-resolved reading the "
      f"settlement champion is {_key(RULE_SUN[('a', True)]['champion'])} in case (a) and "
      f"{' and '.join(sorted({str(_key(RULE_SUN[(c, True)]['champion'])) for c in ('b1', 'b2')}))} in case (b). The "
      "published rule above is case (a).")
    w("")
    w("Champion and challenger beside what the Gaussian standard hides (P(not paid in full given own bank fails), rho 0.30):")
    w("")
    show = []
    for p, l in (("a", False), ("a", True)):
        for role in ("champion", "challenger"):
            v = RULE[(p, l)][role]
            if v is not None and v["key"] not in [x[0] for x in show]:
                show.append((v["key"], role, "strict" if not l else "open resolved"))
    rows = []
    for k, role, rd in show:
        v = VBY[k]
        rows.append((f"{k} ({role}, {rd})", b2(v["base"]),
                     b2(v["t_price"]) if v["t_price"] is not None else "n/a",
                     sf_txt(v["sf_g"]) if v["sf_g"] is not None else "n/a",
                     sf_txt(v["sf_t"]) if v["sf_t"] is not None else "n/a"))
    w(table(["Route", "Gaussian price", "t(5) price, same design", "Gaussian shortfall", "t(5) shortfall"], rows))
    w("")
    w("Reliability of every computed design (S5 is the Gaussian column):")
    w("")
    w(table(["Design", "Price", "t(5) price, same design", "Gaussian: short", "Gaussian: paid in full", "t(5): short"],
               [(lab, b2(pg), b2(pt), sf_txt(g), pcs(1 - g, 2), sf_txt(t)) for _, lab, g, t, pg, pt in REL_ROWS]))
    w("")
    w(f"The clearing-cost engine's reference design misses S5 by {pcs(R5_SF[('ref', 'gauss')] - S5_STD, 4)}: 10 failures of 2% leave "
      f"{pcs(R5_SF[('ref', 'gauss')], 3)} short. One more failure of capacity ({K_STD} in all) passes at "
      f"{b2(R5_STD['c_star'])} bps, {b2(R5_STD['c_star'] - R5_REF['c_star'])} more. The clearing-cost engine's t(5) 5% design needs "
      f"{K_STD_T} failures ({pcs(K_STD_T / cc.V5_N, 0)}) at {b2(R5_TSTD['c_star'])}; the mutual's t(5) 5% design costs "
      f"{b2(R6['alt']['pi'])}.")
    w("")
    # ---- 9b. S2 bar sensitivity
    w("## 9b. S2 bar sensitivity")
    w("")
    w(f"The rule of record keeps S2 at {S2_MIN_DEFAULT:.2f}. This section re-scores S2 at bars of "
      f"{', '.join(f'{b:.2f}' for b in S2_BARS)} at the published route parameters and reruns the rule; nothing else "
      "moves. S2 applies to problem (a) and to (a) and (b) together; problem (b) as specified does not apply it, so its "
      "champion does not move with the bar, and the variant with S2 also applied to (b) is shown beside it. A bar below "
      f"{S2_MIN_DEFAULT:.2f} is reasonable only if the route's encumbered bills or reserves can also be the bank's own "
      "liquidity buffer against the same deposit, a question this engine does not settle; if they cannot, the "
      "encumbrance stacks on the buffer and a lower bar overstates what the bank keeps lending. R7 is at its Sunday "
      "settlement cash case (a) (Section 7).")
    w("")
    w(table(["Variant", "Lendable share (absolute)"] + [f"S2 at {b:.2f}" for b in S2_BARS],
            [(k, f"{VBY[k]['lendable']:.2f}") + tuple(s2_verdict(VBY[k]["lendable"], b) for b in S2_BARS)
             for k in grid_keys]))
    w("")
    w(table(["Bar", "Problem", "Strict: champion", "Strict: challenger", "Open resolved: champion",
             "Open resolved: challenger"],
            [(f"{b:.2f}", pn, _short(S2_SENS[(b, pk, False)]["champion"]), _short(S2_SENS[(b, pk, False)]["challenger"]),
              _short(S2_SENS[(b, pk, True)]["champion"]), _short(S2_SENS[(b, pk, True)]["challenger"]))
             for b in S2_BARS for pk, pn, _ in S2_PROBLEMS]))
    w("")
    w(table(["Bar", "R7: largest always-on share", f"R8: largest always-on share (with the {pcs(mt.THETA_M, 0)} capital "
             "contribution)", "R9: largest prefunded share"],
            [(f"{b:.2f}", pcs(S2_SENS_MAX[b]["R7"], 0), pcs(S2_SENS_MAX[b]["R8"], 0), pcs(S2_SENS_MAX[b]["R9"], 0))
             for b in S2_BARS]))
    w("")
    w("Variants failing S2, by bar: " + "; ".join(
        f"{b:.2f}: " + (", ".join(k for k in grid_keys if s2_verdict(VBY[k]["lendable"], b) == "fail") or "none")
        for b in S2_BARS) + f". With R7's Sunday settlement cash in case (b1) or (b2) its lendable share is "
      f"{R7_SUN['b1']['lend']:.2f}, which fails S2 at every bar in the grid"
      + ("" if R7_SUN["b1"]["lend"] < min(S2_BARS) - 1e-12 else " (CHECK: it does not)") + ".")
    w("")
    if S2_SENS_SELF is not None:
        w(f"Check: at this run's bar ({S2_MIN:.2f}) the table reproduces Section 9: {'yes' if S2_SENS_SELF else 'NO'}.")
        w("")
    # ---- 10. dollars
    w("## 10. Dollars for two banks")
    w("")
    w(table(["Bank", "Liabilities", "Covered excess (20% of liabilities)", "Reciprocal allowance", "Allowance / "
                "liabilities", "Marginal tier", "Headroom over covered excess", "Mutual capital contribution (3%)"],
               [(r["name"], f"${r['liab'] / 1e9:.2f}bn", f"${r['cov'] / 1e9:.2f}bn", f"${r['cap'] / 1e9:.2f}bn",
                 pcs(r["cap_share"], 1), pcs(r["tier"], 0), f"${r['headroom'] / 1e9:.2f}bn", f"${r['capital'] / 1e6:.0f}m")
                for r in BANK_ROWS]))
    w("")
    a50, a5 = BANK_ROWS
    w(f"The reciprocal tier changes the arithmetic: the allowance is {pcs(a50['cap_share'], 1)} of liabilities at the "
      f"$50bn bank (marginal tier {pcs(a50['tier'], 0)}) and {pcs(a5['cap_share'], 1)} at the $5bn bank (marginal tier "
      f"{pcs(a5['tier'], 0)}), so at a 20% covered share neither binds; the cap binds once reciprocal holdings pass "
      f"{pcs(a50['cap_share'], 1)} and {pcs(a5['cap_share'], 1)} of liabilities, beyond which placements are brokered. "
      f"Existing reciprocal holdings use the same allowance. Fees in bps are the same at both banks; the fixed-cost terms "
      f"(R5 frictions, R7 access, the mutual's f_m) would be dearer per dollar at the small bank, which this table does "
      f"not model.")
    w("")
    w("Annual cost of each route on the covered excess, $ million a year (low to high, base):")
    w("")
    rows = []
    for v in VARIANTS:
        cells = [v["route"], v["label"]]
        for r in BANK_ROWS:
            lo, bs, hi = r["cost"][v["key"]]
            cells.append(f"{lo / 1e6:,.1f}" if lo == hi else f"{lo / 1e6:,.1f} to {hi / 1e6:,.1f} ({bs / 1e6:,.1f})")
        rows.append(cells)
    w(table(["Route", "Variant"] + [r["name"] for r in BANK_ROWS], rows))
    w("")
    w("Replacement-cost ceiling and the depositor advantage that clears (the mutual model's Section 12 logic): protection "
      "clears when Delta + WTP + replacement value >= price. Full count: the replacement spread in full each year (the "
      "ceiling on what the bank should pay to keep the balance). Probability-weighted: dP_run x s_rep x the clearing-cost engine's "
      f"five-year annuity ({ANNUITY:.3f}). Minimum Delta in bps; the ceiling in $ million a year on each bank's covered "
      "excess.")
    w("")
    hdr = ["s_rep", "Retention cell", "Ceiling, $50bn bank ($m)", "Ceiling, $5bn bank ($m)"]
    for k, c in CLEAR_PRICES:
        hdr += [f"Min Delta, full count: {k} ({b2(c)})", f"Min Delta, weighted: {k}"]
    rows = []
    for row in CLEAR_ROWS:
        cell = "none" if row["V"] == 0 else f"V {row['V'] / BP:.0f}, dP_run {row['dp']:.0%}"
        cells = [b1(row["s_rep"]), cell] + [f"{row['full'] * r['cov'] / 1e6:,.1f}" for r in BANK_ROWS]
        for k, _ in CLEAR_PRICES:
            cells += [b1(row[("full", k)]), b1(row[("wtd", k)])]
        rows.append(cells)
    w(table(hdr, rows))
    w("")
    w(f"In dollars the depositor advantage that clears scales with the covered excess: at the $50bn bank each bp of Delta "
      f"is ${a50['cov'] * BP / 1e6:.2f}m a year, at the $5bn bank ${a5['cov'] * BP / 1e6:.2f}m. Against them, letting the "
      f"balance go and replacing it costs ${R4_SPREAD[0] * a50['cov'] / 1e6:,.0f}m to ${R4_SPREAD[1] * a50['cov'] / 1e6:,.0f}m "
      f"a year at the $50bn bank and ${R4_SPREAD[0] * a5['cov'] / 1e6:,.1f}m to ${R4_SPREAD[1] * a5['cov'] / 1e6:,.1f}m at "
      f"the $5bn bank.")
    w("")
    # ---- 10b. by deposit type
    w("## 10b. By deposit type: which clock, and what the routes cost")
    w("")
    w("Not every deposit runs on both clocks. A plain account above the insured limit runs on the run clock only; a "
      "tokenized balance runs on the settlement clock whether it is insured or not, where its transfers are netted between "
      "banks; a tokenized balance above the limit "
      "runs on both. Each row is a priced variant of this list, open items resolved and S2 not applied (the strict R5 row "
      "excepted), so the table prices the risk each type carries and does not choose a route. For both clocks the routes "
      "stack: R8 is R6 plus R7 less the shared ledger, and R6 plus R9 is the pairing with no shared ledger, for which no "
      "saving is priced. Lendable shares are on the absolute convention, so the encumbrances add. bps a year on the whole "
      "balance, low to high with the base.")
    w("")
    w(table(["Deposit", "Clock(s)", "Route on the list", "Price (base)", "Lendable share", "Source"],
            [(r["deposit"], r["clocks"], r["hedge"],
              "0" if r["hi"] == 0 else (b2(r["base"]) if abs(r["hi"] - r["lo"]) < 1e-15
                                        else f"{rng_b(r['lo'], r['hi'])} ({b2(r['base'])})"),
              f"{r['lend']:.2f}", r["basis"]) for r in DT_ROWS]))
    w("")
    w(f"The self-insured cost of the run clock alone, with nothing for moving it, is {b2(SELF['Q'])} bps under the pricing "
      f"measure and {b2(SELF['P'])} under the real-world measure (Section 3); it is the charge a plain uninsured account "
      "carries with no route bought, and the settlement clock adds its own capacity cost to it on a tokenized balance.")
    w("")
    w(table(["Sunday settlement cash", "Cheapest route for both clocks", "Price (base)", "Lendable share",
             "Added by the settlement clock over R6, bps", "Lendable share lost to it"],
            [(R7_SUN_LABEL[c].split(")")[0] + ")", DT_BOTH[c]["hedge"], b2(DT_BOTH[c]["base"]), f"{DT_BOTH[c]['lend']:.2f}",
              b2(DT_EXTRA[c][0]), f"{DT_EXTRA[c][1]:.2f}") for c in ("a", "b1", "b2")]))
    w("")
    w("Check: the R8 row reproduces R6 plus R7 less the shared-ledger saving, and its lendable share R6's less the "
      "always-on share: yes.")
    w("")
    # ---- 11. sensitivities
    w("## 11. Sensitivities on the champion")
    w("")
    w(f"One input at a time from the base; each case re-sizes capacity to the S5 standard (Gaussian, rho "
      f"{RHO_REL:.2f}, {S5_STD:.0%}), so the price carries the cost of staying at the standard. The rho row moves the "
      f"pricing correlation only; the S5 standard stays at rho {RHO_REL:.2f} by its definition. For R6 the mutual's "
      f"inputs move over the mutual model's ranges; for R5 the analogues are the vehicle's lock-up premium and frictions over "
      f"the clearing-cost engine's ranges. R5's price does not move with the pricing rho: with fixed LGD and no facility, its credit and "
      f"access are expectations that the correlation does not change.")
    w("")
    for route, rows_ in SENS.items():
        champ_tag = []
        if CHAMP_STRICT is not None and CHAMP_STRICT["route"] == route:
            champ_tag.append("strict champion")
        if CHAMP_OPEN is not None and CHAMP_OPEN["route"] == route:
            champ_tag.append("champion with open items resolved")
        w(f"{route} ({', '.join(champ_tag)}):")
        w("")
        if route == "R6":
            w(table(["Input", "Value", "X", "A", "T", "Mutual", "Tail", "All-in", "Gaussian short"],
                       [(lab, vs, pcs(r["X"], 1), pcs(r["A"], 3), pcs(r["T"], 3), b2(r["mutual"]), b2(r["tail"]), b2(r["pi"]),
                         pcs(r["short"], 2)) if r is not None else (lab, vs, "n/a", "", "", "", "", "", "")
                        for lab, vs, _, r in rows_]))
        else:
            w(table(["Input", "Value", "Failures covered", "Capacity", "Price", "Gaussian short"],
                       [(lab, vs, str(r["k"]), pcs(r["theta"], 0), b2(r["pi"]), pcs(r["short"], 3)) for lab, vs, _, r in rows_]))
        w("")
        w("Range of the price across each sweep, widest first:")
        w("")
        w(table(["Input", "Low", "High", "Spread"],
                   [(lab, b2(lo), b2(hi), b2(hi - lo)) for lab, (lo, hi) in reversed(TORNADO[route])]))
        w("")
    # ---- 12. conventions
    w("## 12. Conventions and limits")
    w("")
    notes = [
        "The engine prices only routes with a failure payoff. R1 to R4 carry the fee ranges of Chapter 4 "
        "(reported figures where a source is named, author assumptions otherwise) and the engine supplies what it can: "
        "the self-insured cost each route moves, lendable share and capacity.",
        "Base price of a range is its midpoint; the rule ranks on base prices. Under the strict rule only model-priced "
        "routes qualify; with open items resolved, R7 and R8 compete for problem (b), and R8 contains R7, so R8 is dearer at "
        "every point of the range and the midpoint convention decides nothing in this run.",
        "R5 is shown at three designs: single name (fully funded, never short), the clearing-cost engine's reference design and the "
        "clearing-cost engine's own iso-reliability row at the S5 standard, so that R5 and R6 are both sized to the same standard.",
        "R6's price is per unit of covered excess (the excess not placed through the reciprocal network); the reciprocal "
        "base is R3 and is outside the model.",
        "Who bears the risk is the author's reading of where the self-insured cost lands; amounts are expectations of the "
        "clearing-cost engine's credit and access terms under each measure.",
        "R7's cap-binding figure treats weekends as independent and the outflow share as lognormal; Chapter 6 "
        "proposes a factor model with Gaussian and Student-t(5) factors, which is not built here.",
        "Sensitivities re-size to the Gaussian standard at rho 0.30; the t(5) standard is reported beside the champion "
        "rather than re-sized in each case.",
        "Fixed-cost scale effects at a small bank, FHLB activity-stock cost and the national-bank investment-power "
        "question on the mutual's capital contribution are not modelled.",
        "R9's parameters sit in one labelled block: IORB, the bill rate, fees and limits are reported figures; the "
        "credit, access, loan spread and frictions ranges are author assumptions. The base follows the RTP joint "
        "account, whose balances earn IORB by a Board order specific to it; a new joint account without such an "
        "order earns nothing, shown as a sensitivity. R9 is sized at R7's 20% share for a like-for-like comparison; "
        "rejection is computed without weekend top-ups. The prefunded slice is not counted as HQLA.",
    ]
    for i, n in enumerate(notes, 1):
        w(f"{i}. {n}")
    w("")
    txt = "\n".join(L)
    for bad in (chr(0x2014), chr(0xA7)):
        if bad in txt:
            raise RuntimeError("forbidden character in results")
    RESULTS_MD.write_text(txt, encoding="utf-8")


# =============================================================================
# 11. FIGURES
# =============================================================================
def make_figures():
    import logging
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

    # palette and frame of the mutual model's figures
    NAVY, STEEL, SLATE, MIST, INK, GRID, ACCENT = "#1F3A5F", "#4F74A8", "#8A9AAE", "#C9D3DF", "#2B2B2B", "#E3E7EC", "#D2851F"
    MUTED, DARKACC, BRICK, SAGE = "#4A5361", "#9A5A0A", "#A4473A", "#6E8F7A"
    fam = "Inter" if any(f.name == "Inter" for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
    plt.rcParams.update({
        "font.family": fam, "font.size": 10, "axes.edgecolor": "#8C96A3", "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "text.color": INK, "hatch.color": "#FFFFFF", "hatch.linewidth": 1.0,
    })
    SRC = "Source: author's calculations."
    ILL = "Illustrative parameters, calibrated to no bank."

    def frame(fig, title, subtitle, source):
        fig.text(0.06, 0.955, title, fontsize=14, fontweight="semibold", ha="left", va="top", color=INK)
        fig.text(0.06, 0.905, subtitle, fontsize=10, ha="left", va="top", color="#5A6472")
        fig.text(0.06, 0.03, source, fontsize=7.5, ha="left", va="bottom", color="#6B7480")

    def save(fig, n):
        fig.savefig(FIG(n), dpi=200)
        plt.close(fig)

    BCOL = {"Depositor": ACCENT, "Bank's own encumbered collateral": SLATE, "Deposit insurance fund": STEEL,
            "FHLB super-lien": BRICK, "Private buffer": NAVY, "Mutual members": SAGE, "Leaves with the balance": MIST}
    BAS_COL = {"reported": SLATE, "model": NAVY, "illustrative": STEEL}

    # ---- U01: the two problems ------------------------------------------------------------------------------
    fig, (axr, axl) = plt.subplots(1, 2, figsize=(11, 5.6), gridspec_kw=dict(width_ratios=[1, 2.1]))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.2, wspace=0.42)
    opens = [(0, 19)] + [(21 + 24 * i, 43 + 24 * i) for i in range(4)] + [(165, 168)]
    axl.broken_barh([(a, b - a) for a, b in opens], (1.1, 0.7), facecolors=NAVY)
    axl.broken_barh([(0, 168)], (0.1, 0.7), facecolors=ACCENT)
    axl.axvspan(115, 165, color=MIST, alpha=0.45, lw=0)
    axl.text(140, 2.05, "Fedwire closed\nFri 19:00 to Sun 21:00 ET (50 hours)", ha="center", va="bottom", fontsize=8.5,
             color=MUTED)
    axl.set_yticks([0.45, 1.45])
    axl.set_yticklabels(["Tokenized deposit\nledger (24/7)", "Fedwire Funds\n(central bank money)"], fontsize=9)
    axl.set_xticks([24 * i for i in range(8)])
    axl.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun", ""], fontsize=9)
    axl.set_xlim(0, 168)
    axl.set_ylim(0, 2.6)
    axl.set_xlabel("Hours of one week, Eastern time: Fedwire open 22 hours on each of five days (110 of 168)",
                   fontsize=9, color=MUTED)
    axl.set_title("(b) Moving the balance outside funding-market hours", fontsize=10, loc="left", color=INK)
    for i, (m, vals) in enumerate((("Q", SI_Q), ("P", SI_P))):
        axr.bar(i, vals["credit"] / BP, 0.55, color=NAVY)
        axr.bar(i, vals["access"] / BP, 0.55, bottom=vals["credit"] / BP, color=STEEL)
        axr.text(i, (vals["credit"] + vals["access"]) / BP + 0.4, f"{b1(vals['credit'] + vals['access'])}", ha="center",
                 va="bottom", fontsize=9.5, fontweight="semibold")
    axr.set_xticks([0, 1])
    axr.set_xticklabels(["Pricing measure Q\n(mu 3)", "Real world P\n(mu 1)"], fontsize=9)
    axr.set_ylabel("bps a year on the balance", fontsize=9, color=MUTED)
    axr.set_ylim(0, 25)
    axr.yaxis.grid(True, color=GRID, lw=0.8)
    axr.set_axisbelow(True)
    axr.set_title("(a) The risk each route must place", fontsize=10, loc="left", color=INK)
    axr.legend(handles=[Patch(color=NAVY, label="Credit"), Patch(color=STEEL, label="Access")], frameon=False,
               fontsize=8.5, loc="upper right")
    frame(fig, "Two problems in one large uninsured balance",
          "Left: the self-insured cost, credit plus access, that each route prices, moves or removes. Right: the large-value\n"
          "settlement asset keeps business hours, the tokenized deposit does not.",
          f"{SRC} Fedwire hours: Federal Reserve Financial Services (2026a). {ILL}")
    save(fig, 1)

    # ---- U02: the price list ----------------------------------------------------------------------------------
    order = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"]
    fig, ax = plt.subplots(figsize=(11, 6.8))
    fig.subplots_adjust(left=0.27, right=0.96, top=0.8, bottom=0.22)
    for i, rt in enumerate(order):
        y = len(order) - 1 - i
        vs = [v for v in VARIANTS if v["route"] == rt]
        lo, hi = min(v["lo"] for v in vs) / BP, max(v["hi"] for v in vs) / BP
        bas = vs[0]["basis"]
        col = BAS_COL["model"] if bas.startswith("model") else BAS_COL["illustrative"] if "illustrative" in bas else BAS_COL["reported"]
        hatch = "////" if rt in ("R7", "R9") else None
        ax.barh(y, max(hi - lo, hi * 0.04), left=lo if hi > lo else lo * 0.98, height=0.5, color=col, hatch=hatch,
                edgecolor="white" if hatch else None, lw=0)
        if rt == "R1":
            ax.barh(y, (R1_HELD[1] - R1_HELD[0]) / BP, left=R1_HELD[0] / BP, height=0.5, color=col)
            ax.barh(y, (R1_HELD[1] * 1.0 - R1_HELD[1]) / BP + (R1_BOUGHT[0] - R1_HELD[1]) / BP, left=R1_HELD[1] / BP,
                    height=0.5, color="white")
        for v in vs:
            if v["lo"] == v["hi"]:
                ax.plot(v["base"] / BP, y, marker="|", ms=16, mew=2.2, color=ACCENT)
        lab = f"{lo:.1f} to {hi:.1f}" if hi > lo + 1e-9 else f"{lo:.2f}"
        if rt in ("R5", "R6"):
            lab = " / ".join(f"{v['base'] / BP:.2f}" for v in sorted(vs, key=lambda v: v["base"]))
        ax.text(hi * 1.07, y, lab, va="center", fontsize=8.3, color=MUTED)
    ax.axvline(SELF["Q"] / BP, color=ACCENT, lw=1.3, ls=(0, (4, 2)))
    ax.text(SELF["Q"] / BP * 1.03, len(order) - 0.45, f"Self-insured risk {b1(SELF['Q'])} (Q)", color=DARKACC, fontsize=8.5,
            va="bottom")
    ax.set_xscale("log")
    ax.set_xlim(5, 900)
    ax.set_xticks([5, 10, 20, 50, 100, 200, 500])
    ax.set_xticklabels(["5", "10", "20", "50", "100", "200", "500"])
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{rt}  {RSHORT[rt]}" for rt in reversed(order)], fontsize=8.8)
    ax.set_xlabel("bps a year on the $100m balance (log scale)", fontsize=9.5, color=MUTED)
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(handles=[Patch(color=SLATE, label="Reported fee or assumed range (not a model number)"),
                       Patch(color=NAVY, label="Model number (ticks: designs)"),
                       Patch(facecolor=STEEL, hatch="////", edgecolor="white", label="Liquidity product, not credit cover")],
              loc="lower left", bbox_to_anchor=(0.06, 0.065), bbox_transform=fig.transFigure, ncol=3, frameon=False,
              fontsize=8)
    frame(fig, "One price list for the large uninsured deposit",
          "Nine routes for a $100m corporate balance above the insured limit; R1 shows held (left) and bought (right) "
          "securities.\nR5 and R6 ticks are designs; R7 and R9 make a fifth of the balance movable on weekends and cover no "
          "failure.",
          f"{SRC} Fee sources: FHLBank schedules 2022 to 2026; Chain Bridge Bancorp 2026. {ILL}")
    save(fig, 2)

    # ---- U03: cost vs lendable share, all nine routes ------------------------------------------------------------
    u3_y = {"R1": 0.0, "R2": 1.06, "R3": 1.025, "R4": 0.035, "R5": 1.0, "R6": R6_LEND, "R7": R7_LEND, "R8": R8_LEND,
            "R9": R9_LEND + 0.035}                          # offset above R7 for legibility (same lendable share)
    u3_lab = {"R1": ((20, 0.13), "R1 pledged securities, held"), "R2": ((7.6, 1.2), "R2 FHLB letter of credit"),
              "R3": ((24, 1.2), "R3 reciprocal placement"), "R4": ((70, 0.15), "R4 let it go (replacement spread)"),
              "R5": ((62, 1.12), "R5 funded vehicle (designs)"), "R6": ((60, 0.93), "R6 mutual with a tail (designs)"),
              "R7": ((60, 0.84), "R7 always-on facility (liquidity only)"), "R8": ((80, 0.72), "R8 one ledger, two tranches"),
              "R9": ((6.2, 0.70), "R9 joint-account prefunding (liquidity only)")}
    fig, ax = plt.subplots(figsize=(11, 6.4))
    fig.subplots_adjust(left=0.09, right=0.96, top=0.8, bottom=0.15)
    for rt in ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9"]:
        vs = [v for v in VARIANTS if v["route"] == rt]
        y = u3_y[rt]
        bas = vs[0]["basis"]
        col = BAS_COL["model"] if bas.startswith("model") else BAS_COL["illustrative"] if "illustrative" in bas else BAS_COL["reported"]
        spans = [(v["lo"], v["hi"]) for v in vs] if rt == "R1" else [(min(v["lo"] for v in vs), max(v["hi"] for v in vs))]
        for lo, hi in spans:
            ax.barh(y, max(hi - lo, hi * 0.03) / BP, left=lo / BP, height=0.028, color=col,
                    hatch="////" if rt in ("R7", "R9") else None, edgecolor="white" if rt in ("R7", "R9") else None, lw=0,
                    alpha=0.35 if (rt == "R1" and lo >= R1_BOUGHT[0] - 1e-12) else 0.9)
        for v in vs:
            ax.plot(v["base"] / BP, y, marker="o", ms=7.5, color=NAVY if bas.startswith("model") else col, mec="white",
                    mew=1.1, zorder=3)
        (tx, ty), lab = u3_lab[rt]
        ax.annotate(lab, xy=(vs[0]["base"] / BP, y), xytext=(tx, ty), fontsize=8.2, color=INK, va="center",
                    arrowprops=dict(arrowstyle="-", color=SLATE, lw=0.6))
    ax.annotate("R1 bought for the purpose", xy=(VBY["R1 bought"]["base"] / BP, 0.0), xytext=(160, -0.14), fontsize=8.2,
                color=MUTED, va="center", arrowprops=dict(arrowstyle="-", color=SLATE, lw=0.6))
    ax.axhline(S2_MIN, color=ACCENT, lw=1.0, ls=(0, (4, 2)))
    ax.text(510, S2_MIN - 0.025, f"S2: lendable share {S2_MIN:g}", ha="right", va="top", fontsize=8.2, color=DARKACC)
    ax.set_xscale("log")
    ax.set_xlim(5, 900)
    ax.set_xticks([5, 10, 20, 50, 100, 200, 500])
    ax.set_xticklabels(["5", "10", "20", "50", "100", "200", "500"])
    ax.set_ylim(-0.25, 1.3)
    ax.set_yticks([0, 0.5, 0.77, 0.8, 0.97, 1.0])
    ax.set_yticklabels(["0", "0.5", "", "0.80", "", "1.0"])
    ax.set_xlabel("bps a year on the $100m balance (log scale; bar = range, marker = base price of each design)",
                  fontsize=9.5, color=MUTED)
    ax.set_ylabel("Lendable share of each deposit dollar", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(handles=[Patch(color=SLATE, label="Reported fee or assumed range (not a model number)"),
                       Patch(color=NAVY, label="Model number"),
                       Patch(facecolor=STEEL, hatch="////", edgecolor="white", label="Liquidity product, not credit cover")],
              loc="center left", bbox_to_anchor=(0.0, 0.42), frameon=False, fontsize=8)
    frame(fig, "Cost against the share of the deposit that still funds loans",
          "All nine routes on the price-list axis. Prices from the results file, Section 4; lendable shares from "
          "Section 5.\nR2 and R3 are offset slightly above 1, R4 slightly above 0 and R9 (0.80, as R7) above R7 for legibility; "
          "R6, R7 and R8 sit at their computed shares.",
          f"{SRC} Results file Sections 4 and 5 (fee sources as named there). {ILL}")
    save(fig, 3)

    # ---- U04: who bears the risk ------------------------------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(11, 6.0), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.8, bottom=0.25, wspace=0.08)
    for ax, m in zip(axs, ("Q", "P")):
        for i, (rt, key) in enumerate(BEAR_FIG):
            y = len(BEAR_FIG) - 1 - i
            left = 0.0
            for b in BEARERS:
                val = BEAR[(key, m)][b] / BP
                if val <= 0:
                    continue
                ax.barh(y, val, left=left, height=0.55, color=BCOL[b],
                        hatch="////" if b == "Leaves with the balance" else None, edgecolor="white", lw=0.5)
                left += val
        ax.set_title(f"Under {m}" + (" (pricing, mu 3)" if m == "Q" else " (real world)"), fontsize=10, loc="left")
        ax.set_xlabel("bps a year on the balance", fontsize=9, color=MUTED)
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axs[0].set_yticks(range(len(BEAR_FIG)))
    axs[0].set_yticklabels([rt for rt, _ in reversed(BEAR_FIG)])
    fig.legend(handles=[Patch(facecolor=BCOL[b], hatch="////" if b == "Leaves with the balance" else None,
                              edgecolor="white", label=b) for b in BEARERS],
               loc="lower left", bbox_to_anchor=(0.06, 0.075), ncol=4, frameon=False, fontsize=8)
    frame(fig, "Who bears the risk the balance carries",
          "The self-insured cost (credit + access) by route and bearer. R2 and R7 move it without pricing it; R3 prices it "
          "publicly;\nR5 and R6 pay private capital for it; R4 sends the balance away and pays the replacement spread instead.",
          f"{SRC} Attributions are the author's reading. R5 = pooled reference design; R8's credit tranche = R6. {ILL}")
    save(fig, 4)

    # ---- U05: screens grid ------------------------------------------------------------------------------------
    gk = ["R1 held", "R2", "R3", "R4", "R5 single", "R5 pooled", "R5 sized", "R6", "R6 alt", "R7", "R8", "R9"]
    scol = {"pass": NAVY, "fail": ACCENT, "open": MIST, "n/a": "#F6F6F4"}
    tcol = {"pass": "white", "fail": "white", "open": INK, "n/a": MUTED}
    fig, ax = plt.subplots(figsize=(10, 6.6))
    fig.subplots_adjust(left=0.13, right=0.97, top=0.8, bottom=0.14)
    for i, k in enumerate(gk):
        for j, (s, _) in enumerate(SCREENS):
            vd = VBY[k]["screens"][s][0]
            ax.add_patch(plt.Rectangle((j, len(gk) - 1 - i), 0.94, 0.88, color=scol[vd], hatch="///" if vd == "open" else None))
            ax.text(j + 0.47, len(gk) - 1 - i + 0.44, vd, ha="center", va="center", fontsize=9, color=tcol[vd])
    ax.set_xlim(-0.05, len(SCREENS))
    ax.set_ylim(-0.1, len(gk))
    ax.set_xticks([j + 0.47 for j in range(len(SCREENS))])
    ax.set_xticklabels(["S1 open to a\nprivate corporate", f"S2 lendable\n>= {S2_MIN:g}", "S3 continues and\ngrows when weak",
                        "S4 no hidden\npublic subsidy", "S5 99% paid when\nown bank fails"], fontsize=8.5)
    ax.xaxis.tick_top()
    ax.set_yticks([len(gk) - 1 - i + 0.44 for i in range(len(gk))])
    ax.set_yticklabels(gk, fontsize=9)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    frame(fig, "The screens",
          "Pass, fail, open (a question the sources do not settle) or n/a, by route and design. An open verdict is not a "
          "pass under the rule.",
          f"Source: author's reading of the sources named in the results file, Section 8; S5 computed. {ILL}")
    save(fig, 5)

    # ---- U06: champion's layer stack ----------------------------------------------------------------------------
    champs = [(CHAMP_STRICT, "Strict champion"), (CHAMP_OPEN, "Open items resolved")]
    GAP = 1.7
    champs = [(c, t) for c, t in champs if c is not None]
    if len(champs) == 2 and champs[0][0]["key"] == champs[1][0]["key"]:
        champs = [(champs[0][0], "Champion, both readings")]
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(11, 5.8), gridspec_kw=dict(width_ratios=[1, 1]))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.78, bottom=0.17, wspace=0.25)
    for i, (c, title) in enumerate(champs):
        if c["route"] == "R6":
            d = R6["ref"] if c["key"] == "R6" else R6["alt"]
            layers = [("Reserve (paid-in bills)", 0.0, d["theta"], SAGE), ("Special assessment", d["theta"], d["A"], "#A9C2B1"),
                      ("Tail (Treasury-backed)", d["A"], d["X"], NAVY)]
            top = d["X"]
            parts = [("Mutual: loss + access (P)", d["el_mut"] + d["acc_mut"], SAGE),
                     ("Mutual: reserve carry", d["carry"], "#A9C2B1"), ("Mutual: frictions", d["f_m"], MIST),
                     ("Tail: loss + access (Q)", d["el_tail"] + d["acc_tail"], NAVY),
                     ("Tail: lock-up, frictions, advance carry", d["lock"] + d["f_tail"] + d["adv_carry"], STEEL)]
        elif c["route"] == "R5" and c["key"] != "R5 single":
            th = K_STD / cc.V5_N if c["key"] == "R5 sized" else cc.V8_REF["theta"]
            pr = R5_STD if c["key"] == "R5 sized" else R5_REF
            layers = [("Funded buffer (bills)", 0.0, th, NAVY)]
            top = th
            parts = [("Credit (Q)", pr["credit"], NAVY), ("Access (Q)", pr["access"], STEEL), ("Lock-up", pr["lock"], SLATE),
                     ("Frictions", pr["f"], MIST)]
        else:
            layers = [("Funded collateral", 0.0, 1.0, NAVY)]
            top = 1.0
            parts = [("Credit (Q)", R5_SINGLE["credit"], NAVY), ("Access (Q)", R5_SINGLE["access"], STEEL),
                     ("Capacity", R5_SINGLE["capacity"], SLATE), ("Frictions", R5_SINGLE["frictions"], MIST)]
        xi = i * GAP
        last = -9.0
        for nm, a0, a1, col in layers:
            axl.bar(xi, (a1 - a0) * 100, 0.45, bottom=a0 * 100, color=col, edgecolor="white")
            yl = max((a0 + a1) / 2 * 100, last + 2.2)
            last = yl
            axl.text(xi + 0.26, yl, f"{nm}: {pcs(a0, 2)} to {pcs(a1, 2)}", fontsize=7.6, va="center", ha="left", color=MUTED)
        axl.bar(xi, max(1.0, top * 100 * 0.25), 0.45, bottom=top * 100, color="white", edgecolor=MIST, hatch="..")
        axl.text(xi + 0.26, max(top * 100 * 1.08, last + 2.2), "Above: unprotected", fontsize=7.6, va="bottom", color=MUTED)
        y0, last = 0.0, -9.0
        for nm, val, col in parts:
            axr.bar(xi, val / BP, 0.45, bottom=y0, color=col, edgecolor="white")
            if val / BP > 0.9:
                yl = max(y0 + val / BP / 2, last + 1.6)
                last = yl
                axr.text(xi + 0.26, yl, f"{nm} {b2(val)}", fontsize=7.6, va="center", ha="left", color=MUTED)
            y0 += val / BP
        axr.text(xi, y0 + 0.5, f"{c['key']}: {b2(c['base'])}", ha="center", va="bottom", fontsize=9, fontweight="semibold")
    for ax in (axl, axr):
        ax.set_xticks([i * GAP for i in range(len(champs))])
        ax.set_xticklabels([f"{t}\n{c['key']}" for c, t in champs], fontsize=8.3)
        ax.set_xlim(-0.4, (len(champs) - 1) * GAP + 1.5)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axl.set_ylabel("Cash capacity at the trigger, % of covered balance", fontsize=9, color=MUTED)
    axr.set_ylabel("bps a year on the covered balance", fontsize=9, color=MUTED)
    frame(fig, "The champion's layer stack and what each layer costs",
          "Left: where each layer attaches and exhausts. Right: the price by component. The rule's strict champion and the\n"
          "champion when every open screen resolves in the route's favor are both shown.",
          f"{SRC} R5 from the clearing-cost engine, R6 from the mutual engine. {ILL}")
    save(fig, 6)

    # ---- U07: reliability Gaussian vs t(5) ----------------------------------------------------------------------
    rows = [r for r in REL_ROWS if r[0] != "R5 tstd"]
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.8, bottom=0.24)
    FLOOR = 1e-4
    x = np.arange(len(rows))
    for j, (cop, col, lab) in enumerate((("g", NAVY, "Gaussian copula"), ("t", ACCENT, "Student-t(5) copula"))):
        vals = [max(r[2] if cop == "g" else r[3], FLOOR) * 100 for r in rows]
        ax.bar(x + (j - 0.5) * 0.36, vals, 0.34, color=col, label=lab)
        for xi, r in zip(x, rows):
            v = r[2] if cop == "g" else r[3]
            ax.text(xi + (j - 0.5) * 0.36, max(v, FLOOR) * 100 * 1.15, "0" if v == 0 else (f"{v * 100:.2f}%" if v >= 1e-3 else
                    f"{v * 100:.3f}%"), ha="center", va="bottom", fontsize=7.3, color=MUTED)
    ax.axhline(S5_STD * 100, color=INK, lw=0.9, ls=(0, (4, 2)))
    ax.text(-0.45, S5_STD * 100 * 1.12, "S5 standard: 1%", ha="left", va="bottom", fontsize=8.3, color=INK)
    ax.set_yscale("log")
    ax.set_ylim(FLOOR * 100 * 0.8, 100)
    ax.set_yticks([0.01, 0.1, 1, 10, 100])
    ax.set_yticklabels(["0.01%", "0.1%", "1%", "10%", "100%"])
    ax.set_xticks(x)
    ax.set_xticklabels([r[1].replace(" (", "\n(") for r in rows], fontsize=8)
    ax.set_ylabel("P(not paid in full given own bank fails), rho 0.30", fontsize=9, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    frame(fig, "What the Gaussian standard hides",
          "Probability that the depositor is not paid in full in the year its own bank fails, same design under two "
          "copulas.\nThe single-name vehicle is fully funded and never short (shown at the floor).",
          f"{SRC} Clearing-cost engine (R5) and mutual engine (R6, R8); state-dependent LGD. {ILL}")
    save(fig, 7)

    # ---- U08: the weekend window ----------------------------------------------------------------------------------
    hrs = np.linspace(0, 50, 501)
    rng = np.random.default_rng(R7_PATH_SEED)
    noise = np.cumsum(rng.normal(0.0, 0.18, hrs.size)) * 0.12
    base_path = 26.0 * (1 - np.exp(-hrs / 22.0)) / (1 - np.exp(-50 / 22.0))
    nd = np.maximum.accumulate(np.clip(base_path + noise - noise[0], 0, None))
    cap = R7_SHARE * 100
    secured = np.minimum(nd, cap)
    queued = np.clip(nd - cap, 0, None)
    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.subplots_adjust(left=0.08, right=0.78, top=0.8, bottom=0.24)
    ax.fill_between(hrs, 0, secured, color=NAVY, alpha=0.85, lw=0, label="Net debit, secured by bills in repo")
    ax.fill_between(hrs, cap, cap + queued, color=ACCENT, alpha=0.85, lw=0, hatch="////",
                    label="Transfers queued past the cap")
    ax.plot(hrs, secured / (1 - R7_HAIRCUT), color=STEEL, lw=1.6, ls=(0, (3, 1.5)),
            label=f"Bills moved into repo (debit / (1 - {R7_HAIRCUT:.0%} haircut))")
    ax.axhline(cap, color=INK, lw=1.0)
    ax.text(29.5, cap + 0.75, f"Cap: lesser of pledged bills after haircut\nand the {R7_SHARE:.0%} disclosed share",
            fontsize=8.3, va="bottom", color=INK)
    ax.axhline(R7_BILLS * 100, color=SLATE, lw=0.8, ls=(0, (1, 1.5)))
    ax.text(0.5, R7_BILLS * 100 + 0.35, f"Bills positioned before Friday's close: {pcs(R7_BILLS, 1)}", fontsize=7.8,
            color=MUTED, va="bottom")
    ax.axvline(50, color=DARKACC, lw=1.4)
    ax.text(50.4, 29.5, "Sun 21:00 Fedwire opens:\nnet debits settle in\nreserves or collateralized\ndaylight credit; queue\nreleased; bills repoed\nor sold Monday",
            ha="left", fontsize=8.0, color=DARKACC, va="top")
    ax.set_xticks([0, 5, 17, 29, 41, 50])
    ax.set_xticklabels(["Fri 19:00", "Sat 00:00", "Sat 12:00", "Sun 00:00", "Sun 12:00", "Sun 21:00"], fontsize=8.5)
    ax.set_xlim(0, 50.2)
    ax.set_ylim(0, 30)
    ax.set_ylabel("% of the member's tokenized balance", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="lower left", bbox_to_anchor=(0.06, 0.075), bbox_transform=fig.transFigure, ncol=3, frameon=False,
              fontsize=8)
    fig.text(0.80, 0.52, "If the member is closed\nduring the window, net\ncreditors hold perfected\nbills and may not "
             "terminate\nbefore 17:00 on the next\nbusiness day (12 U.S.C.\n1821(e)(10)).", fontsize=7.8, color=MUTED,
             va="top")
    frame(fig, "The weekend window and the netting facility",
          "One member's net debit to the other members from Friday's Fedwire close to Sunday's opening: secured by bills "
          "up to the cap,\nqueued above it, settled in central bank money when Fedwire opens.",
          f"Source: author's construction; the path is illustrative (seed {R7_PATH_SEED}), not an estimate. {ILL}")
    save(fig, 8)

    # ---- U09: dollars by bank -------------------------------------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(11, 6.2), sharey=True)
    fig.subplots_adjust(left=0.13, right=0.97, top=0.8, bottom=0.15, wspace=0.08)
    keys = [v["key"] for v in VARIANTS]
    for ax, r in zip(axs, BANK_ROWS):
        for i, k in enumerate(keys):
            y = len(keys) - 1 - i
            lo, bs, hi = (c / 1e6 for c in r["cost"][k])
            v = VBY[k]
            col = NAVY if v["basis"].startswith("model") else STEEL if "illustrative" in v["basis"] else SLATE
            if hi > lo * 1.0001:
                ax.barh(y, hi - lo, left=lo, height=0.5, color=col, hatch="////" if k in ("R7", "R9") else None, edgecolor="white",
                        lw=0)
            ax.plot(bs, y, marker="|", ms=12, mew=2, color=ACCENT)
        ax.set_xscale("log")
        ax.set_title(f"{r['name']}: covered excess ${r['cov'] / 1e9:.1f}bn".replace("$", "\\$"), fontsize=10, loc="left")
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.set_xlabel("$ million a year (log scale)", fontsize=9, color=MUTED)
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axs[0].set_yticks(range(len(keys)))
    axs[0].set_yticklabels(list(reversed(keys)), fontsize=8.5)
    frame(fig, "What each route costs a year in dollars",
          "Covered excess = 20% of liabilities (liabilities 90% of assets). Bars are ranges, ticks the base. R7 and R9 "
          "are hatched: liquidity products.",
          f"{SRC} Reported fees and assumed ranges as in the price list. {ILL}")
    save(fig, 9)

    # ---- U10: tornado on the champion ------------------------------------------------------------------------------
    rts = [rt for rt in ("R5", "R6") if rt in TORNADO]
    ttl = {}
    for rt in rts:
        tags = []
        if CHAMP_STRICT is not None and CHAMP_STRICT["route"] == rt:
            tags.append("strict champion")
        if CHAMP_OPEN is not None and CHAMP_OPEN["route"] == rt:
            tags.append("champion with open items resolved")
        ttl[rt] = f"{rt}: {', '.join(tags)}"
    fig, axs = plt.subplots(1, len(rts), figsize=(11, 5.8), squeeze=False)
    axs = axs[0]
    fig.subplots_adjust(left=0.17, right=0.97, top=0.8, bottom=0.15, wspace=0.62)
    for ax, rt in zip(axs, rts):
        base_pi = SENS_BASE[rt]["pi"] / BP
        items = TORNADO[rt]
        for i, (lab, (lo, hi)) in enumerate(items):
            ax.barh(i, max((hi - lo) / BP, 0.05), left=lo / BP, height=0.55, color=NAVY if rt == "R6" else STEEL)
            ax.text(hi / BP + 0.4, i, f"{lo / BP:.1f} to {hi / BP:.1f}", va="center", fontsize=7.8, color=MUTED)
        ax.axvline(base_pi, color=ACCENT, lw=1.1, ls=(0, (4, 2)))
        ax.set_yticks(range(len(items)))
        ax.set_yticklabels([lab for lab, _ in items], fontsize=8.5)
        ax.set_title(ttl[rt], fontsize=9.5, loc="left")
        ax.set_xlabel("All-in price, bps a year (capacity re-sized to S5 each time)", fontsize=8.5, color=MUTED)
        ax.xaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        xl = ax.get_xlim()
        ax.set_xlim(xl[0], xl[1] + (xl[1] - xl[0]) * 0.18)
    frame(fig, "What moves the champion's price",
          "One input at a time over the ranges in the results file; dashed line = base. Capacity is re-sized to the\n"
          "Gaussian 1% standard in each case, so the price includes the cost of staying at the standard.",
          f"{SRC} {ILL}")
    save(fig, 10)


# =============================================================================
# 12. RUN
# =============================================================================
if __name__ == "__main__":
    FIGURES.mkdir(parents=True, exist_ok=True)
    make_figures()
    write_results()
    print(f"Parity with the imported engines: {'PASS' if PARITY_OK else 'FAIL'}; method checks "
          f"{'PASS' if METHOD_OK else 'FAIL'}")
    print(f"S2 bar {S2_MIN:g}" + (" (rule of record)" if S2_DEFAULT_RUN else " (sensitivity run, not the rule of record)")
          + ("" if S2_SENS_SELF is None else f"; Section 9b reproduces Section 9: {'yes' if S2_SENS_SELF else 'NO'}"))
    for p, pn in PROBLEMS:
        for l in (False, True):
            r = RULE[(p, l)]
            print(f"{pn} [{'open resolved' if l else 'strict'}]: champion {describe(r['champion'])}; "
                  f"challenger {describe(r['challenger'])}")
    print(f"Wrote {RESULTS_MD}")
    for n in range(1, N_FIGS + 1):
        print(f"Wrote {FIG(n)}")
    print(f"Run time {time.perf_counter() - _T_START:.1f} s")
