"""
clearing_cost.py: the clearing cost of an uninsured deposit, numerical core and figures
(Cash That Never Sleeps, Chapter 3).

What it does
    Prices one year of protection on a covered uninsured operating balance N
    (a purchase commitment, standby letter of credit or guarantee that pays par
    when the depository bank fails) and reads that price as the clearing cost of
    holding the balance uninsured. Produces every number Chapter 3 quotes,
    writes them to a markdown results file, and renders figures 01 to 11.

    Part I (Sections 1 to 15): the single-name pricing formula, provider types,
    sensitivities, tranche economics, a diversified portfolio and recovery-gap
    financing. Part II (Sections 16 to 29): a partially funded multi-bank pooled
    vehicle (funded buffer plus committed liquidity facility), its cash needs,
    failure probabilities, pricing, stress scenarios and challenge register.
    Part III (Sections 30 to 34): why private capital would write the protection,
    and what technology changes. Part IV (Sections 35 to 43, new in v8): the
    all-funded reference design, the buffer-versus-facility rule, reliability
    given the depositor's own bank fails, Year-2 reliability and reinstatement,
    the three-party clearing condition and an exact cash-flow check.
    Parts I to III use the model v7 code; v8 re-runs them at a risk-free rate of
    4.3% (v7: 3.9%), and Section 35.0 of the results compares the headline values.

Formula, all rates annual, per unit of N:

    c* = lambda_Q * LGD_dep                                         credit
       + lambda_Q * max(0, 1 - a - LGD_dep) * (r + s_b) * D         access
       + k                                                          standing capacity
       + f                                                          frictions
    lambda_Q = mu * lambda_P

    Self-insured cost (the depositor's own cost of bearing the risk) = credit + access.
    Price of buying protection = c*. The gap is the transfer cost k + f.

    Seller wrong-way risk is NOT priced into c*. It reduces the value of the
    protection to the depositor:
        haircut = lambda_Q * P(seller fails | reference fails) * LGD_dep * LGD_seller

    Bank SBLC seller:
        Q price      = c* as above
        full P price = EL_P + P-access + capital cost + k + f    (mu = 1, no risk premium)
        capital cost = CCF * RW * CET1 ratio * (hurdle - r)      (capital is invested at r)
        P floor      = EL_P + capital cost
        bank c*      = max(Q price, full P price)
    Never add a risk-neutral premium and a capital charge together.

Pooled vehicle: 50 reference banks, each 2% of covered notional, one-factor Gaussian
    copula (Student-t(5) as the fat-tail check). Liabilities: funded buffer theta
    (T-bills; first loss, then term bridge) plus an optional committed short-term
    liquidity facility F that funds the gap between paying par at T+0 and receiving
    the advance dividend about 7 days later.
        k_pool  = theta * s_lock + F * fee_F + expected drawn cost
        c*_pool = credit_Q + access_Q + k_pool + f
    credit_Q and access_Q are expectations under Q: the copula is run with the per-name
    default probability mu * lambda_P (same rho, same LGD mapping). With a fixed LGD this
    reproduces the single-name credit and access terms exactly. Protection-failure and
    vehicle-default probabilities are real-world (P) quantities.
    Reference design (v8): all-funded, theta 20%, F 0 (capacity for 10 simultaneous
    failures). The 10/10 hybrid (theta 10%, F 10% at a 20 bps fee) is a variant.

Inputs   Parameters in the blocks below (each defined once). Empirical figures for
         fig-01 come only from public sources (FDIC staff study, Chu et al., May 2026;
         see the manual's references). Every other parameter is an author assumption,
         illustrative and not calibrated, unless a public rule is cited next to it.
Outputs  model/results_clearing_cost.md (beside this script)
         figures/clearing_cost/fig-NN.png at the repository root (NN = 01 to 11; the folder is created if absent)
Run      python3 -I model/clearing_cost.py
         (from the repository root, or from the model folder with the file name only; paths are
         resolved from this script's own location)
Seeds    20261017 (portfolio Monte Carlo, Part I), 20261018 and 20261019 (pool Monte Carlo
         check, Part II). Everything else is exact quadrature, so the output is deterministic.

Assumptions not fixed by a public source are marked [author assumption] (illustrative)
and listed in the results file under "Assumptions and decisions" (Section 15) and the
challenge registers (Sections 28 and 36).

History. v2: capital cost net of r; bank c* = max(Q, full P). v3: private-capital
sections. v5: pooled vehicle (Part II). v7: Part III. v8: release clean-up (neutral
provenance labels; a replication of a third-party draft removed), Part IV added, figures
10 and 11 added; risk-free rate updated to 4.3% (as of 15 October 2026).
"""

import sys
import time
from pathlib import Path

_T_START = time.perf_counter()

# =============================================================================
# 1. PARAMETERS (each defined once; rates as decimals, 1 bp = 0.0001)
# =============================================================================
BP = 1e-4

# --- Base case (author assumptions, illustrative) -------------------------------------------------------
LAMBDA_P = 0.0025      # physical (P-measure) annual default intensity of the depository bank
MU = 3.0               # risk-premium multiplier, lambda_Q = MU * LAMBDA_P
LGD_DEP = 0.25         # ultimate loss on a domestic deposit claim under depositor preference
ADV_DIV = 0.50         # a: advance-dividend fraction paid within days of failure
D_YEARS = 2.0          # D: expected years from failure to final receivership dividends
R_FREE = 0.043         # r: 3-month Treasury bill, FRED DGS3MO 4.28% on 15 Oct 2026, rounded (as of 15 October 2026;
                       # verify before relying on it). Model v7 used 3.9%; see Section 35.0 of the results.
R_FREE_V7 = 0.039      # model v7 value, kept only for the v7-versus-v8 comparison table
S_B = 0.010            # s_b: provider funding spread over r
F_BASE = 15 * BP       # f: operations, legal, structuring, margin (base)

# --- Provider: funded investor vehicle (collateral in T-bills) ---------------
FUND_K = 10 * BP                    # liquidity premium for locked funds, base (midpoint)
FUND_K_RANGE = (5 * BP, 15 * BP)    # author assumption (range)
FUND_F = F_BASE                     # base
FUND_F_RANGE = (10 * BP, 20 * BP)   # author assumption (fixed costs make small programs dearer)
FUND_P_SELLER = 0.0                 # fully collateralized, bankruptcy remote: no wrong-way exposure [author assumption]
FUND_LGD_SELLER = 0.0

# --- Provider: bank SBLC seller ----------------------------------------------
HQLA_CARRY = 40 * BP                # net carry cost of holding HQLA against the commitment (author assumption)
LCR_OUTFLOW = 0.30                  # base: 30% (liquidity-facility rate, non-financial corporate; 12 CFR 249.32(e), on my reading)
LCR_OUTFLOW_RANGE = (0.0, 0.30)     # range (on my reading of 12 CFR 249.32(e))
LCR_OUTFLOW_STRESS = 1.00           # internal stress assumption (not the regulatory rate), shown alongside
BANK_F = F_BASE
CCF = 1.00                          # 12 CFR 217.33(b)(4): guarantee / financial SBLC
RW = 0.20                           # 12 CFR 217.32(d): exposure to a US depository institution
CET1_RATIO = 0.135                  # capital ratio incl. buffers (author assumption)
HURDLE = 0.10                       # pre-tax hurdle rate on capital (author assumption); charged in excess of r
BANK_P_SELLER = 0.05                # P(seller bank fails | reference fails), illustrative [author assumption]
BANK_LGD_SELLER = 0.60              # illustrative: SBLC claim on a failed issuer is a general creditor claim [author assumption]

# --- Provider: regional mutual pool ------------------------------------------
POOL_RESERVE = 0.10                 # prefunded reserve as a fraction of covered balances [author assumption]
POOL_RESERVE_RANGE = (0.05, 0.20)   # [author assumption]
POOL_RESERVE_OPP = 100 * BP         # members' opportunity cost of funds parked in the reserve, over T-bills [author assumption]
POOL_F = F_BASE
POOL_P_SELLER = 0.40                # base, range 30% to 50% (author assumption)
POOL_P_SELLER_RANGE = (0.30, 0.50)
POOL_LGD_SELLER = 0.50              # share of the pool's obligation unpaid if the pool fails, illustrative [author assumption]

# --- Sensitivity sets (author assumptions) ------------------------------------------------
LAMBDA_P_SET = [0.0010, 0.0025, 0.0050, 0.0100, 0.0200]
LGD_SET = [0.15, 0.25, 0.40]
MU_SET = [2, 3, 4, 5]
ADV_SET = [0.0, 0.50]
D_SET = [1, 2, 3]

# --- Market-implied cross-check (hypothetical round-number senior spreads) ---
SENIOR_SPREADS = [60 * BP, 100 * BP, 150 * BP, 250 * BP]
SENIOR_LGD = 0.60

# --- Depositor yield advantage over a government MMF -------------------------
DELTA_SET = [-50 * BP, 0, 25 * BP, 50 * BP, 100 * BP]
DELTA_BAND = (0, 50 * BP)           # plausible band shaded in fig-04

# --- Wedge ---------------------------------------------------------------------
WEDGE_N = 1_000_000_000             # $1 billion covered, full exercise

# --- v3 A: single-bank funded vehicle, tranche economics ----------------------
FL_THICKNESS = LGD_DEP              # first-loss tranche thickness = base LGD_dep (design choice)
FL_THICKNESS_STRESS = 0.40          # alternative: thickness sized at the stressed LGD [author assumption]
TRANCHE_LP_SET = [0.0010, 0.0025, 0.0050, 0.0100]

# --- v3 B: diversified portfolio, one-factor Gaussian copula (Vasicek) ---------
PORT_N = 50                         # equal exposures, one per bank
PORT_RHO_SET = [0.0, 0.10, 0.20, 0.30]   # 0 = independence, shown as a reference [author assumption]
PORT_LGD_STOCH = (0.15, 0.40)       # optional variant: LGD uniform 15% to 40%, iid across failures
# Tranche points [author assumption]: one failure at LGD 25% costs 0.5% of the portfolio, so 0-1% absorbs two failures,
# 1-3% the third to sixth, 3%+ a seventh or more. 0-3/3-7/7-100 shown as an alternative.
PORT_TRANCHES = [("Equity", 0.0, 0.01), ("Mezzanine", 0.01, 0.03), ("Senior", 0.03, 1.0)]
PORT_TRANCHES_ALT = [("Equity", 0.0, 0.03), ("Mezzanine", 0.03, 0.07), ("Senior", 0.07, 1.0)]
CLUSTER_N = 3                       # "2023-like" cluster: 3 or more failures in a year
MC_PATHS = 400_000
MC_SEED = 20261017
Z_GRID = 4001                       # quadrature points over the common factor, z in [-8, 8]

# --- v3 C: recovery-gap financing ----------------------------------------------
GAP_PRICE_SET = [0.80, 0.90, 0.95]  # price as a fraction of the expected remaining recovery
GAP_D_SET = [1, 2, 3]
GAP_STRESS_LGD = 0.40               # realized LGD when the claim was priced at LGD_dep 25%

# --- Paths ----------------------------------------------------------------------
HERE = Path(__file__).resolve().parent              # model/
ROOT = HERE.parent                                   # repository root
SCRIPT_NAME = "clearing_cost.py"
RESULTS_MD = HERE / "results_clearing_cost.md"
FIGURES = ROOT / "figures" / "clearing_cost"         # created at run time if absent (importing writes nothing)
FIG = lambda n: FIGURES / f"fig-{n:02d}.png"


# =============================================================================
# 2. MODEL
# =============================================================================
def lambda_q(lambda_p=LAMBDA_P, mu=MU):
    """Risk-neutral default intensity."""
    return mu * lambda_p


def components(lambda_p=LAMBDA_P, mu=MU, lgd=LGD_DEP, a=ADV_DIV, d=D_YEARS,
               r=R_FREE, s_b=S_B, k=FUND_K, f=F_BASE):
    """Return the four clearing-cost components and c* (all per unit of N per year)."""
    lq = lambda_q(lambda_p, mu)
    credit = lq * lgd
    bridged = max(0.0, 1.0 - a - lgd)          # recoverable but not yet paid at the advance dividend
    access = lq * bridged * (r + s_b) * d
    return {"credit": credit, "access": access, "capacity": k, "frictions": f, "capital": 0.0,
            "c_star": credit + access + k + f}


def self_insured(**kw):
    """Depositor's own cost of bearing the risk: credit + access, no transfer cost."""
    c = components(k=0.0, f=0.0, **kw)
    return c["credit"] + c["access"]


def wrong_way_haircut(p_seller, lgd_seller, lambda_p=LAMBDA_P, mu=MU, lgd=LGD_DEP):
    """Reduction in protection value to the depositor from seller wrong-way risk."""
    return lambda_q(lambda_p, mu) * p_seller * lgd * lgd_seller


def bank_k(outflow=LCR_OUTFLOW):
    return outflow * HQLA_CARRY


def pool_k(reserve=POOL_RESERVE):
    return reserve * POOL_RESERVE_OPP


CAPITAL_COST = CCF * RW * CET1_RATIO * (HURDLE - R_FREE)     # base: hurdle in excess of r
CAPITAL_COST_GROSS = CCF * RW * CET1_RATIO * HURDLE          # memo only: v1 specification (gross hurdle)


def bank_p_floor(lambda_p=LAMBDA_P, lgd=LGD_DEP, capital=CAPITAL_COST):
    """P-measure floor: EL_P + capital cost."""
    return lambda_p * lgd + capital


def bank_p_components(lambda_p=LAMBDA_P, lgd=LGD_DEP, k=None, f=BANK_F, capital=CAPITAL_COST):
    """Full P-measure price: EL_P + P-access + capital + k + f (mu = 1, no risk premium)."""
    k = bank_k() if k is None else k
    c = components(lambda_p=lambda_p, mu=1.0, lgd=lgd, k=k, f=f)
    c["capital"] = capital
    c["c_star"] += capital
    return c


def bank_prices(lambda_p=LAMBDA_P, lgd=LGD_DEP, k=None, f=BANK_F, capital=CAPITAL_COST):
    """Bank seller: Q price, full P price, and all-in c* = max of the two."""
    k = bank_k() if k is None else k
    q = components(lambda_p=lambda_p, lgd=lgd, k=k, f=f)
    p = bank_p_components(lambda_p=lambda_p, lgd=lgd, k=k, f=f, capital=capital)
    binding = "P" if p["c_star"] > q["c_star"] else "Q"
    return {"q": q, "p": p, "all_in": max(q["c_star"], p["c_star"]), "binding": binding}


def provider_c_star(name, lambda_p=LAMBDA_P, lgd=LGD_DEP):
    p = PROVIDERS[name]
    if name == "Bank SBLC seller":
        return bank_prices(lambda_p=lambda_p, lgd=lgd, k=p["k"], f=p["f"])["all_in"]
    return components(lambda_p=lambda_p, lgd=lgd, k=p["k"], f=p["f"])["c_star"]


PROVIDERS = {
    "Funded investor vehicle": dict(k=FUND_K, f=FUND_F, p=FUND_P_SELLER, lgd_s=FUND_LGD_SELLER,
                                    k_lo=FUND_K_RANGE[0], k_hi=FUND_K_RANGE[1],
                                    f_lo=FUND_F_RANGE[0], f_hi=FUND_F_RANGE[1]),
    "Bank SBLC seller": dict(k=bank_k(), f=BANK_F, p=BANK_P_SELLER, lgd_s=BANK_LGD_SELLER,
                             k_lo=bank_k(LCR_OUTFLOW_RANGE[0]), k_hi=bank_k(LCR_OUTFLOW_RANGE[1]),
                             f_lo=BANK_F, f_hi=BANK_F),
    "Regional mutual pool": dict(k=pool_k(), f=POOL_F, p=POOL_P_SELLER, lgd_s=POOL_LGD_SELLER,
                                 k_lo=pool_k(POOL_RESERVE_RANGE[0]), k_hi=pool_k(POOL_RESERVE_RANGE[1]),
                                 f_lo=POOL_F, f_hi=POOL_F),
}


def breakeven(fn, delta, lo=0.0, hi=0.20):
    """lambda_P at which an increasing cost function fn(lambda_P) equals delta (None if never)."""
    if fn(lo) >= delta:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fn(mid) < delta else (lo, mid)
    return (lo + hi) / 2


# =============================================================================
# 3. FORMATTING
# =============================================================================
def bps(x, force_decimal=False):
    """Whole bps; one decimal only below 5 bps."""
    v = x / BP
    if abs(v) < 1e-9:
        return "0"
    if force_decimal or abs(v) < 5:
        return f"{v:.1f}"
    return f"{v:.0f}"


def pct(x, nd=2):
    return f"{x * 100:.{nd}f}%"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


def M(x):
    return f"${x / 1e6:,.0f}M"


# =============================================================================
# 4. COMPUTE ALL RESULTS
# =============================================================================
BANK = "Bank SBLC seller"
REF = "Funded investor vehicle"          # reference provider for grids and tornado

base = {name: components(k=p["k"], f=p["f"]) for name, p in PROVIDERS.items()}
bank = bank_prices()
base[BANK] = dict(bank["p"] if bank["binding"] == "P" else bank["q"])     # decomposition of the binding price
base[BANK]["c_star"] = bank["all_in"]
for name, p in PROVIDERS.items():
    base[name]["haircut"] = wrong_way_haircut(p["p"], p["lgd_s"])
    if name == BANK:
        base[name]["lo"] = bank_prices(k=p["k_lo"])["all_in"]
        base[name]["hi"] = bank_prices(k=p["k_hi"])["all_in"]
    else:
        base[name]["lo"] = components(k=p["k_lo"], f=p["f_lo"])["c_star"]
        base[name]["hi"] = components(k=p["k_hi"], f=p["f_hi"])["c_star"]
ref = base[REF]
self_ins = self_insured()
transfer = FUND_K + FUND_F

floor = bank_p_floor()
floor_gross = bank_p_floor(capital=CAPITAL_COST_GROSS)
bank_gross = bank_prices(capital=CAPITAL_COST_GROSS)
bank_stress = bank_prices(k=bank_k(LCR_OUTFLOW_STRESS))
bank_zero = bank_prices(k=bank_k(0.0))
# lambda_P at which the bank's Q price overtakes its P price (both linear in lambda_P)
_q0, _p0 = bank_prices(lambda_p=0.0), bank_prices(lambda_p=0.01)
_slope_q = (_p0["q"]["c_star"] - _q0["q"]["c_star"]) / 0.01
_slope_p = (_p0["p"]["c_star"] - _q0["p"]["c_star"]) / 0.01
bank_cross = (_q0["p"]["c_star"] - _q0["q"]["c_star"]) / (_slope_q - _slope_p)

# Sensitivity grid lambda_P x LGD (mu 3, a 50%), reference provider
grid = {(lp, lgd): components(lambda_p=lp, lgd=lgd, k=FUND_K, f=FUND_F) for lp in LAMBDA_P_SET for lgd in LGD_SET}

# Tornado-style one-at-a-time sensitivities, reference provider
tornado = []
def _row(label, values, fn):
    tornado.append((label, [(v, fn(v)["c_star"]) for v in values]))
_row("mu", MU_SET, lambda v: components(mu=v, k=FUND_K, f=FUND_F))
_row("a (advance dividend)", ADV_SET, lambda v: components(a=v, k=FUND_K, f=FUND_F))
_row("D (years to final dividends)", D_SET, lambda v: components(d=v, k=FUND_K, f=FUND_F))
_row("lambda_P", LAMBDA_P_SET, lambda v: components(lambda_p=v, k=FUND_K, f=FUND_F))
_row("LGD_dep", LGD_SET, lambda v: components(lgd=v, k=FUND_K, f=FUND_F))
_row("k (funded vehicle range)", list(FUND_K_RANGE), lambda v: components(k=v, f=FUND_F))
_row("f (funded vehicle range)", list(FUND_F_RANGE), lambda v: components(k=FUND_K, f=v))

access_detail = {(a, d): components(a=a, d=d, k=0, f=0)["access"] for a in ADV_SET for d in D_SET}

# Market-implied cross-check (upper reference, not a calibration)
market = []
for s in SENIOR_SPREADS:
    lq = s / SENIOR_LGD
    market.append(dict(spread=s, lq=lq, mu_impl=lq / LAMBDA_P,
                       credit={lgd: lq * lgd for lgd in LGD_SET},
                       c_star={lgd: components(lambda_p=lq, mu=1.0, lgd=lgd, k=FUND_K, f=FUND_F)["c_star"] for lgd in LGD_SET}))
base_lq_spread = lambda_q() * SENIOR_LGD

# Depositor yield advantage: (a) bearing the risk, (b) buying protection
SELF = "Self-insured (credit + access)"
be = {SELF: {d: breakeven(lambda lp: self_insured(lambda_p=lp), d) for d in DELTA_SET}}
for name in PROVIDERS:
    be[name] = {d: breakeven(lambda lp, n=name: provider_c_star(n, lambda_p=lp), d) for d in DELTA_SET}
gap_self = {(lp, d): self_insured(lambda_p=lp) - d for lp in LAMBDA_P_SET for d in DELTA_SET}
gap_buy = {(lp, d): grid[(lp, LGD_DEP)]["c_star"] - d for lp in LAMBDA_P_SET for d in DELTA_SET}

# Wedge on $1B
wedge = []
for lgd in LGD_SET:
    adv = ADV_DIV * WEDGE_N
    loss = lgd * WEDGE_N
    later = max(0.0, 1 - ADV_DIV - lgd) * WEDGE_N
    bridge_cost = later * (R_FREE + S_B) * D_YEARS
    prem = components(lgd=lgd, k=FUND_K, f=FUND_F)["c_star"] * WEDGE_N
    wedge.append(dict(lgd=lgd, gross=WEDGE_N, adv=adv, net_bridge=WEDGE_N - adv, later=later, loss=loss,
                      bridge_cost=bridge_cost, premium=prem, years=(loss + bridge_cost) / prem))


# --- v3 A: single-bank funded vehicle tranche economics -----------------------
def tranche_vehicle(lambda_p=LAMBDA_P, lgd=LGD_DEP, thickness=None, access_to="first_loss", realized_lgd=None):
    """Investors fund 100% of N in T-bills; first loss = thickness T, senior = 1 - T.
    Premium split (base specification): senior earns k; first loss earns credit + access (access_to="first_loss").
    Spreads are over T-bills on each tranche's own size. f goes to the operator."""
    T = lgd if thickness is None else thickness
    L_ = lgd if realized_lgd is None else realized_lgd
    c = components(lambda_p=lambda_p, lgd=lgd, k=FUND_K, f=FUND_F)
    senior = 1.0 - T
    fl_inc = c["credit"] + (c["access"] if access_to == "first_loss" else 0.0)
    sr_inc = c["capacity"] + (c["access"] if access_to == "senior" else 0.0)
    fl_loss = min(L_ / T, 1.0)                      # share of first-loss principal lost at failure
    sr_loss = max(L_ - T, 0.0) / senior             # share of senior principal lost at failure
    later = max(0.0, 1.0 - ADV_DIV - L_)            # par recovered after D years
    sr_later = min(later, senior - max(L_ - T, 0.0) - min(ADV_DIV, senior))  # senior's share of it (senior paid first)
    sr_back_now = min(ADV_DIV, senior) / senior     # share of senior principal back within days
    sr_locked = max(sr_later, 0.0) / senior         # share of senior principal locked for D years, no interest
    return dict(T=T, fl_spread=fl_inc / T, fl_el=lambda_p * fl_loss, fl_excess=fl_inc / T - lambda_p * fl_loss,
                fl_loss=fl_loss, sr_spread=sr_inc / senior, sr_el=lambda_p * sr_loss, sr_loss=sr_loss,
                sr_back_now=sr_back_now, sr_locked=sr_locked,
                sr_bridge_cost_event=sr_locked * R_FREE * D_YEARS,          # opportunity cost at r, given failure
                sr_bridge_cost_p=lambda_p * sr_locked * R_FREE * D_YEARS)  # annual P-expected, on senior size


tr_base = tranche_vehicle()
tr_alt = tranche_vehicle(access_to="senior")
tr_grid = {(lp, lgd): tranche_vehicle(lambda_p=lp, lgd=lgd) for lp in TRANCHE_LP_SET for lgd in LGD_SET}
tr_thick40 = tranche_vehicle(thickness=FL_THICKNESS_STRESS)
tr_real = {rl: tranche_vehicle(realized_lgd=rl) for rl in LGD_SET}


# --- v3 B: portfolio across many banks with clustered failures -----------------
import math
import numpy as np
from statistics import NormalDist
_ND = NormalDist()
_ncdf = np.frompyfunc(_ND.cdf, 1, 1)


def cond_pd(pd, rho, z):
    """Vasicek conditional default probability given the common factor z."""
    return np.asarray(_ncdf((_ND.inv_cdf(pd) - math.sqrt(rho) * z) / math.sqrt(1.0 - rho)), dtype=float)


def count_pmf(pd=LAMBDA_P, rho=0.2, n=PORT_N):
    """Exact distribution of the number of failures (quadrature over z)."""
    k = np.arange(n + 1)
    binom = np.array([math.comb(n, i) for i in k], dtype=float)
    if rho == 0:
        return binom * pd ** k * (1 - pd) ** (n - k)
    z = np.linspace(-8, 8, Z_GRID)
    w = np.exp(-z * z / 2) / math.sqrt(2 * math.pi) * (z[1] - z[0])
    p = cond_pd(pd, rho, z)[:, None]
    pmf = (w[:, None] * binom[None, :] * p ** k[None, :] * (1 - p) ** (n - k)[None, :]).sum(axis=0)
    return pmf / pmf.sum()


def tranche_stats(losses, probs, tranches):
    out = []
    for name, A, Dt in tranches:
        tl = np.clip(losses - A, 0, Dt - A) / (Dt - A)
        out.append(dict(name=name, A=A, D=Dt, el=float((tl * probs).sum()), p_hit=float(probs[losses > A + 1e-12].sum())))
    return out


def quantile(losses, probs, q):
    order = np.argsort(losses)
    cdf = np.cumsum(probs[order])
    return float(losses[order][np.searchsorted(cdf, q - 1e-12)])


port = {}
for rho in PORT_RHO_SET:
    pmf = count_pmf(rho=rho)
    losses = np.arange(PORT_N + 1) * LGD_DEP / PORT_N
    cnt = np.arange(PORT_N + 1)
    port[rho] = dict(pmf=pmf, p0=pmf[0], p1=pmf[1], p2=pmf[2], p3p=pmf[3:].sum(),
                     e_count=float((cnt * pmf).sum()), el=float((losses * pmf).sum()),
                     q99=quantile(losses, pmf, 0.99), q995=quantile(losses, pmf, 0.995),
                     n99=int(round(quantile(losses, pmf, 0.99) * PORT_N / LGD_DEP)),
                     n995=int(round(quantile(losses, pmf, 0.995) * PORT_N / LGD_DEP)),
                     tr=tranche_stats(losses, pmf, PORT_TRANCHES), tr_alt=tranche_stats(losses, pmf, PORT_TRANCHES_ALT))

# Monte Carlo: stochastic-LGD variant, and a check of the exact count distribution
rng = np.random.default_rng(MC_SEED)
port_mc = {}
for rho in PORT_RHO_SET:
    z = rng.standard_normal(MC_PATHS)
    p = np.full(MC_PATHS, LAMBDA_P) if rho == 0 else cond_pd(LAMBDA_P, rho, z)
    counts = rng.binomial(PORT_N, p)
    loss = np.zeros(MC_PATHS)
    for j in range(1, int(counts.max()) + 1):
        m = counts >= j
        loss[m] += rng.uniform(*PORT_LGD_STOCH, m.sum())
    loss /= PORT_N
    w = np.full(MC_PATHS, 1.0 / MC_PATHS)
    port_mc[rho] = dict(p3p=float((counts >= CLUSTER_N).mean()), el=float(loss.mean()),
                        q99=float(np.quantile(loss, 0.99)), q995=float(np.quantile(loss, 0.995)),
                        tr=tranche_stats(loss, w, PORT_TRANCHES))


# --- v3 C: recovery-gap financing -----------------------------------------------
gap_R = max(0.0, 1 - ADV_DIV - LGD_DEP)                       # expected remaining recovery, fraction of par
gap = {(x, d): (1 / x) ** (1 / d) - 1 for x in GAP_PRICE_SET for d in GAP_D_SET}
gap_stress_R = max(0.0, 1 - ADV_DIV - GAP_STRESS_LGD)
gap_stress = {(x, d): dict(price=x * gap_R, ret_total=gap_stress_R / (x * gap_R) - 1,
                           ret_ann=(gap_stress_R / (x * gap_R)) ** (1 / d) - 1)
              for x in GAP_PRICE_SET for d in GAP_D_SET}
gap_upside_R = max(0.0, 1 - ADV_DIV - min(LGD_SET))
gap_breakeven_lgd = {x: 1 - ADV_DIV - x * gap_R for x in GAP_PRICE_SET}   # LGD at which the buyer gets its price back


# =============================================================================
# 5. RESULTS FILE
# =============================================================================
def write_results():
    L = []
    L.append("# The clearing cost of an uninsured deposit: model results (v3)\n")
    L.append(f"Generated by `{SCRIPT_NAME}` (run with `python3 -I`). Every number below is computed by that script; "
             "edit parameters there, not here. Units: bps per year on the covered balance unless stated. Rounding: whole bps, "
             "one decimal below 5 bps. v2 applied the author's decisions on the v1 flags; v3 adds Sections 10 to 13 (private capital) with all v2 results carried forward unchanged (Section 15). "
             "Independent validation of the arithmetic is welcome.\n")

    # 1. Parameters
    L.append("## 1. Parameters\n")
    L.append(table(["Parameter", "Symbol", "Base", "Range / set", "Source"], [
        ["Physical default intensity", "lambda_P", pct(LAMBDA_P), ", ".join(pct(x) for x in LAMBDA_P_SET), "author assumption (illustrative)"],
        ["Risk-premium multiplier", "mu", f"{MU:g}", ", ".join(str(x) for x in MU_SET), "author assumption (illustrative)"],
        ["Risk-neutral intensity", "lambda_Q = mu x lambda_P", pct(lambda_q()), "", "derived"],
        ["Loss on deposit claim", "LGD_dep", pct(LGD_DEP, 0), ", ".join(pct(x, 0) for x in LGD_SET), "author assumption (illustrative)"],
        ["Advance dividend", "a", pct(ADV_DIV, 0), ", ".join(pct(x, 0) for x in ADV_SET), "author assumption (illustrative)"],
        ["Years to final dividends", "D", f"{D_YEARS:g}", ", ".join(str(x) for x in D_SET), "author assumption (illustrative)"],
        ["Risk-free rate", "r", pct(R_FREE, 1), "", "3-month T-bill, FRED DGS3MO 4.28%, as of 15 October 2026; verify before relying on it"],
        ["Provider funding spread", "s_b", pct(S_B, 1), "", "author assumption (illustrative)"],
        ["Frictions", "f", bps(F_BASE) + " bps", "funded vehicle 10 to 20 bps", "author assumption (illustrative)"],
        ["Funded vehicle capacity cost", "k", bps(FUND_K) + " bps", "5 to 15 bps", "author assumption (base = midpoint)"],
        ["Bank LCR outflow on commitment", "", pct(LCR_OUTFLOW, 0), "0% to 30%; 100% stress", "on my reading of 12 CFR 249.32(e); base 30%"],
        ["Net HQLA carry", "", bps(HQLA_CARRY) + " bps", "", "author assumption (illustrative)"],
        ["Capital: CCF x RW x CET1 x (hurdle - r)", "", f"{CCF:.0%} x {RW:.0%} x {CET1_RATIO:.1%} x ({HURDLE:.0%} - {R_FREE:.1%})",
         "", "12 CFR 217.33(b)(4), 217.32(d); CET1 and hurdle author assumptions; net of r"],
        ["Pool prefunded reserve", "", pct(POOL_RESERVE, 0), "5% to 20%", "illustrative [author assumption]"],
        ["Pool reserve opportunity cost", "", bps(POOL_RESERVE_OPP) + " bps", "", "illustrative [author assumption]"],
        ["P(seller fails given reference fails)", "", "pool 40%; bank 5%; vehicle 0%", "pool 30% to 50%",
         "pool: author assumption; bank, vehicle: illustrative [author assumption]"],
        ["Seller LGD", "LGD_seller", "pool 50%; bank 60%", "", "illustrative [author assumption]"],
    ]))
    L.append("")

    # 2. Base-case decomposition
    L.append("## 2. Base-case decomposition by provider type\n")
    L.append("The bank seller's row decomposes its binding price (Section 3): credit there is EL_P under P, access is P-access, "
             "and capital is a separate component. The other providers are priced under Q with no capital component.\n")
    rows = []
    for name, c in base.items():
        rows.append([name, bps(c["credit"]), bps(c["access"]), bps(c["capital"]), bps(c["capacity"]), bps(c["frictions"]),
                     "**" + bps(c["c_star"]) + "**", f"{bps(c['lo'])} to {bps(c['hi'])}",
                     bps(c["haircut"]), bps(c["c_star"] - c["haircut"])])
    L.append(table(["Provider", "Credit", "Access", "Capital", "Capacity k", "Frictions f", "c*", "c* range (k, f ranges)",
                    "Wrong-way haircut", "c* net of haircut"], rows))
    L.append("")
    L.append(f"- Unrounded funded-vehicle components: credit {ref['credit'] / BP:.2f}, access {ref['access'] / BP:.2f}, "
             f"c* {ref['c_star'] / BP:.2f} bps. Bank all-in c* {bank['all_in'] / BP:.2f} bps. Rounded components may not add to the rounded total.")
    L.append(f"- Self-insured cost (credit + access): {bps(self_ins)} bps. Transfer cost k + f (funded vehicle): {bps(transfer)} bps. "
             f"Credit is {ref['credit'] / ref['c_star']:.0%} of the funded-vehicle c*, access {ref['access'] / ref['c_star']:.0%}, "
             f"transfer cost {transfer / ref['c_star']:.0%}.")
    L.append(f"- Pool wrong-way haircut across P(seller fails | reference fails) 30% to 50%: "
             f"{bps(wrong_way_haircut(0.30, POOL_LGD_SELLER))} to {bps(wrong_way_haircut(0.50, POOL_LGD_SELLER))} bps (LGD_seller 50%); "
             f"at LGD_seller 100%: {bps(wrong_way_haircut(0.30, 1.0))} to {bps(wrong_way_haircut(0.50, 1.0))} bps.\n")

    # 3. Bank seller
    L.append("## 3. Bank SBLC seller: Q price, full P price, all-in c*\n")
    L.append("Bank c* = max(Q price, full P price). Capital cost = CCF x RW x CET1 x (hurdle - r), since capital is invested at r. "
             "The gross-hurdle figures from v1 are a memo column only.\n")
    def brow(label, f_):
        return [label] + [f_(b) for b in (bank_zero, bank, bank_stress, bank_gross)]
    L.append(table(["Item", "Outflow 0% (k 0)", "Base: outflow 30% (k 12)", "Stress: outflow 100% (k 40)", "Memo: base, gross hurdle"], [
        brow("EL_P = lambda_P x LGD_dep", lambda b: bps(b["p"]["credit"])),
        brow("P-access", lambda b: bps(b["p"]["access"])),
        brow("Capital cost", lambda b: bps(b["p"]["capital"])),
        brow("P floor (EL_P + capital)", lambda b: bps(b["p"]["credit"] + b["p"]["capital"])),
        brow("Full P price (EL_P + P-access + capital + k + f)", lambda b: bps(b["p"]["c_star"])),
        brow("Q price (credit + access + k + f under Q)", lambda b: bps(b["q"]["c_star"])),
        brow("**Bank c\\* = max(Q, P)**", lambda b: "**" + bps(b["all_in"]) + "**"),
        brow("Binding measure", lambda b: b["binding"]),
    ]))
    L.append("")
    L.append(f"The P price binds below lambda_P of about {pct(bank_cross)} (base k), the Q price above it. "
             "Bank c* across lambda_P (base k): " +
             "; ".join(f"{pct(lp)}: {bps(bank_prices(lambda_p=lp)['all_in'])} ({bank_prices(lambda_p=lp)['binding']})"
                       for lp in LAMBDA_P_SET) + " bps. P floor across lambda_P: " +
             "; ".join(f"{pct(lp)}: {bps(bank_p_floor(lambda_p=lp))}" for lp in LAMBDA_P_SET) + " bps.\n")

    # 4. Grid
    L.append("## 4. Sensitivity grid by lambda_P and LGD_dep (mu 3, a 50%, funded vehicle k 10, f 15)\n")
    rows = []
    for lp in LAMBDA_P_SET:
        rows.append([pct(lp), pct(lambda_q(lp))]
                    + [bps(grid[(lp, lgd)]["credit"] + grid[(lp, lgd)]["access"]) for lgd in LGD_SET]
                    + [bps(grid[(lp, lgd)]["c_star"]) for lgd in LGD_SET])
    L.append(table(["lambda_P", "lambda_Q"] + [f"Self-insured LGD {lgd:.0%}" for lgd in LGD_SET]
                   + [f"c* LGD {lgd:.0%}" for lgd in LGD_SET], rows))
    L.append("\nAccess component alone (bps):\n")
    L.append(table(["lambda_P"] + [f"access LGD {lgd:.0%}" for lgd in LGD_SET],
                   [[pct(lp)] + [bps(grid[(lp, lgd)]["access"]) for lgd in LGD_SET] for lp in LAMBDA_P_SET]))
    L.append("\nc* minus self-insured cost is the transfer cost k + f = 25 bps in every cell. The pool's c* equals the vehicle's; "
             "the bank's is in Section 3.\n")

    # 5. Tornado
    L.append("## 5. One-at-a-time sensitivities (funded vehicle; base c* = " + bps(ref["c_star"]) + " bps)\n")
    rows = []
    for label, res in tornado:
        vals = [r[1] for r in res]
        def lab(v):
            if label.startswith("lambda"):
                return pct(v)
            if label.startswith(("LGD", "a ")):
                return pct(v, 0)
            if label.startswith(("k", "f")):
                return bps(v)
            return f"{v:g}"
        rows.append([label, "; ".join(f"{lab(v)}: {bps(c)}" for v, c in res),
                     bps(min(vals) - ref["c_star"]), "+" + bps(max(vals) - ref["c_star"])])
    L.append(table(["Driver", "c* at each value (bps)", "Low swing", "High swing"], rows))
    L.append("\nAccess component by a and D (bps, base lambda_P, LGD 25%):\n")
    L.append(table(["a \\ D"] + [f"D = {d}" for d in D_SET],
                   [[pct(a, 0)] + [bps(access_detail[(a, d)]) for d in D_SET] for a in ADV_SET]))
    L.append("")

    # 6. Market implied
    L.append("## 6. Market-implied cross-check: an upper reference, not a calibration\n")
    L.append("Hypothetical round-number senior spreads, senior LGD 60%, lambda_Q = spread / 60%. Senior spreads usually reference "
             "the holding company (structurally junior to a deposit at the bank) and carry non-default premia, so these "
             "intensities overstate the default risk relevant to a deposit claim.\n")
    rows = [[bps(m["spread"]), pct(m["lq"]), f"{m['mu_impl']:.1f}"] + [bps(m["credit"][lgd]) for lgd in LGD_SET]
            + [bps(m["c_star"][LGD_DEP])] for m in market]
    L.append(table(["Senior spread (bps)", "lambda_Q", "Implied mu vs lambda_P 0.25%"]
                   + [f"Credit LGD {lgd:.0%}" for lgd in LGD_SET] + ["c* LGD 25% (funded)"], rows))
    L.append(f"\nBase-case lambda_Q of {pct(lambda_q())} corresponds to a senior spread of about {bps(base_lq_spread)} bps.\n")

    # 7. Provider comparison
    L.append("## 7. Provider comparison\n")
    notes = {REF: "T-bill collateral, no negative carry; investor liquidity premium",
             BANK: f"max(Q {bps(bank['q']['c_star'])}, P {bps(bank['p']['c_star'])}); P floor {bps(floor)}; "
                   f"100% outflow stress c* {bps(bank_stress['all_in'])}",
             "Regional mutual pool": f"reserve {POOL_RESERVE:.0%} pays par only if a member's covered balance is at most "
                                     f"{POOL_RESERVE:.0%} of pool coverage"}
    rows = [[n, bps(c["c_star"]), f"{bps(c['lo'])} to {bps(c['hi'])}", f"{PROVIDERS[n]['p']:.0%}", bps(c["haircut"]),
             bps(c["c_star"] - c["haircut"]), notes[n]] for n, c in base.items()]
    L.append(table(["Provider", "Base c*", "Range", "P(seller fails / ref fails)", "Haircut", "c* net of haircut", "Note"], rows))
    L.append("")

    # 8. Yield advantage, two comparisons
    L.append("## 8. Depositor yield advantage over a government MMF: two comparisons\n")
    L.append("(a) Bearing the risk: the depositor's own cost, credit + access, against its yield advantage Delta. "
             "(b) Buying protection: c* against Delta. The gap between (a) and (b) is the transfer cost k + f. "
             "Delta is a spread over a government money market fund; operating balances often earn an earnings credit rate instead.\n")
    L.append("Break-even lambda_P at which cost equals Delta (mu 3, LGD 25%, a 50%); \"none\" means cost exceeds Delta at any "
             "default probability.\n")
    rows = [[n] + [("none" if be[n][d] is None else pct(be[n][d])) for d in DELTA_SET] for n in be]
    L.append(table(["Comparison"] + [f"Delta {bps(d)}" for d in DELTA_SET], rows))
    L.append("\n(a) Bearing the risk: self-insured cost minus Delta (LGD 25%; positive = depositor not paid for the risk), bps:\n")
    L.append(table(["lambda_P"] + [f"Delta {bps(d)}" for d in DELTA_SET],
                   [[pct(lp)] + [bps(gap_self[(lp, d)]) for d in DELTA_SET] for lp in LAMBDA_P_SET]))
    L.append("\n(b) Buying protection: funded-vehicle c* minus Delta (LGD 25%; positive = protection costs more than the advantage), bps:\n")
    L.append(table(["lambda_P"] + [f"Delta {bps(d)}" for d in DELTA_SET],
                   [[pct(lp)] + [bps(gap_buy[(lp, d)]) for d in DELTA_SET] for lp in LAMBDA_P_SET]))
    L.append("")

    # 9. Wedge
    L.append(f"## 9. The wedge on {M(WEDGE_N)} covered, full exercise (a {ADV_DIV:.0%}, D {D_YEARS:g}, r + s_b {pct(R_FREE + S_B, 1)})\n")
    rows = [[f"{w['lgd']:.0%}", M(w["gross"]), M(w["adv"]), M(w["net_bridge"]), M(w["later"]), M(w["loss"]),
             f"${w['bridge_cost'] / 1e6:,.1f}M", f"${w['premium'] / 1e6:,.1f}M", f"{w['years']:.0f}"] for w in wedge]
    L.append(table(["LGD_dep", "Gross cash at trigger", "Advance dividend back", "Net bridge", "Recovered later (over D)",
                    "Ultimate loss", "Bridge funding cost", "Annual premium at c* (funded)", "Years of premium per event"], rows))
    L.append(f"\nWith no advance dividend (a = 0) the net bridge is the full {M(WEDGE_N)} until receivership dividends begin.\n")

    # ---- v3 sections 10 to 13 ----
    def pp(x, nd=1):
        return f"{x * 100:.{nd}f}%"

    L.append("## 10. Private capital A: single-bank funded vehicle, tranche economics\n")
    L.append(f"Investors fund 100% of the covered balance into T-bills. First-loss tranche = LGD_dep ({FL_THICKNESS:.0%}), senior = the rest. "
             "Premium split as specified: the senior earns k; the first loss earns credit + access; f goes to the operator. "
             "Spreads are over T-bills, on each tranche's own size. The first loss is wiped out at failure, so its P-expected loss is lambda_P.\n")
    t = tr_base
    L.append(table(["Item", "Base (lambda_P 0.25%, LGD 25%)"], [
        ["First-loss spread over T-bills", bps(t["fl_spread"]) + " bps"],
        ["First-loss P-expected loss (= lambda_P)", bps(t["fl_el"]) + " bps"],
        ["First-loss excess spread", "**" + bps(t["fl_excess"]) + " bps**"],
        ["First-loss outcome at failure", f"loses {t['fl_loss']:.0%} of principal"],
        ["Senior spread over T-bills (k on senior size)", bps(t["sr_spread"]) + " bps"],
        ["Senior principal back within days of failure (advance dividend)", pp(t["sr_back_now"], 0)],
        ["Senior principal locked for D years without interest", pp(t["sr_locked"], 0)],
        ["Senior opportunity cost at r if failure occurs", pp(t["sr_bridge_cost_event"]) + " of senior principal"],
        ["Senior P-expected bridge cost per year", bps(t["sr_bridge_cost_p"]) + " bps"],
        ["Senior principal loss if realized LGD <= thickness", "none"],
    ]))
    L.append("\nFirst-loss spread / P-expected loss / excess spread, and senior spread (thickness = LGD in each column), bps:\n")
    rows = []
    for lp in TRANCHE_LP_SET:
        rows.append([pct(lp)] + [f"{bps(tr_grid[(lp, lgd)]['fl_spread'])} / {bps(tr_grid[(lp, lgd)]['fl_el'])} / "
                                 f"{bps(tr_grid[(lp, lgd)]['fl_excess'])}" for lgd in LGD_SET]
                    + [bps(tr_grid[(lp, LGD_DEP)]["sr_spread"])])
    L.append(table(["lambda_P"] + [f"First loss, LGD {lgd:.0%}" for lgd in LGD_SET] + ["Senior, LGD 25%"], rows))
    L.append("\nSenior spread by LGD (thickness = LGD): " + "; ".join(
        f"LGD {lgd:.0%}: {bps(tr_grid[(LAMBDA_P, lgd)]['sr_spread'])} bps" for lgd in LGD_SET) + ".\n")
    L.append("Realized LGD different from the 25% thickness (base lambda_P):\n")
    L.append(table(["Realized LGD", "First-loss principal lost", "Senior principal lost", "Senior back within days", "Senior locked for D years"],
                   [[f"{rl:.0%}", pp(tr_real[rl]["fl_loss"], 0), pp(tr_real[rl]["sr_loss"], 0), pp(tr_real[rl]["sr_back_now"], 0),
                     pp(tr_real[rl]["sr_locked"], 0)] for rl in LGD_SET]))
    L.append(f"\nIf realized LGD exceeds the thickness, the first loss is wiped out and the senior takes the excess: at 40% the senior "
             f"loses {pp(tr_real[0.40]['sr_loss'], 0)} of its principal, against a spread of {bps(t['sr_spread'])} bps a year priced for liquidity, not loss.\n")
    L.append(f"Alternatives: (i) access paid to the senior, which bears the bridge: first loss {bps(tr_alt['fl_spread'])} bps "
             f"(excess {bps(tr_alt['fl_excess'])}), senior {bps(tr_alt['sr_spread'])} bps. (ii) Thickness 40% at an expected LGD of 25%: "
             f"first-loss spread {bps(tr_thick40['fl_spread'])} bps, P-expected loss {bps(tr_thick40['fl_el'])}, excess "
             f"{bps(tr_thick40['fl_excess'])}; senior {bps(tr_thick40['sr_spread'])} bps.\n")

    L.append("## 11. Private capital B: a diversified portfolio across many banks with clustered failures\n")
    L.append(f"{PORT_N} equal exposures, lambda_P {pct(LAMBDA_P)} each, one-factor Gaussian copula (Vasicek), LGD_dep 25% unless stated. "
             f"Exact count distribution by quadrature over the common factor ({Z_GRID} points); stochastic-LGD variant by seeded Monte Carlo "
             f"({MC_PATHS:,} paths, seed {MC_SEED}). Losses are % of total portfolio notional; one failure at LGD 25% costs "
             f"{pp(LGD_DEP / PORT_N, 1)} of the portfolio. rho = 0 is an independence reference.\n")
    L.append(table(["Statistic"] + [f"rho {r:.2f}" for r in PORT_RHO_SET], [
        ["P(0 failures)"] + [pp(port[r]["p0"], 2) for r in PORT_RHO_SET],
        ["P(1 failure)"] + [pp(port[r]["p1"], 2) for r in PORT_RHO_SET],
        ["P(2 failures)"] + [pp(port[r]["p2"], 2) for r in PORT_RHO_SET],
        ["**P(3 or more), 2023-like cluster**"] + ["**" + pp(port[r]["p3p"], 2) + "**" for r in PORT_RHO_SET],
        ["Expected failures per year"] + [f"{port[r]['e_count']:.4f}" for r in PORT_RHO_SET],
        ["Expected loss (% of portfolio)"] + [pp(port[r]["el"], 4) for r in PORT_RHO_SET],
        ["99th percentile loss (failures)"] + [f"{pp(port[r]['q99'])} ({port[r]['n99']})" for r in PORT_RHO_SET],
        ["99.5th percentile loss (failures)"] + [f"{pp(port[r]['q995'])} ({port[r]['n995']})" for r in PORT_RHO_SET],
        ["Gross cash at trigger at 99.5th, per $1B exposure"] + [f"${port[r]['n995']:,}B" for r in PORT_RHO_SET],
        ["Net bridge at 99.5th after 50% advance dividend"] + [f"${port[r]['n995'] * ADV_DIV:,.1f}B" for r in PORT_RHO_SET],
        ["MC check: P(3 or more)"] + [pp(port_mc[r]["p3p"], 2) for r in PORT_RHO_SET],
    ]))
    L.append("\nTranches of portfolio loss (chosen points, see parameters): expected loss as % of tranche per year / probability of any loss:\n")
    L.append(table(["Tranche"] + [f"rho {r:.2f}" for r in PORT_RHO_SET],
                   [[f"{tr['name']} {pp(tr['A'], 0)} to {pp(tr['D'], 0)}"] +
                    [f"{pp(port[r]['tr'][i]['el'], 3)} / {pp(port[r]['tr'][i]['p_hit'], 2)}" for r in PORT_RHO_SET]
                    for i, tr in enumerate(port[PORT_RHO_SET[0]]["tr"])]))
    L.append("\nAlternative tranche points 0 to 3% / 3 to 7% / 7 to 100% (same format):\n")
    L.append(table(["Tranche"] + [f"rho {r:.2f}" for r in PORT_RHO_SET],
                   [[f"{tr['name']} {pp(tr['A'], 0)} to {pp(tr['D'], 0)}"] +
                    [f"{pp(port[r]['tr_alt'][i]['el'], 3)} / {pp(port[r]['tr_alt'][i]['p_hit'], 3)}" for r in PORT_RHO_SET]
                    for i, tr in enumerate(port[PORT_RHO_SET[0]]["tr_alt"])]))
    L.append(f"\nStochastic-LGD variant (uniform {PORT_LGD_STOCH[0]:.0%} to {PORT_LGD_STOCH[1]:.0%}, iid; Monte Carlo):\n")
    L.append(table(["Statistic"] + [f"rho {r:.2f}" for r in PORT_RHO_SET], [
        ["Expected loss"] + [pp(port_mc[r]["el"], 4) for r in PORT_RHO_SET],
        ["99th percentile loss"] + [pp(port_mc[r]["q99"], 2) for r in PORT_RHO_SET],
        ["99.5th percentile loss"] + [pp(port_mc[r]["q995"], 2) for r in PORT_RHO_SET],
    ] + [[f"{tr['name']} {pp(tr['A'], 0)} to {pp(tr['D'], 0)}: EL / P(hit)"] +
         [f"{pp(port_mc[r]['tr'][i]['el'], 3)} / {pp(port_mc[r]['tr'][i]['p_hit'], 2)}" for r in PORT_RHO_SET]
         for i, tr in enumerate(port_mc[PORT_RHO_SET[0]]["tr"])]))
    L.append("")

    L.append("## 12. Private capital C: recovery-gap financing (illustrative)\n")
    L.append(f"After a failure with a {ADV_DIV:.0%} advance dividend, the claim holder waits about D years for the remaining recovery, "
             f"1 - a - LGD_dep = {pp(gap_R, 0)} of par at base ({pp(1 - ADV_DIV - max(LGD_SET), 0)} to {pp(1 - ADV_DIV - min(LGD_SET), 0)} "
             "across LGD 40% to 15%). A buyer pays a fraction of the expected remaining recovery and is repaid once, at the end of D. "
             "Receivership claims typically earn no interest, so the discount is the whole return. Illustrative; no market prices are implied.\n")
    L.append("Annualized return to the buyer if recovery comes in as expected (independent of the recovery level):\n")
    L.append(table(["Price (% of expected recovery)"] + [f"D = {d}" for d in GAP_D_SET] + [f"D = {d}, excess over r" for d in GAP_D_SET],
                   [[f"{x:.0%}"] + [pp(gap[(x, d)]) for d in GAP_D_SET] + [pp(gap[(x, d)] - R_FREE) for d in GAP_D_SET]
                    for x in GAP_PRICE_SET]))
    L.append(f"\nDownside: priced on LGD 25% (expected remaining recovery {pp(gap_R, 0)} of par) but LGD comes in at "
             f"{GAP_STRESS_LGD:.0%} (remaining recovery {pp(gap_stress_R, 0)}):\n")
    L.append(table(["Price (% of expected)", "Price (% of par)", "Total return"] + [f"Annualized, D = {d}" for d in GAP_D_SET]
                   + ["LGD at which buyer only gets its price back"],
                   [[f"{x:.0%}", pp(gap_stress[(x, 1)]["price"]), pp(gap_stress[(x, 1)]["ret_total"], 0)]
                    + [pp(gap_stress[(x, d)]["ret_ann"]) for d in GAP_D_SET] + [pp(gap_breakeven_lgd[x])] for x in GAP_PRICE_SET]))
    L.append(f"\nUpside if LGD comes in at 15% (remaining recovery {pp(gap_upside_R, 0)}): total return "
             + "; ".join(f"{x:.0%}: {pp(gap_upside_R / (x * gap_R) - 1, 0)}" for x in GAP_PRICE_SET) + ".\n")

    L.append("## 13. Regulatory fact for the prose (verified)\n")
    L.append("12 CFR 249.32(h): the LCR run-off rate for unsecured wholesale deposits from non-financial corporates is 25% for operational "
             "deposits and 40% for non-operational deposits that are not fully insured. (Distinct from the 249.32(e) commitment outflow "
             "used for the bank seller's k in Section 3.)\n")

    # 10. Observations
    o = []
    o.append(f"Access funding is small in expectation: {bps(ref['access'])} bps at base against {bps(ref['credit'])} bps of credit, "
             f"and only {bps(access_detail[(0.0, 3)])} bps with no advance dividend and D = 3. The bridge matters as cash at trigger "
             f"({M(wedge[1]['net_bridge'])} on {M(WEDGE_N)}), not as an expected cost; the standing-capacity term k, paid every year "
             f"whether or not anything fails, is about {ref['capacity'] / ref['access']:.0f} times the expected access cost for the funded vehicle.")
    o.append(f"At base the transfer cost (k + f = {bps(transfer)} bps) is larger than the risk itself (credit + access = "
             f"{bps(self_ins)} bps). At a low PD, most of the price of protection is the cost of the transfer.")
    o.append(f"Provider c* at base: funded vehicle {bps(base[REF]['c_star'])}, bank SBLC {bps(base[BANK]['c_star'])}, "
             f"pool {bps(base['Regional mutual pool']['c_star'])} bps. For the bank the full P price ({bps(bank['p']['c_star'])}) "
             f"slightly exceeds the Q price ({bps(bank['q']['c_star'])}), so capital rather than the risk premium sets its price at low PD; "
             f"the P price binds below lambda_P of about {pct(bank_cross)}. The P floor (EL_P + capital) is {bps(floor)} bps, of which "
             f"capital is {bps(CAPITAL_COST)}. At the 100% stress outflow the bank's c* is {bps(bank_stress['all_in'])} bps.")
    o.append(f"Pool protection is worth {bps(base['Regional mutual pool']['haircut'])} bps less to the depositor at base "
             f"(range {bps(wrong_way_haircut(0.30, POOL_LGD_SELLER))} to {bps(wrong_way_haircut(0.50, POOL_LGD_SELLER))}). "
             f"The haircut is small in bps because it scales with lambda_Q; its content is the tail (Ohio and Maryland, 1985), "
             f"where the pool fails when it is needed. A {POOL_RESERVE:.0%} reserve cannot pay par on a failed member whose covered "
             f"balance exceeds {POOL_RESERVE:.0%} of total pool coverage without post-event assessments.")
    o.append(f"Bearing the risk versus buying protection. With a 50 bps yield advantage the depositor is paid for bearing the risk up to "
             f"lambda_P of about {pct(be[SELF][50 * BP])}, but buying protection from the vehicle pays only up to {pct(be[REF][50 * BP])} "
             f"(bank {pct(be[BANK][50 * BP])}). At 100 bps: bearing {pct(be[SELF][100 * BP])}, buying {pct(be[REF][100 * BP])}. "
             f"At 25 bps the depositor is paid for bearing the risk up to {pct(be[SELF][25 * BP])} but no protection purchase clears, "
             f"because k + f alone are 25 bps. At zero or negative advantage (an earnings credit rate) neither clears at any PD.")
    o.append(f"So a depositor can be fairly paid for the risk and still rationally decline to buy protection; the {bps(transfer)} bps "
             f"transfer cost is the space a private provider has to compress.")
    o.append(f"The base-case lambda_Q of {pct(lambda_q())} corresponds to a senior spread near {bps(base_lq_spread)} bps at 60% senior LGD. "
             f"Hypothetical spreads of 60 to 250 bps imply lambda_Q of {pct(market[0]['lq'])} to {pct(market[-1]['lq'])} (mu of "
             f"{market[0]['mu_impl']:.0f} to {market[-1]['mu_impl']:.0f} against lambda_P 0.25%), and a credit component at LGD 25% of "
             f"{bps(market[0]['credit'][0.25])} to {bps(market[-1]['credit'][0.25])} bps. As an upper reference, spread-implied pricing "
             f"sits far above the base case once a bank trades wide, which is when depositors would want protection.")
    o.append(f"Biggest single drivers (funded vehicle): lambda_P ({bps(tornado[3][1][0][1])} to {bps(tornado[3][1][-1][1])} bps across "
             f"0.10% to 2.00%), then mu (2 to 5: {bps(tornado[0][1][0][1])} to {bps(tornado[0][1][-1][1])}) and LGD "
             f"(15% to 40%: {bps(tornado[4][1][0][1])} to {bps(tornado[4][1][-1][1])}). a and D move c* by at most "
             f"{bps(max(abs(c - ref['c_star']) for _, res in tornado[1:3] for _, c in res))} bps.")
    o.append(f"The wedge: {M(WEDGE_N)} of cash at trigger, {M(wedge[1]['net_bridge'])} net after a 50% advance dividend, "
             f"{M(wedge[0]['loss'])} to {M(wedge[2]['loss'])} ultimate loss across LGD 15% to 40%, against about "
             f"${wedge[1]['premium'] / 1e6:,.1f}M a year of premium at base; one event costs roughly {wedge[1]['years']:.0f} years "
             f"of premium at LGD 25%.")
    oA = tr_base
    o.append(f"Tranche A. The first loss earns {bps(oA['fl_spread'])} bps over T-bills against a P-expected loss of {bps(oA['fl_el'])} bps, "
             f"an excess spread of {bps(oA['fl_excess'])} bps a year, for a position that loses 100% of principal when the one bank fails. "
             f"At lambda_P 1% the numbers scale to {bps(tr_grid[(0.01, LGD_DEP)]['fl_spread'])} / {bps(tr_grid[(0.01, LGD_DEP)]['fl_el'])} / "
             f"{bps(tr_grid[(0.01, LGD_DEP)]['fl_excess'])}. The excess is almost entirely the mu - 1 risk premium: with mu = 1 the spread would be "
             f"{bps(oA['fl_spread'] / MU)} bps and the excess {bps(oA['fl_spread'] / MU - oA['fl_el'])} bps. "
             f"It is thin against the event: an all-or-nothing, single-name outcome that no amount of spread diversifies inside a one-bank vehicle.")
    o.append(f"The senior earns {bps(oA['sr_spread'])} bps for standing ready; at failure it gets {pp(oA['sr_back_now'], 0)} of principal back within "
             f"days and has {pp(oA['sr_locked'], 0)} locked for about {D_YEARS:g} years without interest (opportunity cost about "
             f"{pp(oA['sr_bridge_cost_event'])} of principal). It loses principal only if realized LGD exceeds the thickness: at 40% it loses "
             f"{pp(tr_real[0.40]['sr_loss'], 0)}. Sizing the first loss at a stressed 40% instead of 25% cuts the first-loss spread to "
             f"{bps(tr_thick40['fl_spread'])} bps and the excess to {bps(tr_thick40['fl_excess'])}.")
    r1, r3 = PORT_RHO_SET[1], PORT_RHO_SET[-1]
    o.append(f"Portfolio B. Clustering leaves expected loss unchanged ({pp(port[0.0]['el'], 4)} of the portfolio at every rho) and moves "
             f"the tail. P(3 or more failures among 50) is {pp(port[0.0]['p3p'], 2)} under independence, {pp(port[r1]['p3p'], 2)} at rho "
             f"{r1:.2f} and {pp(port[r3]['p3p'], 2)} at rho {r3:.2f}. The 99.5th percentile loss goes from {pp(port[0.0]['q995'])} "
             f"({port[0.0]['n995']} failures) to {pp(port[r3]['q995'])} ({port[r3]['n995']}) at rho {r3:.2f}.")
    o.append(f"Tranche losses move the same way: the mezzanine's probability of any loss goes from {pp(port[0.0]['tr'][1]['p_hit'], 2)} "
             f"(independence) to {pp(port[r3]['tr'][1]['p_hit'], 2)} at rho {r3:.2f}, and the senior's from {pp(port[0.0]['tr'][2]['p_hit'], 3)} "
             f"to {pp(port[r3]['tr'][2]['p_hit'], 3)}. Diversification makes each depositor's protection cheaper to back, but the capacity "
             f"needed is set by clusters, and a provider covering the class would need cash for the {port[r3]['n995']} failures of a "
             f"99.5th-percentile year at rho {r3:.2f}: ${port[r3]['n995']:,}B of gross cash at trigger if each exposure is $1B. Private protection can make one "
             f"depositor safe; it cannot make uninsured deposits safe as a class without capacity for the cluster.")
    o.append(f"Recovery gap C. Buying the remaining claim at 90% of expected recovery returns {pp(gap[(0.90, 1)])} a year over one year, "
             f"{pp(gap[(0.90, 2)])} over two and {pp(gap[(0.90, 3)])} over three; at 95% the two-year return ({pp(gap[(0.95, 2)])}) is below "
             f"r ({pp(R_FREE)}). The return is all discount and all duration risk. A buyer at 90% gets only its price back at LGD "
             f"{pp(gap_breakeven_lgd[0.90])}, so a {(gap_breakeven_lgd[0.90] - LGD_DEP) * 100:.1f} percentage-point miss on LGD erases the return; at LGD 40% the "
             f"buyer loses {pp(-gap_stress[(0.90, 1)]['ret_total'], 0)} of its price. This is the same bridge the tranche-A senior carries.")
    L.append("## 14. What the numbers say\n")
    L.extend(f"{i}. {t}" for i, t in enumerate(o, 1))
    L.append("")

    # 11. Assumptions and decisions
    L.append("## 15. Assumptions and decisions\n")
    L.append("Author decisions on the v1 flags (2026-10-17):\n")
    dec = [
        f"Capital cost is charged as the hurdle in excess of r, since capital is invested at r: {bps(CAPITAL_COST)} bps "
        f"(v1 gross-hurdle figure {bps(CAPITAL_COST_GROSS)} bps kept as a memo column). P floor {bps(floor)} bps "
        f"(v1: {bps(floor_gross)}).",
        f"Bank c* = max(Q price, full P price including access, k and f). Base: Q {bps(bank['q']['c_star'])}, "
        f"P {bps(bank['p']['c_star'])}, c* {bps(bank['all_in'])} bps.",
        f"Bank k base is the 30% outflow (k {bps(bank_k())} bps); 0% (c* {bps(bank_zero['all_in'])}) and the 100% internal stress "
        f"(c* {bps(bank_stress['all_in'])}) are shown alongside.",
        "Market-implied table kept, labelled an upper reference rather than a calibration.",
        "Two distinct yield-advantage comparisons: bearing the risk (credit + access) and buying protection (c*); the gap is k + f.",
        "Funded investor vehicle is the reference provider for the grids, the tornado and fig-04.",
        "v3: Sections 10 to 13 added (tranche economics, portfolio, recovery gap, LCR fact). Figures renumbered in reading order: "
        "fig-02 decomposition, fig-03 wedge, fig-05 portfolio tail (new). All v2 numbers carried forward unchanged.",
    ]
    L.extend(f"{i}. {t}" for i, t in enumerate(dec, 1))
    L.append("\nAssumptions kept as specified, noted for the reader:\n")
    notes_ = [
        "Access term timing. (r + s_b) x D charges the bridge for the full D years, as if all residual recovery arrived at the end, "
        "with simple interest. Receivership dividends usually come in instalments, so the term is an upper bound; under 2 bps at base.",
        "Funding spread for the funded vehicle. A fully funded vehicle has no incremental funding spread; applying s_b 1% overstates "
        f"its access cost by about {bps(lambda_q() * max(0, 1 - ADV_DIV - LGD_DEP) * S_B * D_YEARS)} bps. Kept uniform for comparability.",
        "Wrong-way haircut covers only the credit leg. When the seller fails with the reference bank the depositor also loses par at "
        f"trigger; adding the access leg would raise the pool haircut by about "
        f"{bps(lambda_q() * POOL_P_SELLER * POOL_LGD_SELLER * max(0, 1 - ADV_DIV - LGD_DEP) * (R_FREE + S_B) * D_YEARS)} bps at base.",
        "Illustrative inputs [author assumption]: pool reserve 10% (5% to 20%), reserve opportunity cost 100 bps, pool LGD_seller 50%; bank seller "
        "P(seller fails | reference fails) 5% and LGD_seller 60% (an SBLC beneficiary's claim on a failed issuer is a general creditor "
        "claim, behind deposits under depositor preference); funded vehicle 0% (fully collateralized, bankruptcy remote).",
        "Intensity versus probability. lambda is treated as a one-year default probability; at lambda_Q = 10% the Poisson probability "
        "is 9.5%, otherwise the difference is below rounding.",
        "v3 flag, tranche A premium split. The base specification gives access to the first loss, but the first loss is wiped out at failure "
        "and the bridge (recovery after the advance dividend) is owed to and carried by the senior. Access compensation therefore "
        f"belongs economically with the senior. Model follows the base specification; Section 10 shows the alternative (first loss {bps(tr_alt['fl_spread'])}, "
        f"senior {bps(tr_alt['sr_spread'])} bps). Immaterial in size (access {bps(ref['access'])} bps on notional).",
        "v3 flag, thickness = expected LGD. A first loss sized at the expected 25% leaves the senior exposed to any LGD miss, which is "
        "exactly the uncertainty the recovery-gap analysis shows. Section 10 shows the 40% thickness alternative.",
        "v3 flag, portfolio tranche points. With LGD 25% and 50 equal names one failure costs 0.5% of the portfolio, so the suggested "
        "0-3/3-7/7-100 points put the equity through six failures and leave mezzanine and senior almost untouched; I used 0-1/1-3/3-100 "
        "(two, then up to six failures) and show the suggested points as an alternative.",
        "v3 flag, LGD and clustering. The stochastic-LGD variant draws LGD independently of the common factor. In a real cluster, "
        "fire-sale asset values and heavier secured (FHLB) borrowing would push LGD up exactly when failures bunch, so the variant "
        "understates the tail. rho values are illustrative, not calibrated to bank asset correlations.",
        "v3 note, recovery gap. Returns assume a single repayment at the end of D; instalment dividends would raise the annualized "
        "return for a given price. Receivership claims typically earn no interest.",
        "max(0, 1 - a - LGD_dep) never binds in the specified sets (smallest value 10% at LGD 40%, a 50%); it would bind only if an "
        "advance dividend exceeded ultimate recovery, which the FDIC avoids by sizing advances conservatively.",
    ]
    L.extend(f"{i}. {t}" for i, t in enumerate(notes_, len(dec) + 1))
    L.append("")
    return L          # v5: Part I lines; written by write_results_v6()


# =============================================================================
# 5b. v5 PART II: PARTIALLY FUNDED MULTI-BANK VEHICLE
# =============================================================================
# --- v5 parameters (each defined once) -----------------------------------------
V5_N = 50                                  # reference banks in the pool
V5_PD_SET = [0.0025, 0.0050]               # lambda_P per name: base, alternative (author assumption)
V5_RHO_SET = [0.10, 0.20, 0.30]            # asset correlation, one-factor Gaussian copula (illustrative, not calibrated)
V5_RHO_FAIL = 0.30                         # rho for protection-failure statements and fig-07 (conservative end)
V5_RHO_MID = 0.20                          # rho for the pricing mid case
# Correlated LGD [author assumption]: z is the common factor (z < 0 is a bad state).
#   LGD(z) = 15% for z >= 0, rising linearly to 40% at z = -3 (a 1-in-741-year state), 40% below that.
V5_LGD_GOOD, V5_LGD_BAD, V5_Z_BAD = 0.15, 0.40, -3.0
# In the correlated mode the advance dividend is a fixed share of estimated recovery, a = (2/3)(1 - LGD):
# 57% at LGD 15%, 50% at 25%, 40% at 40% (inside the 30% to 60% range). FDIC sizes advances on estimated
# recovery value (public source: FDIC practice), so a falls when LGD rises [author assumption].
V5_ADV_SHARE = 2.0 / 3.0
V5_ADV_SET = [0.30, 0.50, 0.60]            # fixed-mode advance dividend: range 30% to 60%, base 50% (ADV_DIV)
V5_ADV_LAG_DAYS = 7                        # T+0 to advance dividend. Assumption from FDIC practice ("within the week")
V5_ADV_LAG_ALT = 30                        # sensitivity: a slow advance dividend [author assumption]
V5_THETA_SET = [0.05, 0.10, 0.15, 0.20]    # funded buffer in T-bills, fraction of covered notional
V5_F_SET = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]   # committed liquidity facility, fraction of covered notional
V5_CAP = 0.20                              # design rule [author assumption]: theta + F = 20%, i.e. par on 10 simultaneous failures
V5_CAP_ALT = 0.12                          # 6 simultaneous failures: a thinner alternative capacity
V5_FEE_SET = [5 * BP, 10 * BP, 20 * BP, 40 * BP]  # commitment fee on undrawn F, swept (author assumption)
V5_S_LOCK = FUND_K                         # liquidity premium on locked funds = single-name k (10 bps)
V5_S_LOCK_RANGE = FUND_K_RANGE             # 5 to 15 bps
V5_S_DRAW = 200 * BP                       # drawn margin over r on the facility [author assumption]
V5_S_DRAW_RANGE = (100 * BP, 400 * BP)     # [author assumption]
V5_FRIC = F_BASE                           # frictions: same 15 bps as the single-name vehicle (like for like)
V5_FRIC_SET = [7.5 * BP, 10 * BP, 15 * BP, 20 * BP]   # 7.5 = low sweep point
# Bank as facility provider: cost floor on the undrawn commitment (on my reading)
V5_LCR_SPE = 1.00                          # 12 CFR 249.32(e): liquidity facility to an SPE / financial sector entity
V5_FAC_CCF = 1.00                          # base: 100% CCF (author assumption; a securitization-like or credit-enhancing exposure)
V5_FAC_CCF_ALT = [0.20, 0.50]              # if treated as an ordinary commitment: <= 1 year 20%, > 1 year 50%
V5_FAC_RW = 1.00                           # unrated SPE treated as a corporate exposure
V5_FAC_RW_ALT = 0.20                       # floor if treated as a senior securitization exposure
# Facility provider wrong-way (bank provider) [author assumption]
V5_PROV_PD = 0.0010                        # provider bank's own annual PD, illustrative
V5_PROV_PD_SET = [0.0005, 0.0010, 0.0025]
V5_PROV_RHO = 0.30                         # provider loading on the same common factor
V5_PROV_RHO_SET = [0.30, 0.50]
# Fat-tail check: Student-t copula with the same rho and the same marginal PD
V5_T_NU = 5
# Monte Carlo cross-check of the exact (quadrature) results
V5_MC_YEARS = 1_000_000
V5_MC_SEED = 20261018
V5_MC_CHUNK = 100_000
V5_LOW_MARK = 31 * BP                      # a low-end reference price for the frictions-and-fee frontier
V5_F_WIDE = 0.90                           # sensitivity: facility committed on 90% of notional (theta 10%)
# Tranches of the pool's credit loss, % of covered notional [author assumption]: one failure at LGD 25% costs 0.5%, so the
# equity (0 to 1%) takes two failures, the mezzanine (1 to 3%) up to six, the funded senior runs to theta, and
# any loss above theta falls on the facility provider.
V5_TRANCHES = lambda theta: [("Equity", 0.0, 0.01), ("Mezzanine", 0.01, 0.03), ("Senior, funded", 0.03, theta),
                             ("Above the buffer (facility)", theta, 1.0)]
# Stress scenarios (section B)
V5_STRESS_N = [3, 6, 10]
V5_STRESS_LGD = [0.25, 0.40]
V5_STRESS_ADV = [0.30, 0.50]
V5_STRESS_THETA, V5_STRESS_F = 0.10, 0.10
# Yield advantage sweep (section C)
V5_DELTA_SET = [d * BP for d in range(0, 151, 25)]
# Mid case for the pooled vehicle (sections C and D): fixed LGD 25% for like-for-like with the single-name vehicle
V5_MID = dict(pd=LAMBDA_P, rho=V5_RHO_MID, mode="fixed", theta=0.10, F=0.10, fee=20 * BP)
# 2023-like timing for fig-08: two failures over one weekend, a third about seven weeks later [illustrative]
V5_TIMELINE_DAYS = [0, 2, 52]
EPS = 1e-9


# --- v5 model -------------------------------------------------------------------
def _ncdf_scalar(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))       # accurate in the far left tail


_NCDF = np.frompyfunc(_ncdf_scalar, 1, 1)


def ncdf(x):
    return np.asarray(_NCDF(np.asarray(x, dtype=float)), dtype=float)


_Z5 = np.linspace(-8, 8, Z_GRID)
_WZ5 = np.exp(-_Z5 ** 2 / 2)
_WZ5 /= _WZ5.sum()


def lgd_of_z(z, mode):
    """mode 'fixed' = LGD_DEP; a float = that fixed LGD; 'corr' = the factor-linked mapping."""
    if mode == "corr":
        return V5_LGD_GOOD + (V5_LGD_BAD - V5_LGD_GOOD) * np.clip(z / V5_Z_BAD, 0.0, 1.0)
    return np.full_like(z, LGD_DEP if mode == "fixed" else float(mode))


def adv_of(lgd, mode, a=None):
    if a is not None:
        return np.full_like(lgd, a)
    return V5_ADV_SHARE * (1.0 - lgd) if mode == "corr" else np.full_like(lgd, ADV_DIV)


def _binom_rows(p, n):
    j = np.arange(n + 1)
    coef = np.array([math.comb(n, i) for i in j], dtype=float)
    return coef[None, :] * p[:, None] ** j[None, :] * (1.0 - p[:, None]) ** (n - j)[None, :]


def _t_nodes(pd, rho, nu=V5_T_NU, nz=401, nw=240):
    """Student-t copula nodes over (z, W), W ~ chi-square(nu); returns z, weights, conditional PD."""
    s = np.linspace(math.log(1e-4), math.log(80.0), nw)               # W = exp(s)
    Wv = np.exp(s)
    dens = Wv ** (nu / 2) * np.exp(-Wv / 2)                            # chi-square pdf x Jacobian e^s (constants cancel)
    ww = dens / dens.sum()
    lo, hi = -40.0, 0.0                                                 # threshold c with E_W[Phi(c sqrt(W/nu))] = pd
    for _ in range(80):
        c = (lo + hi) / 2
        lo, hi = (c, hi) if float((ww * ncdf(c * np.sqrt(Wv / nu))).sum()) < pd else (lo, c)
    c = (lo + hi) / 2
    z = np.linspace(-8, 8, nz)
    wz = np.exp(-z ** 2 / 2)
    wz /= wz.sum()
    Zg, Wg = np.meshgrid(z, Wv, indexing="ij")
    p = ncdf((c * np.sqrt(Wg / nu) - math.sqrt(rho) * Zg) / math.sqrt(1 - rho)).ravel()
    return Zg.ravel(), (wz[:, None] * ww[None, :]).ravel(), p, c


_POOL_CACHE = {}


def pool(pd, rho, mode="fixed", a=None, copula="gauss", n_names=V5_N):
    """One year of the pool, by exact conditional integration over the common factor.
    Nodes carry: weight, conditional PD, failure-count pmf (0..n), LGD and advance dividend in that state."""
    key = (round(pd, 12), rho, mode, a, copula, n_names)
    if key in _POOL_CACHE:
        return _POOL_CACHE[key]
    if copula == "gauss":
        z, wn = _Z5, _WZ5
        p = ncdf((_ND.inv_cdf(pd) - math.sqrt(rho) * z) / math.sqrt(1 - rho))
    else:
        z, wn, p, _ = _t_nodes(pd, rho)
    lgd = lgd_of_z(z, mode)
    adv = adv_of(lgd, mode, a)
    pmf = _binom_rows(p, n_names)
    out = dict(pd=pd, rho=rho, mode=mode, z=z, w=wn, p=p, lgd=lgd, adv=adv, pmf=pmf,
               pmf_others=_binom_rows(p, n_names - 1), joint=wn[:, None] * pmf,
               W=1.0 / n_names, n=np.arange(n_names + 1)[None, :].astype(float))
    _POOL_CACHE[key] = out
    return out


def t0_cash(P, timing="simultaneous", n=None):
    """Cash the vehicle must pay at T+0. Simultaneous (design standard): all of the year's failures land inside
    one advance-dividend window, so cash = n x w. Sequential: failures more than the lag apart, so the earlier
    failures' advance dividends are back and only their term bridge is outstanding: w + (n - 1) x w x (1 - a)."""
    n = P["n"] if n is None else n
    if timing == "simultaneous":
        return n * P["W"] + 0 * P["adv"][:, None]
    return np.where(n > 0, P["W"] + (n - 1) * P["W"] * (1 - P["adv"][:, None]), 0.0)


def term_need(P, n=None):
    n = P["n"] if n is None else n
    return n * P["W"] * (1 - P["adv"][:, None])


def credit_loss(P, n=None):
    n = P["n"] if n is None else n
    return n * P["W"] * P["lgd"][:, None]


def E(P, x):
    return float((P["joint"] * x).sum())


def Pr(P, mask):
    return float((P["joint"] * mask).sum())


def Q_(P, x, q):
    return quantile(np.broadcast_to(x, P["joint"].shape).ravel(), P["joint"].ravel(), q)


def prov_pd(P, pd_s, rho_s):
    """Provider bank's conditional default probability given the common factor (Gaussian copula only)."""
    return ncdf((_ND.inv_cdf(pd_s) - math.sqrt(rho_s) * P["z"]) / math.sqrt(1 - rho_s))


def p_fail(P, theta, F, timing="simultaneous", prov=None, mac=False):
    """P(vehicle cannot pay par at T+0) = protection failure. prov = (pd_s, rho_s) lets the facility provider
    fail with the common factor; mac = True means the facility is not available in a stress year (F = 0)."""
    T0 = t0_cash(P, timing)
    if mac:
        F = 0.0
    if prov is None:
        return Pr(P, T0 > theta + F + EPS)
    ps = prov_pd(P, *prov)[:, None]
    return float((P["joint"] * ((1 - ps) * (T0 > theta + F + EPS) + ps * (T0 > theta + EPS))).sum())


def ref_cond(P, fn):
    """E[fn(n_total, P) | a given reference name fails]: weight w x p(z) x pmf of the other n - 1 names."""
    n_tot = np.arange(1, P["pmf_others"].shape[1] + 1)[None, :].astype(float)
    jw = P["w"][:, None] * P["p"][:, None] * P["pmf_others"]
    return float((jw * fn(n_tot, P)).sum() / jw.sum())


def unpaid_share(n, P, theta, F, prov=None):
    """Pro rata unpaid share of par across the failed names (simultaneous standard)."""
    T0 = n * P["W"]
    short = np.clip(T0 - theta - F, 0, None)
    if prov is not None:
        ps = prov_pd(P, *prov)[:, None]
        short = (1 - ps) * short + ps * np.clip(T0 - theta, 0, None)
    return np.where(T0 > 0, short / np.where(T0 > 0, T0, 1), 0.0)


def depositor_haircut(P, theta, F, prov=None):
    """Expected annual value lost by protected depositors because par is not paid in full (per unit of covered
    notional): E[unpaid amount x LGD]. A depositor who is not paid holds the deposit claim and bears LGD."""
    n = P["n"]
    T0 = n * P["W"]
    return E(P, unpaid_share(n, P, theta, F, prov) * T0 * P["lgd"][:, None])


def pool_price(pd=LAMBDA_P, rho=V5_RHO_MID, mode="fixed", theta=0.10, F=0.10, fee=20 * BP, f=V5_FRIC,
               s_lock=V5_S_LOCK, s_draw=V5_S_DRAW, a=None, mu=MU, d=D_YEARS, lag=V5_ADV_LAG_DAYS,
               copula="gauss", n_names=V5_N, r=None):
    """c*_pool = credit_Q + access_Q + theta s_lock + F fee_F + expected drawn cost (Q) + f. r defaults to R_FREE."""
    r = R_FREE if r is None else r
    Qd = pool(min(mu * pd, 0.999), rho, mode, a, copula, n_names)
    n = Qd["n"]
    T0 = t0_cash(Qd)
    credit = E(Qd, credit_loss(Qd))
    access = E(Qd, n * Qd["W"] * np.clip(1 - Qd["adv"][:, None] - Qd["lgd"][:, None], 0, None)) * (r + S_B) * d
    draw0 = E(Qd, np.clip(T0 - theta, 0, F))                    # drawn from T+0 until the advance dividend
    termout = E(Qd, np.clip(term_need(Qd) - theta, 0, F))       # still drawn after the advance dividend, for up to D
    drawn = draw0 * (r + s_draw) * lag / 365 + termout * max(0.0, s_draw - S_B) * d
    lock, commit = theta * s_lock, F * fee
    k = lock + commit + drawn
    return dict(credit=credit, access=access, lock=lock, commit=commit, drawn=drawn, k=k, f=f,
                c_star=credit + access + k + f, draw0=draw0, termout=termout,
                el_above=E(Qd, np.clip(credit_loss(Qd) - theta, 0, None)))


def bisect_lp(fn, target, lo=1e-6, hi=0.20, it=60):
    if fn(lo) >= target:
        return None
    for _ in range(it):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if fn(mid) < target else (lo, mid)
    return (lo + hi) / 2


# --- v5 results ---------------------------------------------------------------------
SINGLE = ref["c_star"]                               # single-name funded vehicle c*
BANK_FAC_LCR = V5_LCR_SPE * HQLA_CARRY
fac_capital = lambda ccf=V5_FAC_CCF, rw=V5_FAC_RW: ccf * rw * CET1_RATIO * (HURDLE - R_FREE)
bank_fee_floor = {"base": BANK_FAC_LCR + fac_capital(),
                  "ccf20": BANK_FAC_LCR + fac_capital(ccf=0.20), "ccf50": BANK_FAC_LCR + fac_capital(ccf=0.50),
                  "rw20": BANK_FAC_LCR + fac_capital(rw=V5_FAC_RW_ALT)}
BANK_FEE_LO, BANK_FEE_HI = min(bank_fee_floor.values()), max(bank_fee_floor.values())

# A1: LGD mapping and default-weighted LGD
lgd_map_rows = []
for zq in [1.0, 0.0, -1.0, -1.5, -2.0, -2.5, -3.0, -3.5]:
    lg = float(lgd_of_z(np.array([zq]), "corr")[0])
    lgd_map_rows.append((zq, _ncdf_scalar(zq), lg, V5_ADV_SHARE * (1 - lg)))
lgd_dw = {}
for pd in V5_PD_SET + [MU * LAMBDA_P]:
    for rho in V5_RHO_SET:
        P_ = pool(pd, rho, "corr")
        lgd_dw[(pd, rho)] = (E(P_, P_["n"] * P_["lgd"][:, None]) / E(P_, P_["n"]),
                             E(P_, P_["n"] * P_["adv"][:, None]) / E(P_, P_["n"]))

# A2: cash needs by year
cash = {}
for pd in V5_PD_SET:
    for rho in V5_RHO_SET:
        for mode in ("fixed", "corr"):
            P_ = pool(pd, rho, mode)
            T0, TN, CL = t0_cash(P_), term_need(P_), credit_loss(P_)
            cash[(pd, rho, mode)] = dict(
                p1=Pr(P_, P_["n"] >= 1), p3=Pr(P_, P_["n"] >= 3), e_n=E(P_, P_["n"]),
                t0=(E(P_, T0), Q_(P_, T0, 0.995), Q_(P_, T0, 0.999)),
                tn=(E(P_, TN), Q_(P_, TN, 0.995), Q_(P_, TN, 0.999)),
                cl=(E(P_, CL), Q_(P_, CL, 0.995), Q_(P_, CL, 0.999)))

# A3: outcomes by theta (rho 0.30, PD 0.25%, both LGD modes), F by the 20% design rule
outcomes = {}
for pd in V5_PD_SET:
    for mode in ("fixed", "corr"):
        P_ = pool(pd, V5_RHO_FAIL, mode)
        T0 = t0_cash(P_)
        p_any = Pr(P_, P_["n"] >= 1)
        for th in V5_THETA_SET:
            F_ = max(0.0, V5_CAP - th)
            outcomes[(pd, mode, th)] = dict(
                F=F_, suff=Pr(P_, T0 <= th + EPS), suff_c=(Pr(P_, (T0 <= th + EPS) & (P_["n"] >= 1)) / p_any),
                drawn=Pr(P_, T0 > th + EPS), fail=p_fail(P_, th, F_), fail0=p_fail(P_, th, 0.0),
                termout=Pr(P_, term_need(P_) > th + EPS), insolv=Pr(P_, credit_loss(P_) > th + EPS),
                drawn_q=Pr(pool(MU * pd, V5_RHO_FAIL, mode), t0_cash(pool(MU * pd, V5_RHO_FAIL, mode)) > th + EPS))

# A4: vehicle effective default probability: theta x F
vpd = {}
for pd in V5_PD_SET:
    P_ = pool(pd, V5_RHO_FAIL, "corr")
    for th in V5_THETA_SET:
        for F_ in V5_F_SET:
            vpd[(pd, th, F_)] = p_fail(P_, th, F_)
cap_list = [0.06, 0.10, 0.12, 0.16, 0.20, 0.30]
vpd_rho = {}
for rho in V5_RHO_SET:
    for pd in V5_PD_SET:
        P_ = pool(pd, rho, "corr")
        for c in cap_list:
            vpd_rho[(rho, pd, c, "sim")] = p_fail(P_, c, 0.0)
            vpd_rho[(rho, pd, c, "seq")] = p_fail(P_, c, 0.0, timing="sequential")
vpd_t = {(pd, c): p_fail(pool(pd, V5_RHO_FAIL, "fixed", copula="t"), c, 0.0) for pd in V5_PD_SET for c in cap_list}
vpd_ind = {(pd, c): float(sum(math.comb(V5_N, i) * pd ** i * (1 - pd) ** (V5_N - i)
                              for i in range(V5_N + 1) if i * (1.0 / V5_N) > c + EPS)) for pd in V5_PD_SET for c in cap_list}
# conditional on the depositor's own bank failing
vpd_cond = {}
for pd in V5_PD_SET:
    P_ = pool(pd, V5_RHO_FAIL, "corr")
    for c in cap_list:
        vpd_cond[(pd, c)] = ref_cond(P_, lambda n, PP, c=c: (n * PP["W"] > c + EPS).astype(float))
        vpd_cond[(pd, c, "unpaid")] = ref_cond(P_, lambda n, PP, c=c: unpaid_share(n, PP, c, 0.0))

# A5: facility provider wrong-way (bank provider), at the design rule
wwy = {}
P_fail_base = pool(LAMBDA_P, V5_RHO_FAIL, "corr")
for th in V5_THETA_SET:
    F_ = max(0.0, V5_CAP - th)
    row = dict(F=F_, none=p_fail(P_fail_base, th, F_), mac=p_fail(P_fail_base, th, F_, mac=True),
               hc_none=depositor_haircut(P_fail_base, th, F_),
               cond_none=ref_cond(P_fail_base, lambda n, PP, th=th, F_=F_: (n * PP["W"] > th + F_ + EPS).astype(float)))
    for pds in V5_PROV_PD_SET:
        for rs in V5_PROV_RHO_SET:
            row[(pds, rs)] = p_fail(P_fail_base, th, F_, prov=(pds, rs))
    prov = (V5_PROV_PD, V5_PROV_RHO)
    row["hc_bank"] = depositor_haircut(P_fail_base, th, F_, prov=prov)
    row["cond_bank"] = ref_cond(P_fail_base, lambda n, PP, th=th, F_=F_: (
        (1 - prov_pd(PP, *prov)[:, None]) * (n * PP["W"] > th + F_ + EPS) + prov_pd(PP, *prov)[:, None] * (n * PP["W"] > th + EPS)))
    ps = prov_pd(P_fail_base, *prov)[:, None]
    drawn_mask = t0_cash(P_fail_base) > th + EPS
    row["ps_given_drawn"] = float((P_fail_base["joint"] * drawn_mask * ps).sum()) / max(Pr(P_fail_base, drawn_mask), 1e-300)
    wwy[th] = row
prov_uncond = V5_PROV_PD

# A6: pricing
mid = pool_price(**V5_MID)
mid_corr = pool_price(**{**V5_MID, "mode": "corr"})
price_grid = {}
for cap in (V5_CAP, V5_CAP_ALT):
    for th in V5_THETA_SET:
        F_ = max(0.0, cap - th)
        for fee in V5_FEE_SET + [BANK_FEE_LO, BANK_FEE_HI]:
            price_grid[(cap, th, fee)] = pool_price(theta=th, F=F_, fee=fee)
breakeven_fee = {}
for cap in (V5_CAP, V5_CAP_ALT):
    for th in V5_THETA_SET:
        F_ = max(0.0, cap - th)
        for fr in V5_FRIC_SET:
            c0 = pool_price(theta=th, F=F_, fee=0.0, f=fr)["c_star"]
            breakeven_fee[(cap, th, fr)] = None if F_ == 0 else (SINGLE - c0) / F_
            breakeven_fee[(cap, th, fr, "c0")] = c0
mid_sens = {}
for rho in V5_RHO_SET:
    for pd in V5_PD_SET:
        for mode in ("fixed", "corr"):
            mid_sens[(rho, pd, mode)] = pool_price(**{**V5_MID, "rho": rho, "pd": pd, "mode": mode})["c_star"]
single_corr = {rho: lgd_dw[(MU * LAMBDA_P, rho)][0] * MU * LAMBDA_P for rho in V5_RHO_SET}   # credit term only

# Facility on 90% of notional (theta 10%), and the frictions-and-fee frontier at theta 10%, F 10%
wide = [("F 90% at a 20 bps non-bank fee", pool_price(theta=0.10, F=V5_F_WIDE, fee=20 * BP)["c_star"]),
        ("F 90% at the bank cost floor (low)", pool_price(theta=0.10, F=V5_F_WIDE, fee=BANK_FEE_LO)["c_star"]),
        ("F 90% at the bank cost floor (high)", pool_price(theta=0.10, F=V5_F_WIDE, fee=BANK_FEE_HI)["c_star"]),
        ("F sized to need (10%), 20 bps non-bank fee", pool_price(theta=0.10, F=0.10, fee=20 * BP)["c_star"]),
        ("F 10% at the bank cost floor (high)", pool_price(theta=0.10, F=0.10, fee=BANK_FEE_HI)["c_star"]),
        ("F 10%, 20 bps fee, f 7.5 bps (low frictions sweep point)", pool_price(theta=0.10, F=0.10, fee=20 * BP, f=7.5 * BP)["c_star"])]
wide_fail = dict(none=p_fail(P_fail_base, 0.10, V5_F_WIDE),
                 bank=p_fail(P_fail_base, 0.10, V5_F_WIDE, prov=(V5_PROV_PD, V5_PROV_RHO)),
                 six=p_fail(P_fail_base, 0.10, V5_CAP_ALT - 0.10),
                 mac=p_fail(P_fail_base, 0.10, V5_F_WIDE, mac=True))
c_no_fee_no_f = pool_price(theta=0.10, F=0.10, fee=0.0, f=0.0)["c_star"]

# A7: trade-off of designs
designs = [
    ("Single-name, fully funded (v4)", None, None, None),
    ("Pool, theta 20%, no facility", 0.20, 0.0, 0.0),
    ("Pool, theta 10%, F 10%, non-bank 20 bps", 0.10, 0.10, 20 * BP),
    ("Pool, theta 10%, F 10%, bank floor (high)", 0.10, 0.10, BANK_FEE_HI),
    ("Pool, theta 5%, F 15%, non-bank 20 bps", 0.05, 0.15, 20 * BP),
    ("Pool, theta 10%, F 2% (6 failures), 20 bps", 0.10, 0.02, 20 * BP),
    ("Pool, theta 10%, no facility", 0.10, 0.0, 0.0),
]
tradeoff = []
for name, th, F_, fee in designs:
    if th is None:
        tradeoff.append(dict(name=name, c=SINGLE, fail=0.0, fail_bank=None, cond=0.0, hc=0.0))
        continue
    c = pool_price(theta=th, F=F_, fee=fee, f=V5_FRIC)["c_star"]
    is_bank = "bank" in name
    prov = (V5_PROV_PD, V5_PROV_RHO)
    tradeoff.append(dict(
        name=name, c=c, fail=p_fail(P_fail_base, th, F_),
        fail_bank=p_fail(P_fail_base, th, F_, prov=prov) if F_ > 0 else None,
        cond=ref_cond(P_fail_base, lambda n, PP, th=th, F_=F_: (n * PP["W"] > th + F_ + EPS).astype(float)),
        hc=depositor_haircut(P_fail_base, th, F_, prov=prov if (is_bank and F_ > 0) else None)))

# A8: tranches of pool credit loss (theta 10%)
tranche_v6 = {}
for rho in V5_RHO_SET:
    for mode in ("fixed", "corr"):
        Pp, Qq = pool(LAMBDA_P, rho, mode), pool(MU * LAMBDA_P, rho, mode)
        lp_, pp_ = np.broadcast_to(credit_loss(Pp), Pp["joint"].shape).ravel(), Pp["joint"].ravel()
        lq_, pq_ = np.broadcast_to(credit_loss(Qq), Qq["joint"].shape).ravel(), Qq["joint"].ravel()
        trs = V5_TRANCHES(0.10)
        tranche_v6[(rho, mode)] = list(zip(trs, tranche_stats(lp_, pp_, trs), tranche_stats(lq_, pq_, trs)))
# check: thickness-weighted Q-EL across tranches = credit term
tranche_check = {k_: sum((tr[2] - tr[1]) * q["el"] for tr, _, q in v) for k_, v in tranche_v6.items()}

# B: deterministic stress
stress = []
for n_ in V5_STRESS_N:
    for lg in V5_STRESS_LGD:
        for a_ in V5_STRESS_ADV:
            th, F_, w_ = V5_STRESS_THETA, V5_STRESS_F, 1.0 / V5_N
            t0 = n_ * w_
            tn = t0 * (1 - a_)
            loss = t0 * lg
            stress.append(dict(n=n_, lgd=lg, a=a_, t0=t0, buf=min(th, t0), fac=min(F_, max(0.0, t0 - th)),
                               short=max(0.0, t0 - th - F_), seq=w_ + (n_ - 1) * w_ * (1 - a_), term=tn,
                               termout=max(0.0, tn - th), loss=loss, buf_left=th - loss, fac_loss=max(0.0, loss - th),
                               cap_next=max(0.0, th - tn), need_F=max(0.0, t0 - th)))

# C: yield advantage sweep
costs_c = {
    "Self-insured (credit + access)": lambda lp: self_insured(lambda_p=lp),
    "Single-name funded vehicle": lambda lp: components(lambda_p=lp, k=FUND_K, f=FUND_F)["c_star"],
    "Pooled vehicle, mid case": lambda lp: pool_price(**{**V5_MID, "pd": lp})["c_star"],
    "Bank SBLC": lambda lp: bank_prices(lambda_p=lp)["all_in"],
}
cost_base = {k_: fn(LAMBDA_P) for k_, fn in costs_c.items()}
be_c = {k_: {d_: bisect_lp(fn, d_) for d_ in V5_DELTA_SET} for k_, fn in costs_c.items()}

# D: who pays (per unit of balance, relative to the outside-option yield y)
WHO_DELTA = [0, 50 * BP, 100 * BP]                    # sweep values, not estimates
who_c = mid["c_star"]


# --- Monte Carlo cross-check (latent-variable simulation, independent of the quadrature) -------------------
def _mc(pd, rho, mode, copula="gauss", years=V5_MC_YEARS, seed=V5_MC_SEED):
    rng5 = np.random.default_rng(seed)
    c_g = _ND.inv_cdf(pd)
    c_t = _t_nodes(pd, rho)[3] if copula == "t" else None
    counts, zs = [], []
    done = 0
    while done < years:
        m = min(V5_MC_CHUNK, years - done)
        z = rng5.standard_normal(m)
        eps_ = rng5.standard_normal((m, V5_N))
        x = math.sqrt(rho) * z[:, None] + math.sqrt(1 - rho) * eps_
        if copula == "t":
            wv = rng5.chisquare(V5_T_NU, m)
            x = x * np.sqrt(V5_T_NU / wv)[:, None]
            counts.append((x < c_t).sum(axis=1))
        else:
            counts.append((x < c_g).sum(axis=1))
        zs.append(z)
        done += m
    n = np.concatenate(counts).astype(float)
    z = np.concatenate(zs)
    lgd = lgd_of_z(z, mode)
    adv = adv_of(lgd, mode)
    w_ = 1.0 / V5_N
    t0, tn, cl = n * w_, n * w_ * (1 - adv), n * w_ * lgd
    return dict(n=n, p3=float((n >= 3).mean()), p6=float((n >= 6).mean()), p11=float((n >= 11).mean()),
                e_t0=float(t0.mean()), q_t0=(float(np.quantile(t0, 0.995)), float(np.quantile(t0, 0.999))),
                q_tn=(float(np.quantile(tn, 0.995)), float(np.quantile(tn, 0.999))),
                e_cl=float(cl.mean()), q_cl=(float(np.quantile(cl, 0.995)), float(np.quantile(cl, 0.999))),
                fail_10_10=float((t0 > 0.20 + EPS).mean()), drawn_10=float((t0 > 0.10 + EPS).mean()),
                termout_10=float((tn > 0.10 + EPS).mean()))


mc5 = _mc(LAMBDA_P, V5_RHO_FAIL, "corr")
mc5_t = _mc(LAMBDA_P, V5_RHO_FAIL, "fixed", copula="t", seed=V5_MC_SEED + 1)
P_chk = pool(LAMBDA_P, V5_RHO_FAIL, "corr")
P_chk_t = pool(LAMBDA_P, V5_RHO_FAIL, "fixed", copula="t")
exact_chk = dict(p3=Pr(P_chk, P_chk["n"] >= 3), p6=Pr(P_chk, P_chk["n"] >= 6), p11=Pr(P_chk, P_chk["n"] >= 11),
                 e_t0=E(P_chk, t0_cash(P_chk)), q_t0=(cash[(LAMBDA_P, V5_RHO_FAIL, "corr")]["t0"][1:]),
                 q_tn=cash[(LAMBDA_P, V5_RHO_FAIL, "corr")]["tn"][1:], e_cl=cash[(LAMBDA_P, V5_RHO_FAIL, "corr")]["cl"][0],
                 q_cl=cash[(LAMBDA_P, V5_RHO_FAIL, "corr")]["cl"][1:], fail_10_10=p_fail(P_chk, 0.10, 0.10),
                 drawn_10=Pr(P_chk, t0_cash(P_chk) > 0.10 + EPS), termout_10=Pr(P_chk, term_need(P_chk) > 0.10 + EPS))
exact_chk_t = dict(p3=Pr(P_chk_t, P_chk_t["n"] >= 3), p6=Pr(P_chk_t, P_chk_t["n"] >= 6), p11=Pr(P_chk_t, P_chk_t["n"] >= 11))


# --- F: challenge register sensitivities ---------------------------------------------------------
# Reference points: price = mid case (theta 10%, F 10%, 20 bps, rho 0.20, LGD 25%); protection failure =
# P(cannot pay par), theta 10% + F 10%, rho 0.30, correlated LGD, simultaneous standard, PD 0.25%.
CR_C0 = mid["c_star"]
CR_P0 = p_fail(P_fail_base, 0.10, 0.10)
_cp = lambda **kw: pool_price(**{**V5_MID, **kw})["c_star"]
_pf = lambda pd=LAMBDA_P, rho=V5_RHO_FAIL, mode="corr", th=0.10, F=0.10, **kw: p_fail(
    pool(pd, rho, mode, kw.pop("a", None), kw.pop("copula", "gauss"), kw.pop("n_names", V5_N)), th, F, **kw)
cr = {}
cr["pd"] = (_cp(pd=0.005), _pf(pd=0.005))
cr["rho"] = (_cp(rho=0.10), _cp(rho=0.30), _pf(rho=0.10), _pf(rho=0.20))
cr["t"] = (_cp(copula="t"), _pf(mode="fixed", copula="t"))
cr["lgd"] = (mid_corr["c_star"], _cp(mode=0.40),
             Pr(pool(LAMBDA_P, V5_RHO_FAIL, "fixed"), credit_loss(pool(LAMBDA_P, V5_RHO_FAIL, "fixed")) > 0.10 + EPS),
             Pr(P_fail_base, credit_loss(P_fail_base) > 0.10 + EPS),
             Pr(pool(LAMBDA_P, V5_RHO_FAIL, 0.40), credit_loss(pool(LAMBDA_P, V5_RHO_FAIL, 0.40)) > 0.10 + EPS))
_Pa = {a_: pool(LAMBDA_P, V5_RHO_FAIL, "fixed", a_) for a_ in (0.0, 0.30, 0.50, 0.60)}
cr["adv"] = (_cp(a=0.30), _cp(a=0.60), _cp(a=0.0),
             {a_: Pr(P_, term_need(P_) > 0.10 + EPS) for a_, P_ in _Pa.items()},
             {a_: p_fail(P_, 0.10, 0.10, timing="sequential") for a_, P_ in _Pa.items() if a_ > 0})
cr["lag"] = (_cp(lag=V5_ADV_LAG_ALT),)
cr["D"] = (_cp(d=1), _cp(d=3))
cr["conc"] = (_cp(n_names=25), _pf(n_names=25), _pf(n_names=25, mode="fixed"))
cr["timing"] = (_pf(timing="sequential"),)
cr["theta"] = (_cp(theta=0.05, F=0.15), _cp(theta=0.20, F=0.0), _pf(th=0.10, F=0.02), _pf(th=0.10, F=0.20))
cr["fee"] = (_cp(fee=5 * BP), _cp(fee=40 * BP), _cp(fee=BANK_FEE_LO), _cp(fee=BANK_FEE_HI))
cr["lock"] = (_cp(s_lock=V5_S_LOCK_RANGE[0]), _cp(s_lock=V5_S_LOCK_RANGE[1]))
cr["draw"] = (_cp(s_draw=V5_S_DRAW_RANGE[0]), _cp(s_draw=V5_S_DRAW_RANGE[1]))
cr["fric"] = (_cp(f=10 * BP), _cp(f=20 * BP))   # frictions floor 10 bps (author choice)
cr["mu"] = (_cp(mu=2), _cp(mu=5))
cr["prov"] = (_pf(prov=(V5_PROV_PD, V5_PROV_RHO)), _pf(prov=(V5_PROV_PD, 0.50)), _pf(prov=(0.0025, V5_PROV_RHO)))
cr["mac"] = (_pf(mac=True),)
cr["replen"] = (_pf(th=0.10 - 3 * (1.0 / V5_N) * (1 - ADV_DIV)), _pf(th=0.10 - 6 * (1.0 / V5_N) * (1 - ADV_DIV)))


# --- v5 results writer -----------------------------------------------------------------------------
def fp(x):
    """Probability as a percent, with enough digits for a tail."""
    if x is None:
        return "n/a"
    if x <= 0:
        return "0"
    if x >= 0.001:
        return f"{x * 100:.2f}%"
    if x >= 1e-6:
        return f"{x * 100:.4f}%"
    return "< 0.0001%"


def one_in(x):
    return "never" if x <= 0 else f"1 in {1 / x:,.0f}"


def pc(x, nd=1):
    return f"{x * 100:.{nd}f}%"


def b1(x):
    return f"{x / BP + 1e-9:.1f}"


def pel(x):
    """Tranche loss rate as % of tranche; scientific notation below 0.001%."""
    return f"{x * 100:.3f}%" if x * 100 >= 0.001 else ("0" if x <= 0 else f"{x * 100:.1e}%")


def write_results_v6():
    L1 = write_results()                              # Part I: v4 lines, unchanged
    L = ["# The clearing cost of an uninsured deposit: model results (v5)\n",
         f"Generated by `{SCRIPT_NAME}` (run with `python3 -I`). Every number below is computed by that script; edit "
         "parameters there, not here. Units: bps per year on the covered balance unless stated. Rounding: whole bps, one "
         "decimal below 5 bps (Part I); one decimal in Part II price tables. Parameters are illustrative author assumptions "
         "unless a public source is cited; the design parameters flagged in Section 28 are judgments.\n",
         "**Part I (Sections 1 to 15)** is the single-name model (code unchanged since v4). "
         "**Part II (Sections 16 to 29)** is the partially funded multi-bank vehicle (code unchanged since v5): "
         "stress scenarios, the yield-advantage sweep, who pays, and a challenge register.\n",
         "---\n", "# Part I. The single-name model\n"]
    L += L1[2:]
    L.append("---\n")
    L.append("# Part II. A partially funded multi-bank vehicle\n")

    # 16. Design
    L.append("## 16. Design, cash timing and conventions\n")
    L.append(f"The vehicle writes protection on {V5_N} reference banks, each capped at {pc(1 / V5_N, 0)} of covered notional "
             "(one failure = a par payment of 2% of the pool). Failures follow a one-factor Gaussian copula with asset "
             "correlation rho; z is the common factor and a low z is a bad year for every bank at once.\n")
    L.append("Cash timing on one failure, per unit of that bank's covered balance:\n")
    L.append(table(["When", "Cash", "Source"], [
        ["T+0 (failure, receiver appointed, usually a Friday)", "vehicle pays par: 1", "design"],
        [f"T+0 + about {V5_ADV_LAG_DAYS} days", "advance dividend a comes back (base 50%, range 30% to 60%)",
         "assumption based on FDIC practice: advance dividends since 1984; IndyMac 50%; SVB announcement said 'within the week'"],
        ["Over D years (base 2, range 1 to 3)", "remaining recovery 1 - a - LGD comes back", "author assumption"],
        ["Never", "LGD is the final loss", "author assumption"],
    ]))
    L.append("\nLiabilities and waterfall. (1) A funded buffer theta, invested in T-bills, pays par first and is the first "
             "loss; it also carries the term bridge after the advance dividend. (2) A committed liquidity facility F is "
             "drawn at T+0 only for the par payments above the buffer, and is repaid from the advance dividends. "
             "(3) If the advance dividends do not repay it (term need n w (1 - a) above theta), the facility terms out for up "
             "to D years, secured on the receivership claims; it takes a credit loss only if the pool's credit loss exceeds "
             "theta. (4) If T+0 cash exceeds theta + F the vehicle cannot pay par: **protection failure**. Shortfalls are "
             "shared pro rata across the failed names in the window; an unpaid depositor keeps its deposit claim and bears LGD on "
             "the unpaid share.\n")
    L.append("Design standard for timing: **simultaneous**. All of a year's failures are assumed to land inside one advance-"
             "dividend window, so T+0 cash = n x 2%. This is the conservative bound; spring 2023 had two failures over one "
             "weekend. The sequential alternative (failures more than a week apart, so earlier advance dividends are back) "
             "needs w + (n - 1) w (1 - a) at the last failure and is shown as a sensitivity.\n")
    L.append("Measures. Protection-failure, facility-draw and vehicle-default probabilities are real-world (P) probabilities "
             "at lambda_P. Prices are under Q: the same copula run at mu x lambda_P per name (same rho, same LGD mapping), "
             f"which with a fixed LGD gives exactly the single-name credit ({ref['credit'] / BP:.2f} bps) and access ({ref['access'] / BP:.2f} bps) terms. "
             "Probabilities are exact (quadrature over z, 4,001 points; Student-t variant over a 401 x 240 grid in (z, W)); "
             f"a seeded latent-variable Monte Carlo ({V5_MC_YEARS:,} years, seed {V5_MC_SEED}) checks them in Section 18.\n")
    L.append("Pricing. k_pool = theta x s_lock + F x fee_F + expected drawn cost; c*_pool = credit_Q + access_Q + k_pool + f. "
             "Expected drawn cost = E_Q[T+0 draw] x (r + s_draw) x lag / 365 + E_Q[term-out] x (s_draw - s_b) x D; the r part of "
             "the term-out is already in the access term. The facility's share of credit loss (loss above theta) is part of "
             "the credit term, not an extra charge.\n")
    L.append(table(["Parameter", "Base", "Range / set", "Source"], [
        ["Reference banks; cap per bank", f"{V5_N}; {pc(1 / V5_N, 0)}", "25 banks at 4% (Section 28)", "design choice"],
        ["lambda_P per bank", pc(LAMBDA_P, 2), ", ".join(pc(x, 2) for x in V5_PD_SET), "author assumption"],
        ["Asset correlation rho", f"{V5_RHO_MID:.2f} (price); {V5_RHO_FAIL:.2f} (failure)", ", ".join(f"{r:.2f}" for r in V5_RHO_SET),
         "author assumption; illustrative, not calibrated"],
        ["LGD_dep", "fixed 25% or correlated 15% to 40%", "fixed 40% stress", "author assumption; mapping [author assumption], Section 17"],
        ["Advance dividend a", "50% (correlated mode: (2/3)(1 - LGD))", "30% to 60%; 0 as a failure mode", "FDIC practice (public source); link [author assumption]"],
        ["T+0 to advance dividend", f"{V5_ADV_LAG_DAYS} days", f"{V5_ADV_LAG_ALT} days", "assumption from FDIC practice"],
        ["D", f"{D_YEARS:g} years", "1 to 3", "author assumption"],
        ["Funded buffer theta", "10%", ", ".join(pc(x, 0) for x in V5_THETA_SET), "design choice"],
        ["Facility F", f"theta + F = {pc(V5_CAP, 0)} (10 failures)", ", ".join(pc(x, 0) for x in V5_F_SET) + f"; {pc(V5_CAP_ALT, 0)} rule",
         "design rule [author assumption]"],
        ["fee_F on undrawn F", "20 bps (non-bank mid)", "5, 10, 20, 40; bank floor " + f"{b1(BANK_FEE_LO)} to {b1(BANK_FEE_HI)}",
         "author assumption (sweep); bank floor Section 20"],
        ["s_lock on the buffer", bps(V5_S_LOCK) + " bps", "5 to 15", "= single-name k (author assumption)"],
        ["Drawn margin s_draw over r", bps(V5_S_DRAW) + " bps", "100 to 400", "illustrative [author assumption]"],
        ["Frictions f", bps(V5_FRIC) + " bps", "7.5, 10, 15, 20", "author assumption (7.5 = low sweep point)"],
        ["Bank facility provider PD; rho", f"{pc(V5_PROV_PD, 2)}; {V5_PROV_RHO:.2f}", "0.05% to 0.25%; 0.30 to 0.50", "illustrative [author assumption]"],
    ]))
    L.append("")

    # 17. LGD mapping
    L.append("## 17. A1. Correlated LGD and the advance dividend\n")
    L.append("Mapping [author assumption]: LGD(z) = 15% for z >= 0, rising linearly to 40% at z = -3, flat at 40% below. In the correlated "
             "mode the advance dividend is two thirds of estimated recovery, a = (2/3)(1 - LGD), because the FDIC sizes "
             "advances on estimated recovery value; it therefore falls in bad states. Rationale: fire-sale asset values and "
             "heavier secured (FHLB) borrowing in a cluster push LGD up exactly when failures bunch (12 U.S.C. 1430(e) puts the "
             "FHLB ahead of the receiver).\n")
    L.append(table(["Common factor z", "P(Z <= z): how rare the year is", "LGD", "Advance dividend a"],
                   [[f"{zq:+.1f}", pc(pz, 2) if pz > 0.001 else fp(pz), pc(lg, 0), pc(av, 0)] for zq, pz, lg, av in lgd_map_rows]))
    L.append("\nDefault-weighted mean LGD and advance dividend (what the average failed bank looks like):\n")
    L.append(table(["Measure, per-bank PD", "rho 0.10", "rho 0.20", "rho 0.30"],
                   [[f"{'Q' if abs(pd - MU * LAMBDA_P) < 1e-12 else 'P'}, {pc(pd, 2)}"] +
                    [f"LGD {pc(lgd_dw[(pd, r)][0])}, a {pc(lgd_dw[(pd, r)][1])}" for r in V5_RHO_SET]
                    for pd in V5_PD_SET + [MU * LAMBDA_P]]))
    L.append("\nThe mapping is roughly level-neutral at rho 0.10 to 0.20 (mean near 25%) and adds a level effect at 0.30. The "
             "credit term under Q moves from 18.75 bps (fixed 25%) to "
             + ", ".join(f"{b1(single_corr[r])} at rho {r:.2f}" for r in V5_RHO_SET)
             + " bps; the same shift applies to the single-name vehicle, so it does not change the pooled-versus-single comparison.\n")

    # 18. cash needs
    L.append("## 18. A2. Cash needs in a year: T+0 cash, term funding and credit loss\n")
    L.append("Percent of covered notional; P measure; simultaneous standard. T+0 cash does not depend on LGD or a. Term "
             "funding is the cash still out after advance dividends, n w (1 - a); credit loss is n w LGD.\n")
    rows = []
    for pd in V5_PD_SET:
        for rho in V5_RHO_SET:
            cf, cc = cash[(pd, rho, "fixed")], cash[(pd, rho, "corr")]
            rows.append([f"{pc(pd, 2)}, rho {rho:.2f}", fp(cf["p1"]), fp(cf["p3"]),
                         f"{pc(cf['t0'][0], 2)} / {pc(cf['t0'][1], 0)} / {pc(cf['t0'][2], 0)}",
                         f"{pc(cf['tn'][0], 3)} / {pc(cf['tn'][1])} / {pc(cf['tn'][2])}",
                         f"{pc(cc['tn'][0], 3)} / {pc(cc['tn'][1])} / {pc(cc['tn'][2])}",
                         f"{pc(cf['cl'][0], 3)} / {pc(cf['cl'][1])} / {pc(cf['cl'][2])}",
                         f"{pc(cc['cl'][0], 3)} / {pc(cc['cl'][1])} / {pc(cc['cl'][2])}"])
    L.append(table(["lambda_P, rho", "P(1+ failures)", "P(3+ failures)", "T+0 cash: mean / 99.5th / 99.9th",
                    "Term funding mean / 99.5th / 99.9th (fixed)", "Term funding mean / 99.5th / 99.9th (correlated)",
                    "Credit loss mean / 99.5th / 99.9th (fixed)", "Credit loss mean / 99.5th / 99.9th (correlated)"], rows))
    L.append("\nMonte Carlo check (rho 0.30, lambda_P 0.25%, correlated LGD; latent variables for all 50 banks; "
             f"{V5_MC_YEARS:,} years):\n")
    L.append(table(["Statistic", "Exact", "Monte Carlo"], [
        ["P(3+ failures)", fp(exact_chk["p3"]), fp(mc5["p3"])],
        ["P(6+ failures) = P(facility drawn at theta 10%)", fp(exact_chk["p6"]), fp(mc5["p6"])],
        ["P(11+ failures) = P(cannot pay par at theta 10% + F 10%)", fp(exact_chk["p11"]), fp(mc5["p11"])],
        ["Mean T+0 cash", pc(exact_chk["e_t0"], 3), pc(mc5["e_t0"], 3)],
        ["T+0 cash 99.5th / 99.9th", f"{pc(exact_chk['q_t0'][0], 0)} / {pc(exact_chk['q_t0'][1], 0)}",
         f"{pc(mc5['q_t0'][0], 0)} / {pc(mc5['q_t0'][1], 0)}"],
        ["Term funding 99.5th / 99.9th", f"{pc(exact_chk['q_tn'][0], 2)} / {pc(exact_chk['q_tn'][1], 2)}",
         f"{pc(mc5['q_tn'][0], 2)} / {pc(mc5['q_tn'][1], 2)}"],
        ["Mean credit loss", pc(exact_chk["e_cl"], 4), pc(mc5["e_cl"], 4)],
        ["Credit loss 99.5th / 99.9th", f"{pc(exact_chk['q_cl'][0], 2)} / {pc(exact_chk['q_cl'][1], 2)}",
         f"{pc(mc5['q_cl'][0], 2)} / {pc(mc5['q_cl'][1], 2)}"],
        ["P(term funding above a 10% buffer)", fp(exact_chk["termout_10"]), fp(mc5["termout_10"])],
        ["Student-t (5) copula, fixed LGD: P(3+) / P(6+) / P(11+)",
         f"{fp(exact_chk_t['p3'])} / {fp(exact_chk_t['p6'])} / {fp(exact_chk_t['p11'])}",
         f"{fp(mc5_t['p3'])} / {fp(mc5_t['p6'])} / {fp(mc5_t['p11'])}"],
    ]))
    L.append("\nDiscrete quantiles (T+0 cash moves in 2% steps). Continuous quantiles of the correlated-LGD variables differ "
             "slightly between methods because the Monte Carlo interpolates; the probabilities agree within sampling error.\n")

    # 19. outcomes by theta
    L.append("## 19. A3. What the buffer and the facility do, by buffer size\n")
    L.append(f"rho {V5_RHO_FAIL:.2f}, P measure, simultaneous standard, F = {pc(V5_CAP, 0)} - theta. 'Term-out' = advance "
             "dividends do not repay the facility, so it stays drawn for up to D years. 'Loss above buffer' = credit loss "
             "exceeds theta, so the facility provider takes a loss. Q column: probability of a draw under the pricing measure.\n")
    for pd in V5_PD_SET:
        L.append(f"lambda_P {pc(pd, 2)}:\n")
        rows = []
        for th in V5_THETA_SET:
            of, oc = outcomes[(pd, "fixed", th)], outcomes[(pd, "corr", th)]
            rows.append([pc(th, 0), pc(of["F"], 0), fp(of["suff"]), fp(of["suff_c"]), fp(of["drawn"]), fp(of["drawn_q"]),
                         f"{fp(of['fail'])} ({one_in(of['fail'])})", fp(of["fail0"]),
                         f"{fp(of['termout'])} / {fp(oc['termout'])}", f"{fp(of['insolv'])} / {fp(oc['insolv'])}"])
        L.append(table(["theta", "F", "P(buffer alone suffices)", "same, given 1+ failures", "P(facility drawn)",
                        "P(drawn), Q", "P(cannot pay par), years", "same with F = 0",
                        "P(term-out) fixed / correlated", "P(loss above buffer) fixed / correlated"], rows))
        L.append("")

    # 20. vehicle default probability
    L.append("## 20. A4. The vehicle's own default probability (cannot pay par)\n")
    L.append(f"Matrix: theta (rows) x F (columns), rho {V5_RHO_FAIL:.2f}, correlated LGD, simultaneous standard, P measure. "
             "Only theta + F matters for this event. A fully funded single-name vehicle has zero by construction.\n")
    for pd in V5_PD_SET:
        L.append(f"lambda_P {pc(pd, 2)} (the reference bank's own PD is {pc(pd, 2)}):\n")
        L.append(table(["theta \\ F"] + [pc(F_, 0) for F_ in V5_F_SET],
                       [[pc(th, 0)] + [fp(vpd[(pd, th, F_)]) for F_ in V5_F_SET] for th in V5_THETA_SET]))
        L.append("")
    L.append("By total capacity theta + F, model and timing (P measure):\n")
    rows = []
    for c in cap_list:
        rows.append([f"{pc(c, 0)} ({int(round(c * V5_N))} failures)"]
                    + [fp(vpd_rho[(r, LAMBDA_P, c, 'sim')]) for r in V5_RHO_SET]
                    + [fp(vpd_rho[(V5_RHO_FAIL, LAMBDA_P, c, 'seq')]), fp(vpd_t[(LAMBDA_P, c)]), fp(vpd_ind[(LAMBDA_P, c)]),
                       fp(vpd_rho[(V5_RHO_FAIL, 0.005, c, 'sim')]), fp(vpd_t[(0.005, c)]),
                       fp(vpd_cond[(LAMBDA_P, c)]), pc(vpd_cond[(LAMBDA_P, c, 'unpaid')], 3)])
    L.append(table(["theta + F", "rho 0.10", "rho 0.20", "rho 0.30", "rho 0.30 sequential", "t(5) copula rho 0.30",
                    "independent", "PD 0.50%, rho 0.30", "PD 0.50%, t(5) rho 0.30",
                    "P(fail | my bank fails), rho 0.30", "E[unpaid share | my bank fails]"], rows))
    L.append("\nColumns 2 to 9 are for PD 0.25% unless labelled. The conditional columns are what matters to a depositor: "
             "protection is called only when its own bank fails, and that selects the bad years.\n")

    # 21. facility provider
    L.append("## 21. A5. The facility provider: cost floor and wrong-way risk\n")
    L.append("(i) A bank providing the facility. On my reading of 12 CFR 249.32(e), a committed liquidity facility to a special "
             "purpose entity or financial sector entity carries a 100% LCR outflow, so the bank holds HQLA equal to the "
             "undrawn amount at the 40 bps net carry used in the model. Capital: base 100% CCF x the SPE's risk weight (100%, an "
             f"unrated SPE treated as a corporate exposure) x {CET1_RATIO:.1%} CET1 x ({HURDLE:.0%} hurdle - {R_FREE:.1%} r). If the facility were "
             "treated as an ordinary commitment the CCF would be 20% (one year or less) or 50% (over one year); as a senior "
             "securitization exposure the risk weight could fall toward its 20% floor. These are floors: they exclude the "
             "provider's expected loss, lending-limit usage and any return for the wrong-way position.\n")
    L.append(table(["Treatment (on my reading)", "LCR cost", "Capital cost", "Floor on fee_F"], [
        ["100% outflow; 100% CCF x 100% RW (base)", b1(BANK_FAC_LCR), b1(fac_capital()), b1(bank_fee_floor["base"])],
        ["100% outflow; 50% CCF x 100% RW", b1(BANK_FAC_LCR), b1(fac_capital(ccf=0.5)), b1(bank_fee_floor["ccf50"])],
        ["100% outflow; 20% CCF x 100% RW", b1(BANK_FAC_LCR), b1(fac_capital(ccf=0.2)), b1(bank_fee_floor["ccf20"])],
        ["100% outflow; 100% CCF x 20% RW", b1(BANK_FAC_LCR), b1(fac_capital(rw=0.2)), b1(bank_fee_floor["rw20"])],
    ]))
    L.append(f"\nSo a bank-provided facility costs at least {b1(BANK_FEE_LO)} to {b1(BANK_FEE_HI)} bps a year on the undrawn "
             "amount.\n")
    L.append("(ii) A non-bank provider (an insurer or asset manager committing to repo its own Treasury holdings to the vehicle, "
             "or to buy the vehicle's receivership claims at a pre-agreed price). There is no verified market price. The "
             "provider bears no LCR or bank capital charge, but must keep the Treasuries unencumbered for the life of the "
             "commitment, must deliver cash in a banking crisis, and takes as collateral receivership claims, which are not "
             "standard repo collateral. Its cost is swept at 5, 10, 20 and 40 bps, with 20 bps as the mid case. The structure "
             "must also survive the provider's own stress: insurers and asset managers face redemptions and margin calls in "
             "the same crisis.\n")
    L.append("(iii) Wrong-way risk when the provider is a bank. The provider fails with probability given z from the same "
             f"factor (PD {pc(V5_PROV_PD, 2)}, loading {V5_PROV_RHO:.2f} unless stated). If it fails, only the buffer is available. "
             f"rho {V5_RHO_FAIL:.2f}, lambda_P 0.25%, correlated LGD, F = {pc(V5_CAP, 0)} - theta.\n")
    rows = []
    for th in V5_THETA_SET:
        r_ = wwy[th]
        rows.append([pc(th, 0), pc(r_["F"], 0), fp(r_["none"]), fp(r_[(V5_PROV_PD, 0.30)]), fp(r_[(V5_PROV_PD, 0.50)]),
                     fp(r_[(0.0025, 0.30)]), fp(r_["mac"]), pc(r_["ps_given_drawn"], 2),
                     f"{fp(r_['cond_none'])} / {fp(r_['cond_bank'])}",
                     f"{r_['hc_none'] / BP:.4f} / {r_['hc_bank'] / BP:.4f}"])
    L.append(table(["theta", "F", "P(fail), provider never fails", "bank PD 0.10%, rho 0.30", "bank PD 0.10%, rho 0.50",
                    "bank PD 0.25%, rho 0.30", "facility unavailable in stress (MAC)", "P(provider fails | facility drawn)",
                    "P(fail | my bank fails): none / bank", "Depositor haircut, bps: none / bank"], rows))
    L.append(f"\nThe provider's unconditional PD is {pc(prov_uncond, 2)}; in the years the facility is drawn its conditional PD "
             f"is {pc(wwy[0.10]['ps_given_drawn'], 1)} (theta 10%). The haircut in bps is tiny because it is a tail event "
             "times a share of LGD; the content is in the conditional column.\n")

    # 22. pricing
    L.append("## 22. A6. Pricing the pooled vehicle\n")
    m = mid
    L.append(f"Mid case: theta 10%, F 10%, fee_F 20 bps, rho {V5_RHO_MID:.2f}, lambda_P 0.25%, LGD 25% fixed, f 15 bps.\n")
    L.append(table(["Component", "Pooled mid case", "Single-name vehicle (v4)"], [
        ["Credit (Q)", b1(m["credit"]), b1(ref["credit"])],
        ["Access (Q)", b1(m["access"]), b1(ref["access"])],
        ["Buffer lock theta x s_lock", b1(m["lock"]), b1(FUND_K) + " (100% locked)"],
        ["Facility commitment F x fee_F", b1(m["commit"]), "0"],
        ["Expected drawn cost", f"{m['drawn'] / BP:.3f}", "0"],
        ["Capacity k", b1(m["k"]), b1(FUND_K)],
        ["Frictions f", b1(m["f"]), b1(FUND_F)],
        ["**c***", "**" + b1(m["c_star"]) + "**", "**" + b1(SINGLE) + "**"],
    ]))
    L.append(f"\nCorrelated LGD: pooled mid case {b1(mid_corr['c_star'])} bps (the single-name vehicle would rise by the same credit "
             f"shift). Facility's Q-expected credit loss (loss above theta), already inside the credit term: "
             f"{m['el_above'] / BP:.5f} bps.\n")
    for cap in (V5_CAP, V5_CAP_ALT):
        L.append(f"c* by buffer and commitment fee, F = {pc(cap, 0)} - theta (capacity for {int(round(cap * V5_N))} simultaneous "
                 f"failures), f 15 bps. Single-name c* = {b1(SINGLE)}:\n")
        fees = V5_FEE_SET + [BANK_FEE_LO, BANK_FEE_HI]
        L.append(table(["theta", "F"] + [f"fee {b1(fe)}" + (" (bank floor)" if fe in (BANK_FEE_LO, BANK_FEE_HI) else "") for fe in fees],
                       [[pc(th, 0), pc(max(0.0, cap - th), 0)] + [b1(price_grid[(cap, th, fe)]["c_star"]) for fe in fees]
                        for th in V5_THETA_SET]))
        L.append("")
    L.append(f"Break-even fee_F (bps) at which the pooled vehicle costs the same as the single-name {b1(SINGLE)} bps vehicle, by frictions "
             "f charged to the pool (the single-name vehicle keeps f 15). 'Any' = no facility; 'never' = dearer at any fee.\n")
    rows = []
    for cap in (V5_CAP, V5_CAP_ALT):
        for th in V5_THETA_SET:
            cells = []
            for fr in V5_FRIC_SET:
                v = breakeven_fee[(cap, th, fr)]
                c0 = breakeven_fee[(cap, th, fr, "c0")]
                cells.append(("any (" + b1(c0) + ")" if c0 < SINGLE else "never") if v is None else ("never" if v < 0 else f"{v / BP:.0f}"))
            rows.append([pc(cap, 0), pc(th, 0), pc(max(0.0, cap - th), 0)] + cells)
    L.append(table(["theta + F", "theta", "F"] + [f"f = {b1(fr)}" for fr in V5_FRIC_SET], rows))
    L.append("\nMid-case c* by rho, lambda_P and LGD mode (bps):\n")
    L.append(table(["rho"] + [f"PD {pc(pd, 2)}, {md}" for pd in V5_PD_SET for md in ("fixed", "corr")],
                   [[f"{r:.2f}"] + [b1(mid_sens[(r, pd, md)]) for pd in V5_PD_SET for md in ("fixed", "corr")] for r in V5_RHO_SET]))
    L.append(f"\nFor reference, the single-name vehicle at lambda_P 0.50% is {b1(components(lambda_p=0.005, k=FUND_K, f=FUND_F)['c_star'])} bps.\n")
    L.append("Facility sizing at theta 10%: a facility committed on 90% of notional (so par never depends on the buffer) "
             "against one sized to need, and the low frictions sweep point (bps):\n")
    L.append(table(["Case", "c*"], [[a_, b1(b_)] for a_, b_ in wide]))
    L.append(f"\nWhat it takes to reach 31 bps at theta 10%, F 10%: c* = {b1(c_no_fee_no_f)} + f + 0.10 x fee_F. "
             + "; ".join(f"f {b1(fr)}: fee_F at most {((V5_LOW_MARK - c_no_fee_no_f - fr) / 0.10) / BP:.0f} bps"
                         if V5_LOW_MARK - c_no_fee_no_f - fr >= 0 else f"f {b1(fr)}: impossible"
                         for fr in V5_FRIC_SET) + ".\n")
    L.append(table(["Facility sizing at theta 10%: protection failure (rho 0.30, P)", "Probability"], [
        ["F 90%, provider never fails", fp(wide_fail["none"])],
        ["F 90%, provider is a bank (PD 0.10%, rho 0.30)", fp(wide_fail["bank"])],
        ["F 90%, facility unavailable in stress", fp(wide_fail["mac"])],
        ["Capacity for 6 failures (theta 10% + F 2%)", fp(wide_fail["six"])],
    ]))
    L.append("")

    # 23. trade-off
    L.append("## 23. A7. The trade-off: a lower price for a less certain par\n")
    L.append("c* at the mid case (rho 0.20, LGD 25%). Failure statistics at rho 0.30, "
             "correlated LGD, lambda_P 0.25%, simultaneous standard. Haircut uses the bank-provider case where the provider "
             "is a bank.\n")
    L.append(table(["Design", "c* (bps)", "P(cannot pay par)", "years", "with a bank provider", "P(fail | my bank fails)",
                    "Depositor haircut (bps)"],
                   [[t_["name"], b1(t_["c"]), fp(t_["fail"]), one_in(t_["fail"]), fp(t_["fail_bank"]) if t_["fail_bank"] is not None else "n/a",
                     fp(t_["cond"]), f"{t_['hc'] / BP:.4f}"] for t_ in tradeoff]))
    L.append("")

    # 24. tranches
    L.append("## 24. A8. Tranching the pool's credit loss (theta 10%)\n")
    L.append("Loss as % of covered notional. Spread = Q-expected loss of the tranche per year on its own size (the copula run at "
             "mu x lambda_P = 0.75% per bank), over T-bills. P-EL at lambda_P 0.25%. Multiple = spread / P-EL. Each cell: "
             "P-EL / spread / P(any loss), % of tranche per year.\n")
    for mode in ("fixed", "corr"):
        L.append(f"LGD {('fixed 25%' if mode == 'fixed' else 'correlated 15% to 40%')}:\n")
        trs = tranche_v6[(V5_RHO_SET[0], mode)]
        rows = []
        for i, (tr, _, _) in enumerate(trs):
            cells = []
            for r in V5_RHO_SET:
                _, sp, sq = tranche_v6[(r, mode)][i]
                mult = sq["el"] / sp["el"] if sp["el"] > 0 else float("nan")
                cells.append(f"{pel(sp['el'])} / {pel(sq['el'])} ({mult:.1f}x) / {fp(sp['p_hit'])}")
            rows.append([f"{tr[0]} {pc(tr[1], 0)} to {pc(tr[2], 0)}"] + cells)
        L.append(table(["Tranche"] + [f"rho {r:.2f}" for r in V5_RHO_SET], rows))
        L.append("")
    L.append("Check: thickness-weighted spreads sum to the credit term (bps): "
             + "; ".join(f"rho {k_[0]:.2f} {k_[1]} {v / BP:.2f}" for k_, v in tranche_check.items()) + ".\n")
    L.append("Pricing every tranche at mu 3 times its own P-EL would overprice the equity (its Q multiple is below 3) and "
             "understate the senior (its multiple is far above 3), because a three-fold PD fattens the cluster tail more than "
             "proportionally.\n")

    # 25. stress
    L.append("## 25. B. Deterministic stress scenarios for the pool\n")
    L.append(f"theta {pc(V5_STRESS_THETA, 0)}, F {pc(V5_STRESS_F, 0)}, each bank 2% of the pool. Percent of covered notional. "
             "All failures in one advance-dividend window (simultaneous) unless stated.\n")
    L.append(table(["Failures", "LGD", "a", "T+0 cash", "Buffer used", "Facility drawn", "Shortfall at T+0",
                    "Peak if sequential", "Term need after a", "Facility term-out", "Credit loss", "Buffer left at the end",
                    "Facility loss", "Buffer free for next year until recoveries", "F needed for par"],
                   [[s_["n"], pc(s_["lgd"], 0), pc(s_["a"], 0), pc(s_["t0"], 0), pc(s_["buf"], 0), pc(s_["fac"], 0),
                     pc(s_["short"], 0), pc(s_["seq"], 1), pc(s_["term"], 1), pc(s_["termout"], 1), pc(s_["loss"], 1),
                     pc(s_["buf_left"], 1), pc(s_["fac_loss"], 1), pc(s_["cap_next"], 1), pc(s_["need_F"], 0)] for s_ in stress]))
    L.append("\nF needed for par by buffer (simultaneous): " + "; ".join(
        f"{n_} failures: " + ", ".join(f"theta {pc(th, 0)} needs F {pc(max(0.0, n_ / V5_N - th), 0)}" for th in V5_THETA_SET)
        for n_ in V5_STRESS_N) + ".\n")

    # 26. yield advantage
    L.append("## 26. C. Yield-advantage sweep\n")
    L.append("Delta is the depositor's yield advantage in bps, swept from 0 to 150; no point estimate is offered. Two illustrative "
             "benchmark regimes read the same axis differently. Passive cash vs government MMF: Delta is the spread over a "
             "government money market fund, the outside option for cash that does not need to sit at a bank. Operating "
             "balances vs a large bank's operating account: operating cash cannot sit in a fund, so Delta is the spread (rate "
             "or earnings credit) over what the same balance would earn in a large bank's operating account; that account is "
             "itself uninsured above the limit, so in this regime the costs below overstate the risk the depositor avoids by "
             "the large bank's own (smaller) self-insured cost.\n")
    L.append(f"Costs at lambda_P 0.25% (bps): " + "; ".join(f"{k_} {b1(v)}" for k_, v in cost_base.items()) + ".\n")
    L.append("Delta minus cost, bps (positive = the advantage covers the cost):\n")
    L.append(table(["Cost"] + [f"Delta {d_ / BP:.0f}" for d_ in V5_DELTA_SET],
                   [[k_] + [f"{(d_ - v) / BP:+.1f}" for d_ in V5_DELTA_SET] for k_, v in cost_base.items()]))
    L.append("\nBreak-even lambda_P at which the cost equals Delta (mu 3, LGD 25%, a 50%); 'none' = cost exceeds Delta at any PD:\n")
    L.append(table(["Cost"] + [f"Delta {d_ / BP:.0f}" for d_ in V5_DELTA_SET],
                   [[k_] + [("none" if be_c[k_][d_] is None else pc(be_c[k_][d_], 2)) for d_ in V5_DELTA_SET] for k_ in costs_c]))
    L.append("\nPooled mid case: theta 10%, F 10% at 20 bps, rho 0.20, f 15. Its drawn cost is recomputed at each PD.\n")

    # 27. who pays
    L.append("## 27. D. Who pays: the posted rate moves, the cost does not\n")
    L.append(f"Per unit of balance, relative to the outside-option yield y. c = pooled mid-case c* = {b1(who_c)} bps; Delta values "
             "are sweep points, not estimates. 'Bank pays' covers a rate cut or an equivalent earnings credit reduction.\n")
    rows = []
    for d_ in WHO_DELTA:
        for label, posted, prem_dep, prem_bank in [
            ("Depositor buys protection", d_, who_c, 0.0),
            ("Bank buys it, passes it through in the rate or ECR", d_ - who_c, 0.0, who_c),
            ("Bank buys it and absorbs it (rate unchanged)", d_, 0.0, who_c),
            ("Nobody buys it", d_, 0.0, 0.0)]:
            protected = label != "Nobody buys it"
            rows.append([f"{d_ / BP:.0f}", label, f"y {('+' if posted >= 0 else '-')} {abs(posted) / BP:.1f}",
                         b1(prem_dep), b1(prem_bank), f"y {('+' if posted - prem_dep >= 0 else '-')} {abs(posted - prem_dep) / BP:.1f}",
                         f"y {('+' if posted + prem_bank >= 0 else '-')} {abs(posted + prem_bank) / BP:.1f}",
                         "par" if protected else "par less LGD on failure", b1(prem_dep + prem_bank)])
    L.append(table(["Delta", "Who pays", "Posted rate", "Premium paid by depositor", "Premium paid by bank",
                    "Depositor net yield", "Bank all-in cost of the balance", "Depositor gets at failure", "Total paid for protection"], rows))
    L.append("\nIdentity: depositor net yield + premium paid by the depositor = posted rate; bank all-in cost = posted rate + "
             "premium paid by the bank. Whenever the balance is protected, depositor net + provider income = bank all-in "
             "cost, and the provider income is c whoever writes the cheque. Who pays changes the posted rate, the accounting and "
             "the tax line (an earnings credit offsets fees rather than paying interest), not the cost. Two non-neutral "
             "points: a bank that pays a third party a fee tied to the deposit risks deposit-broker status under the "
             "facilitation prong (12 CFR 337.6, an open question), and the LCR run-off on the deposit is unchanged either way.\n")

    # 28. challenge register
    L.append("## 28. F. Challenge register\n")
    L.append(f"Price sensitivity: pooled mid case c* = {b1(CR_C0)} bps (theta 10%, F 10% at 20 bps, rho 0.20, LGD 25%). Failure "
             f"sensitivity: P(cannot pay par) = {fp(CR_P0)} ({one_in(CR_P0)} years) at theta 10% + F 10%, rho 0.30, correlated "
             "LGD, simultaneous standard, PD 0.25%. Each row moves one assumption.\n")
    pfa = cr["adv"]
    reg = [
        ["Per-bank PD lambda_P", "0.25% (0.50%)", "author assumption; illustrative",
         "No observable PD for a deposit claim; adverse selection: banks whose depositors buy know most",
         f"{b1(CR_C0)} -> {b1(cr['pd'][0])}", f"{fp(CR_P0)} -> {fp(cr['pd'][1])}"],
        ["Asset correlation rho", "0.20 price, 0.30 failure (0.10 to 0.30)", "illustrative; no calibration to bank failures",
         "Rating agencies will ask for a calibrated or stressed correlation; 2023 shows clustering",
         f"{b1(cr['rho'][0])} to {b1(cr['rho'][1])} (fixed LGD); {b1(mid_sens[(0.10, LAMBDA_P, 'corr')])} to "
         f"{b1(mid_sens[(0.30, LAMBDA_P, 'corr')])} (correlated)", f"{fp(cr['rho'][2])} (0.10), {fp(cr['rho'][3])} (0.20), {fp(CR_P0)} (0.30)"],
        ["Copula family", "Gaussian (Student-t, 5 df)", "standard, tractable",
         "Gaussian copula has no tail dependence; a t copula is the usual challenge",
         f"{b1(cr['t'][0])}", f"{fp(CR_P0)} -> {fp(cr['t'][1])} (t)"],
        ["LGD_dep and its link to the cycle", "25% fixed; correlated 15% to 40%; 40% stress",
         "depositor preference; FHLB priority makes LGD worse in clusters",
         "No receivership-level dataset of deposit recoveries net of secured borrowing",
         f"{b1(cr['lgd'][0])} (corr), {b1(cr['lgd'][1])} (40%)",
         f"none on the T+0 standard; P(loss above buffer) {fp(cr['lgd'][2])} fixed, {fp(cr['lgd'][3])} corr, {fp(cr['lgd'][4])} at 40%"],
        ["Advance dividend a", "50% (30% to 60%); 0 as a failure mode", "FDIC practice since 1984; IndyMac 50%",
         "Discretionary in amount and timing; not paid at all if the FDIC chooses otherwise; the facility is repaid from it",
         f"{b1(pfa[0])} (30%), {b1(pfa[1])} (60%), {b1(pfa[2])} (0)",
         f"T+0 standard unchanged; P(term-out) {fp(pfa[3][0.30])} at 30%, {fp(pfa[3][0.50])} at 50%, {fp(pfa[3][0.0])} at 0; "
         f"sequential P(fail) {fp(pfa[4][0.30])} at 30%, {fp(pfa[4][0.60])} at 60%"],
        ["T+0 to advance dividend", f"{V5_ADV_LAG_DAYS} days ({V5_ADV_LAG_ALT})", "FDIC practice: 'within days', 'within the week'",
         "Assumption, not a commitment; a late dividend extends the draw", f"{b1(cr['lag'][0])}", "none on the simultaneous standard"],
        ["Years to final dividends D", "2 (1 to 3)", "author assumption", "Receiverships can run longer",
         f"{b1(cr['D'][0])} to {b1(cr['D'][1])}", "none (one-year horizon); ties up the buffer longer (Section 25)"],
        ["Concentration cap per bank", "2% x 50 banks (4% x 25)", "design choice; Ohio 1985 is the counterexample",
         "Can 50 eligible regional banks with willing depositors be found; does the cap hold as balances move",
         f"{b1(cr['conc'][0])}", f"{fp(CR_P0)} -> {fp(cr['conc'][1])} (25 banks)"],
        ["Timing standard", "simultaneous (sequential)", "conservative bound; 2023 had two failures in one weekend",
         "Sequential is more realistic in most years; simultaneous is the standard a rating agency would test",
         "none", f"{fp(CR_P0)} -> {fp(cr['timing'][0])} (sequential)"],
        ["Buffer theta and capacity theta + F", "10% + 10% (theta 5% to 20%; capacity 12% to 30%)", "design choice",
         "The capacity is a judgment about the worst cluster to survive", f"{b1(cr['theta'][0])} (theta 5%) to {b1(cr['theta'][1])} (theta 20%)",
         f"{fp(cr['theta'][2])} at 12%; {fp(cr['theta'][3])} at 30%"],
        ["Facility fee fee_F", f"20 bps (5 to 40 non-bank; bank floor {b1(BANK_FEE_LO)} to {b1(BANK_FEE_HI)})", "no verified market price",
         "Who commits cash in a banking crisis, and at what price; no verified market price",
         f"{b1(cr['fee'][0])} to {b1(cr['fee'][1])}; bank {b1(cr['fee'][2])} to {b1(cr['fee'][3])}", "none (price only)"],
        ["Facility provider", "never fails (bank: PD 0.10%, rho 0.30 to 0.50)", "the depositor's protection is only as good as F",
         "Wrong-way: a bank provider fails in the same states; a non-bank faces redemptions", "none (value haircut, Section 21)",
         f"{fp(CR_P0)} -> {fp(cr['prov'][0])} (rho 0.30), {fp(cr['prov'][1])} (rho 0.50), {fp(cr['prov'][2])} (PD 0.25%)"],
        ["Facility conditionality", "unconditional, no MAC, no borrowing base", "required for par certainty",
         "Providers will ask for conditions precedent; any MAC removes F exactly when needed", "higher fee (not modelled)",
         f"{fp(CR_P0)} -> {fp(cr['mac'][0])} (F unavailable)"],
        ["Buffer lock premium s_lock", "10 bps (5 to 15)", "= single-name k", "A first-loss buffer locked for D after a cluster "
         "may need more", f"{b1(cr['lock'][0])} to {b1(cr['lock'][1])}", "none"],
        ["Drawn margin s_draw", "200 bps (100 to 400)", "illustrative", "Stressed-state borrowing cost of an SPE",
         f"{b1(cr['draw'][0])} to {b1(cr['draw'][1])} (drawn cost under 0.01 bps)", "none"],
        ["Frictions f", "15 bps (10 to 20)", "author assumption; floor 10 (author choice)", "Fifty names, a facility, ratings and legal "
         "opinions may cost more, not less", f"{b1(cr['fric'][0])} to {b1(cr['fric'][1])}", "none"],
        ["Risk-premium multiplier mu", "3 (2 to 5)", "author assumption", "Rare-event risk premia are not observed",
         f"{b1(cr['mu'][0])} to {b1(cr['mu'][1])}", "none (P measure)"],
        ["Replenishment after a loss year", "buffer topped up (not modelled)", "annual renewal",
         "After a cluster the buffer is tied up in receivership claims for D years",
         "renewal premium (not modelled)", f"next year at theta reduced by the term bridge: {fp(cr['replen'][0])} after 3 failures, "
         f"{fp(cr['replen'][1])} after 6"],
        ["Legal: claim transfer and advance-dividend receipt", "vehicle owns the claim and receives the advance dividend",
         "purchase at par (Section 9)", "Deposit agreements restrict assignment; setoff; receiver recognition",
         "none", f"if the vehicle cannot collect the advance dividend, the facility terms out: {fp(pfa[3][0.0])}"],
        ["Regulatory characterization", "security-based swap or guarantee", "Section 9",
         "A 50-name guarantee program looks like insurance (state financial guaranty law); ECP test", "not quantified", "not quantified"],
        ["Policy risk", "no systemic risk exception assumed", "statute requires a two-thirds vote and Treasury",
         "A repeat exception removes buyers' reason to pay", "not quantified", "not quantified"],
    ]
    L.append(table(["Assumption", "Value (range)", "Why", "Challenge (regulator, rating agency, investor)",
                    "c* sensitivity (bps)", "P(cannot pay par) sensitivity"], reg))
    L.append("")

    # 29. what the numbers say
    o = []
    o.append(f"Pooled c*. At theta 10% and F 10%, the pooled vehicle costs {b1(mid['c_star'])} bps with a 20 bps non-bank facility, "
             f"against {b1(SINGLE)} for the single-name vehicle; across theta 5% to 20% and fee_F 5 to 40 bps it spans "
             f"{b1(min(price_grid[(V5_CAP, th, fe)]['c_star'] for th in V5_THETA_SET for fe in V5_FEE_SET))} to "
             f"{b1(max(price_grid[(V5_CAP, th, fe)]['c_star'] for th in V5_THETA_SET for fe in V5_FEE_SET))} bps (f 15). The saving is "
             f"the capacity term only: credit and access are the same per bank, so pooling can save at most the {bps(FUND_K)} bps "
             "of lock premium, and gives part of it back in facility fees.")
    o.append(f"Break-even fee. With equal frictions, the pool beats {b1(SINGLE)} bps up to a fee of {breakeven_fee[(V5_CAP, 0.10, V5_FRIC)] / BP:.0f} bps "
             f"at theta 10% (F 10%) and {breakeven_fee[(V5_CAP, 0.05, V5_FRIC)] / BP:.0f} bps at theta 5% (F 15%). A bank facility at its "
             f"cost floor ({b1(BANK_FEE_LO)} to {b1(BANK_FEE_HI)} bps on my reading of LCR and capital) sits around or above that.")
    o.append(f"Facility sizing. Committing the facility on 90% of notional at a 20 bps fee gives {b1(wide[0][1])}; at a bank floor "
             f"{b1(wide[1][1])} to {b1(wide[2][1])}. Sized to need (10%) at 20 bps it is {b1(wide[3][1])}, and about 31 bps is "
             f"reachable only by also cutting frictions to 7.5 ({b1(wide[5][1])}). So about 31 bps is a defensible low end only "
             "if both the frictions and the facility cost assumptions are evidenced; the base is 38 to 39.")
    o.append(f"Protection failure. At theta 10% + F 10% the vehicle cannot pay par with probability {fp(CR_P0)} a year ({one_in(CR_P0)}) "
             f"at rho 0.30 under a Gaussian copula, but {fp(cr['t'][1])} under a t(5) copula and {fp(cr['pd'][1])} at PD 0.50%. "
             f"Conditional on the depositor's own bank failing it is {fp(vpd_cond[(LAMBDA_P, 0.20)])}. With only the buffer (a facility "
             f"unavailable in stress) it is {fp(cr['mac'][0])}. The tail model moves the answer more than any parameter.")
    o.append(f"The facility as the weak link. If the provider is a bank (PD 0.10%, rho 0.30) its conditional PD in the years it is "
             f"drawn is {pc(wwy[0.10]['ps_given_drawn'], 1)}, and P(cannot pay par) rises from {fp(CR_P0)} to {fp(cr['prov'][0])}; "
             f"the value haircut is a fraction of a basis point, but it is concentrated in exactly the cluster years.")
    st3 = [s_ for s_ in stress if s_["n"] == 3 and s_["lgd"] == 0.25 and s_["a"] == 0.50][0]
    st6 = [s_ for s_ in stress if s_["n"] == 6 and s_["lgd"] == 0.40 and s_["a"] == 0.30][0]
    st10 = [s_ for s_ in stress if s_["n"] == 10 and s_["lgd"] == 0.40 and s_["a"] == 0.30][0]
    o.append(f"Stress. A 2023-like year (3 failures) needs {pc(st3['t0'], 0)} at T+0, inside a 10% buffer, and loses "
             f"{pc(st3['loss'], 1)}. Six failures at LGD 40% and a 30% advance dividend need {pc(st6['t0'], 0)} at T+0 "
             f"(facility {pc(st6['fac'], 0)}); the advance dividends repay the facility within the week, the buffer carries the "
             f"{pc(st6['term'], 1)} term bridge, and the credit loss is {pc(st6['loss'], 1)}. "
             f"Ten failures need {pc(st10['t0'], 0)}: par is paid only with F of at least 10%, the facility terms out "
             f"{pc(st10['termout'], 1)}, and the credit loss ({pc(st10['loss'], 1)}) still fits inside the buffer.")
    o.append("Who pays changes the posted rate, not the cost: with protection, depositor net yield plus provider income always "
             "equals the bank's all-in cost of the balance.")
    L.append("## 29. What the v5 numbers say\n")
    L.extend(f"{i}. {t}" for i, t in enumerate(o, 1))
    L.append("")
    L.append("v5 modelling notes (specification issues and choices):\n")
    flags = [
        "The T+0 protection-failure event depends only on the failure count under the simultaneous standard, so "
        "correlated LGD does not move it. LGD enters through term-out and loss-above-buffer (fig-07 right panel), and through "
        "the advance dividend, which I linked to LGD (a = (2/3)(1 - LGD)) in the correlated mode [author assumption].",
        "Prices use the copula under Q (PD x mu). Pricing each tranche at mu 3 times its own P-EL would understate senior tranches "
        "(Section 24).",
        "The facility's credit loss (loss above theta) is allocated from the credit term, not added; adding it would double count.",
        "The design rule theta + F = 20% (10 simultaneous failures) is mine, chosen so the vehicle's P-measure default "
        "probability is about 0.01% a year at rho 0.30 under a Gaussian copula. It is a judgment for a sponsor and a rating agency.",
        "Bank facility cost floor uses a 100% CCF and a 100% risk weight in the base reading. A 20% or 50% CCF (ordinary "
        f"commitment) or a 20% securitization floor gives {b1(BANK_FEE_LO)} to "
        f"{b1(max(bank_fee_floor['ccf20'], bank_fee_floor['ccf50'], bank_fee_floor['rw20']))} bps. All on my reading; counsel should confirm.",
        "A repo against FDIC advance-dividend receivables has no standard collateral market; I modelled the "
        "facility as unsecured liquidity repaid from advance dividends, then secured on receivership claims if it terms out.",
        "Rho, the LGD mapping, the provider PD and s_draw are illustrative, not calibrated.",
    ]
    L.extend(f"{i}. {t}" for i, t in enumerate(flags, 1))
    L.append("")
    RESULTS_MD.write_text("\n".join(L), encoding="utf-8")


# =============================================================================
# 6. FIGURES
# =============================================================================
def make_figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    NAVY, STEEL, SLATE, MIST, INK, GRID, ACCENT = "#1F3A5F", "#4F74A8", "#8A9AAE", "#C9D3DF", "#2B2B2B", "#E3E7EC", "#D2851F"
    MUTED = "#4A5361"
    plt.rcParams.update({
        "font.family": "Inter", "font.size": 10, "axes.edgecolor": "#8C96A3", "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "text.color": INK, "hatch.color": NAVY, "hatch.linewidth": 0.8,
    })
    SRC = "Source: author's calculations."

    def frame(fig, title, subtitle, source):
        fig.text(0.06, 0.955, title, fontsize=14, fontweight="semibold", ha="left", va="top", color=INK)
        fig.text(0.06, 0.905, subtitle, fontsize=10, ha="left", va="top", color="#5A6472")
        fig.text(0.06, 0.03, source, fontsize=7.5, ha="left", va="bottom", color="#6B7480")

    # ---- fig-01: 2023 evidence (verified FDIC figures only); unchanged from v1 ----
    banks = ["SVB", "Signature", "First Republic"]
    thresholds = ["$49M", "$16M", "$6M"]
    share_held = [38.5, 62, 50]
    held_lbl = ["38-39%", "62%", "50%"]
    share_ran = [74, 65, 74]
    fig, ax = plt.subplots(figsize=(8, 5.2))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.2)
    x = range(3)
    w = 0.34
    b1 = ax.bar([i - w / 2 - 0.01 for i in x], share_held, w, color=SLATE, label="Share of the bank's deposits they held")
    b2 = ax.bar([i + w / 2 + 0.01 for i in x], share_ran, w, color=NAVY, label="Share of them that ran by 17 March 2023")
    for bars, labels in ((b1, held_lbl), (b2, [f"{v}%" for v in share_ran])):
        for bar, t in zip(bars, labels):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5, t, ha="center", va="bottom", fontsize=10, color=INK)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{b}\ntop 0.5% threshold about {t}" for b, t in zip(banks, thresholds)], fontsize=10)
    ax.tick_params(axis="x", length=0)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels([f"{v}%" for v in [0, 25, 50, 75, 100]])
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", bbox_to_anchor=(0, 1.08), ncol=2, frameon=False, fontsize=9.5, handlelength=1.2)
    frame(fig, "The largest depositors held much of the funding and most of them ran",
          "Top 0.5 percent of depositors by tax ID at the three banks that failed in spring 2023",
          "Source: Chu et al., \"Dissecting Depositor Flight: An Analysis of the Spring 2023 Bank Failures,\" FDIC Center for Financial Research\n"
          "Staff Studies, May 2026. \"Ran\" means withdrawing at least 75 percent of the 6 March 2023 balance. SVB share held is reported as 38 to 39 percent.")
    fig.savefig(FIG(1), dpi=200)
    plt.close(fig)

    # ---- fig-03 (was fig-02): the wedge on $1B ---------------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.8))
    fig.subplots_adjust(left=0.17, right=0.96, top=0.8, bottom=0.29)
    ys = [2, 1, 0]
    for y, wv in zip(ys, wedge):
        a_, later, loss = wv["adv"] / 1e6, wv["later"] / 1e6, wv["loss"] / 1e6
        ax.barh(y, a_, color=MIST, edgecolor="white", height=0.56)
        ax.barh(y, later, left=a_, color=STEEL, edgecolor="white", height=0.56)
        ax.barh(y, loss, left=a_ + later, color=NAVY, edgecolor="white", height=0.56)
        ax.text(a_ / 2, y, f"${a_:,.0f}M", ha="center", va="center", fontsize=9.5, color=INK)
        ax.text(a_ + later / 2, y, f"${later:,.0f}M", ha="center", va="center", fontsize=9.5, color="white")
        ax.text(a_ + later + loss / 2, y, f"${loss:,.0f}M", ha="center", va="center", fontsize=9.5, color="white")
    ax.set_yticks(ys)
    ax.set_yticklabels([f"Deposit LGD {wv['lgd']:.0%}" for wv in wedge], fontsize=10)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 1000)
    ax.set_xticks([0, 250, 500, 750, 1000])
    ax.set_xticklabels(["$0", "$250M", "$500M", "$750M", "$1,000M"])
    ax.set_xlabel("Cash the provider pays at the trigger, $1 billion covered", fontsize=9.5, color=MUTED)
    ax.spines["left"].set_visible(False)
    def bracket(x0, x1, y, text):
        ax.plot([x0, x0, x1, x1], [y - 0.07, y, y, y - 0.07], color=INK, lw=0.9, clip_on=False)
        ax.text((x0 + x1) / 2, y + 0.06, text, ha="center", va="bottom", fontsize=9, color=INK, clip_on=False)
    bracket(0, 1000, 2.98, "Gross cash at trigger: $1,000M")
    bracket(500, 1000, 2.47, "Net bridge after the 50% advance dividend: $500M")
    ax.set_ylim(-0.4, 3.3)
    handles = [Patch(color=MIST, label="Advance dividend returned within days"),
               Patch(color=STEEL, label=f"Recovered later, over about {D_YEARS:g} years"),
               Patch(color=NAVY, label="Ultimate loss")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.1), ncol=3, frameon=False, fontsize=9, handlelength=1.2)
    frame(fig, "One failure turns a small annual price into a large cash call",
          "Provider cash flows on $1 billion of covered balance, full exercise, 50 percent advance dividend",
          SRC + " Illustrative; advance dividend and LGD are assumptions,\nnot forecasts for any bank.")
    fig.savefig(FIG(3), dpi=200)
    plt.close(fig)

    # ---- fig-02 (was fig-03): decomposition by provider (bank at its binding P price) ----
    names = list(base.keys())
    short = ["Funded investor\nvehicle", "Bank SBLC seller\n(P price binds)", "Regional\nmutual pool"]
    fig, ax = plt.subplots(figsize=(8, 5.6))
    fig.subplots_adjust(left=0.1, right=0.97, top=0.8, bottom=0.25)
    segs = [("credit", "Credit", NAVY, None), ("capital", "Capital cost (bank)", "white", "////"),
            ("access", "Access funding", STEEL, None), ("capacity", "Standing capacity k", SLATE, None),
            ("frictions", "Frictions f", MIST, None)]
    xs = [0, 1, 2]
    W = 0.52
    for xi, n in zip(xs, names):
        bottom = 0
        for key, _, col, hatch in segs:
            v = base[n][key] / BP
            if v <= 0:
                continue
            ax.bar(xi, v, W, bottom=bottom, color=col, edgecolor=NAVY if hatch else "white", lw=0.8, hatch=hatch)
            if v >= 5:
                tc = "white" if col in (NAVY, STEEL, SLATE) else INK
                ax.text(xi, bottom + v / 2, f"{v:.0f}", ha="center", va="center", fontsize=9, color=tc,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none") if hatch else None)
            bottom += v
        ax.text(xi, bottom + 1.5, f"{bottom:.0f} bps", ha="center", va="bottom", fontsize=10, fontweight="semibold")
    acc0 = base[names[0]]
    yacc = (acc0["credit"] + acc0["access"] / 2) / BP
    ax.annotate(f"access {acc0['access'] / BP:.1f}", xy=(W / 2, yacc), xytext=(0.36, yacc), fontsize=8, color=MUTED,
                va="center", arrowprops=dict(arrowstyle="-", color="#8C96A3", lw=0.7))
    # bank: P floor (top of capital) and Q price markers
    fl = floor / BP
    qb = bank["q"]["c_star"] / BP
    ax.plot([1 - W / 2 - 0.05, 1 + W / 2 + 0.05], [fl, fl], color=ACCENT, lw=2.2, solid_capstyle="butt")
    ax.text(1 + W / 2 + 0.08, fl, f"P floor {fl:.0f} bps", ha="left", va="center", fontsize=8.5, color=ACCENT)
    ax.plot([1 - W / 2 - 0.05, 1 + W / 2 + 0.05], [qb, qb], color=ACCENT, lw=1.6, ls=(0, (3, 2)))
    ax.text(1 + W / 2 + 0.08, qb - 1.0, f"Q price {qb:.0f} bps", ha="left", va="top", fontsize=8.5, color=ACCENT)
    # pool wrong-way haircut
    pc = base[names[2]]
    top, hc = pc["c_star"] / BP, pc["haircut"] / BP
    ax.plot([2 + W / 2 + 0.04] * 2, [top - hc, top], color=ACCENT, lw=2.4, solid_capstyle="butt")
    ax.text(2 + W / 2 + 0.09, top - hc / 2, f"Value to the depositor\nfalls {hc:.1f} bps for\nwrong-way risk",
            ha="left", va="center", fontsize=8.5, color=ACCENT)
    ax.set_xticks(xs)
    ax.set_xticklabels(short, fontsize=10)
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(-0.45, 2.95)
    ax.set_ylim(0, 60)
    ax.set_ylabel("bps per year on the covered balance", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    handles = [Patch(facecolor=c, edgecolor=NAVY if h else c, hatch=h, label=l) for _, l, c, h in segs]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.1), ncol=5, frameon=False, fontsize=8.8,
               handlelength=1.2, columnspacing=1.2)
    frame(fig, "More than half of the base-case clearing cost is the cost of the transfer",
          "Base-case clearing cost by provider type: PD 0.25%, mu 3, deposit LGD 25%, advance dividend 50%",
          SRC + " Bank price = max(Q, P), P price = EL_P + access + capital + k + f.\n"
          f"P floor = EL_P + capital; capital = 100% CCF x 20% RW x 13.5% CET1 x (10% hurdle less {R_FREE:.1%} r). Capacity: vehicle 10 bps,\n"
          "bank 30% outflow x 40 bps HQLA carry, pool 10% reserve x 100 bps. Haircut at 40% joint failure and 50% pool LGD (illustrative).")
    fig.savefig(FIG(2), dpi=200)
    plt.close(fig)

    # ---- fig-04: bearing the risk vs buying protection, against the yield advantage ----
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(10, 5.4))
    fig.subplots_adjust(left=0.075, right=0.9, top=0.76, bottom=0.2, wspace=0.42)
    xs = [lp * 100 for lp in LAMBDA_P_SET]
    band_lbl = "Plausible yield advantage\nover a government MMF:\n0 to 50 bps"

    def setup(ax, ymax, title):
        ax.axhspan(DELTA_BAND[0] / BP, DELTA_BAND[1] / BP, color=ACCENT, alpha=0.14, lw=0)
        ax.set_xscale("log")
        ax.set_xticks(xs)
        ax.set_xticklabels([f"{v:.2f}%" for v in xs], fontsize=9)
        ax.minorticks_off()
        ax.set_xlim(0.085, 2.3)
        ax.set_ylim(0, ymax)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_title(title, loc="left", fontsize=10.5, fontweight="semibold", color=INK, pad=10)
        ax.set_xlabel("Bank default probability, lambda_P (log scale)", fontsize=9, color=MUTED)

    # left: LGD 25%, self-insured vs purchased
    setup(axl, 200, "Deposit LGD 25%: bearing the risk or buying protection")
    si = [self_insured(lambda_p=lp) / BP for lp in LAMBDA_P_SET]
    cs = [grid[(lp, LGD_DEP)]["c_star"] / BP for lp in LAMBDA_P_SET]
    axl.fill_between(xs, si, cs, color=SLATE, alpha=0.22, lw=0)
    axl.plot(xs, cs, color=NAVY, lw=2.2, marker="s", ms=5)
    axl.plot(xs, si, color=STEEL, lw=2.2, marker="o", ms=5)
    axl.text(xs[-1] * 1.07, cs[-1], f"Buying\nprotection\n(c*) {cs[-1]:.0f}", color=NAVY, fontsize=8.8, va="center", ha="left")
    axl.text(xs[-1] * 1.07, si[-1] - 6, f"Bearing\nthe risk\n{si[-1]:.0f}", color=STEEL, fontsize=8.8, va="center", ha="left")
    axl.annotate(f"Transfer cost\nk + f = {transfer / BP:.0f} bps", xy=(0.7, (self_insured(lambda_p=0.007) + transfer / 2) / BP),
                 xytext=(0.2, 120), fontsize=8.8, color=MUTED, ha="center",
                 arrowprops=dict(arrowstyle="-", color="#8C96A3", lw=0.8))
    for key, col in ((REF, NAVY), (SELF, STEEL)):
        bx = be[key][50 * BP] * 100
        axl.plot([bx], [50], marker="o", ms=6, mfc="white", mec=col, mew=1.6, zorder=5)
        axl.annotate(f"{bx:.2f}%", xy=(bx, 50), xytext=(bx, 63 if key == REF else 28), fontsize=8.5, color=col,
                     ha="center", arrowprops=dict(arrowstyle="-", color=col, lw=0.6))
    axl.text(0.92, 45, band_lbl, fontsize=8, color="#9A5A0A", va="top", ha="left")
    axl.set_ylabel("bps per year on the covered balance", fontsize=9, color=MUTED)

    # right: purchased c* by LGD
    setup(axr, 300, "Buying protection, by deposit LGD")
    styles = {0.15: (SLATE, "o", 1.6), 0.25: (NAVY, "s", 2.2), 0.40: (SLATE, "D", 1.6)}
    for lgd in LGD_SET:
        ys = [grid[(lp, lgd)]["c_star"] / BP for lp in LAMBDA_P_SET]
        col, mk, lw = styles[lgd]
        axr.plot(xs, ys, color=col, lw=lw, marker=mk, ms=4.5)
        axr.text(xs[-1] * 1.07, ys[-1], f"LGD {lgd:.0%}\n{ys[-1]:.0f}", color=col, fontsize=8.8, va="center", ha="left")
    bx, by = LAMBDA_P * 100, ref["c_star"] / BP
    axr.plot([bx], [by], marker="o", ms=10, mfc="none", mec=ACCENT, mew=1.6)
    axr.annotate(f"Base case {by:.0f} bps", xy=(bx, by), xytext=(0.105, 110), fontsize=8.8, color=INK,
                 arrowprops=dict(arrowstyle="-", color="#8C96A3", lw=0.8))
    axr.text(0.56, 46, band_lbl, fontsize=8, color="#9A5A0A", va="top", ha="left")

    frame(fig, "Buying protection costs a fixed transfer cost more than bearing the risk",
          "Clearing cost against the depositor's yield advantage: mu 3, advance dividend 50%, funded vehicle k 10 bps and f 15 bps",
          SRC + " Bearing the risk = credit + access; buying protection = c* = credit + access + k + f.\n"
          "Markers show where each cost crosses a 50 bps advantage. Operating balances often earn an earnings credit rate instead of interest.\n"
          "Illustrative parameters, not estimates for any bank.")
    fig.savefig(FIG(4), dpi=200)
    plt.close(fig)

    # ---- fig-05: portfolio tail, probability of at least n failures among 50 ----------
    fig, ax = plt.subplots(figsize=(8, 5.4))
    fig.subplots_adjust(left=0.12, right=0.85, top=0.8, bottom=0.24)
    nmax = 10
    ns = list(range(1, nmax + 1))
    styles = {0.0: (SLATE, (0, (3, 2)), 1.6, "o"), 0.10: ("#9DB2CF", "-", 2.0, "o"),
              0.20: (STEEL, "-", 2.0, "s"), 0.30: (NAVY, "-", 2.4, "D")}
    ax.axvspan(CLUSTER_N - 0.3, nmax + 0.5, color=ACCENT, alpha=0.10, lw=0)
    ax.text(CLUSTER_N - 0.15, 0.6, "2023-like cluster:\n3 or more failures in a year", fontsize=8.5, color="#9A5A0A",
            va="top", ha="left")
    for rho in PORT_RHO_SET:
        pmf = port[rho]["pmf"]
        exc = [float(pmf[n:].sum()) for n in ns]
        col, ls, lw, mk = styles[rho]
        ax.plot(ns, exc, color=col, ls=ls, lw=lw, marker=mk, ms=4.5)
        lab = "independent" if rho == 0 else f"rho {rho:.2f}"
        last = max(i for i, e in enumerate(exc) if e >= 1.5e-6)      # last point inside the y range
        ax.text(ns[last] + 0.25, exc[last], lab, color=col, fontsize=9, va="center", ha="left")
        if rho in (0.0, 0.30):
            p3 = exc[CLUSTER_N - 1]
            ax.annotate(f"{p3 * 100:.2f}%", xy=(CLUSTER_N, p3), xytext=(CLUSTER_N + 0.6, p3 * (3.5 if rho else 0.25)),
                        fontsize=8.5, color=col, arrowprops=dict(arrowstyle="-", color=col, lw=0.7))
    ax.set_yscale("log")
    ax.set_ylim(1e-6, 1)
    ax.set_yticks([1, 1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6])
    ax.set_yticklabels(["100%", "10%", "1%", "0.1%", "0.01%", "0.001%", "0.0001%"])
    ax.minorticks_off()
    ax.set_xlim(0.6, nmax + 0.4)
    ax.set_xticks(ns)
    ax.set_xticklabels([f"{n}\n{n * LGD_DEP / PORT_N * 100:.1f}%" for n in ns], fontsize=9)
    ax.set_xlabel("At least this many failures among 50 banks in a year (second line: portfolio loss at LGD 25%)",
                  fontsize=9, color=MUTED)
    ax.set_ylabel("Probability per year (log scale)", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    frame(fig, "Clustering leaves the expected loss unchanged and fattens the tail",
          f"50 banks, default probability 0.25% each, one-factor Gaussian copula with asset correlation rho",
          SRC + "\nExact distribution by quadrature over the common factor. Expected failures are 0.125 a year at every rho.\n"
          "rho values are illustrative, not calibrated. Illustrative parameters, not estimates for any bank.")
    fig.savefig(FIG(5), dpi=200)
    plt.close(fig)



def make_figures_v6():
    """fig-06 pooled c* vs fee_F; fig-07 protection failure vs theta; fig-08 cash timeline of a 2023-like year."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    NAVY, STEEL, SLATE, MIST, INK, GRID, ACCENT = "#1F3A5F", "#4F74A8", "#8A9AAE", "#C9D3DF", "#2B2B2B", "#E3E7EC", "#D2851F"
    MUTED = "#4A5361"
    plt.rcParams.update({
        "font.family": "Inter", "font.size": 10, "axes.edgecolor": "#8C96A3", "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "text.color": INK,
    })
    SRC = "Source: author's calculations."

    def frame(fig, title, subtitle, source):
        fig.text(0.06, 0.955, title, fontsize=14, fontweight="semibold", ha="left", va="top", color=INK)
        fig.text(0.06, 0.905, subtitle, fontsize=10, ha="left", va="top", color="#5A6472")
        fig.text(0.06, 0.03, source, fontsize=7.5, ha="left", va="bottom", color="#6B7480")

    # ---- fig-06: pooled c* vs commitment fee, by buffer -------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5.6))
    fig.subplots_adjust(left=0.1, right=0.78, top=0.8, bottom=0.24)
    xmax = 135
    xs = np.linspace(0, xmax, 271)
    ax.axvspan(BANK_FEE_LO / BP, BANK_FEE_HI / BP, color=ACCENT, alpha=0.12, lw=0)
    ax.text((BANK_FEE_LO + BANK_FEE_HI) / 2 / BP, 59.3, "Bank facility cost floor\n(LCR and capital, on my reading)",
            ha="center", va="top", fontsize=8.5, color="#9A5A0A")
    ax.axhline(SINGLE / BP, color=INK, lw=1.4, ls=(0, (4, 2)))
    ax.text(2, SINGLE / BP + 0.5, f"Single-name vehicle {SINGLE / BP:.0f} bps", fontsize=8.8, color=INK, va="bottom")
    cols = {0.05: NAVY, 0.10: STEEL, 0.15: SLATE, 0.20: "#9DB2CF"}
    ends = []
    for th in V5_THETA_SET:
        F_ = max(0.0, V5_CAP - th)
        c0 = pool_price(theta=th, F=F_, fee=0.0)["c_star"] / BP
        ys = c0 + F_ * xs
        ax.plot(xs, ys, color=cols[th], lw=2.2 if th == 0.10 else 1.8)
        fx = [fe / BP for fe in V5_FEE_SET]
        ax.plot(fx, [c0 + F_ * v for v in fx], ls="none", marker="o", ms=4.5, color=cols[th])
        ends.append([th, F_, ys[-1]])
        be = breakeven_fee[(V5_CAP, th, V5_FRIC)]
        if be is not None and 0 < be / BP < xmax:
            ax.plot([be / BP], [SINGLE / BP], marker="o", ms=7, mfc="white", mec=cols[th], mew=1.6, zorder=5)
            left = be / BP < 75                      # thin buffer: label up-left; thicker: below-right, between lines
            ax.annotate(f"Break-even {be / BP:.0f} bps", xy=(be / BP, SINGLE / BP),
                        xytext=(be / BP - 15, SINGLE / BP + 4.4) if left else (be / BP + 10, SINGLE / BP - 1.3),
                        fontsize=8.5, color=cols[th], ha="right" if left else "left", va="center",
                        arrowprops=dict(arrowstyle="-", color=cols[th], lw=0.7))
    # right-end labels, spread to avoid collisions
    ends.sort(key=lambda e: e[2])
    ypos = []
    for e in ends:
        y = e[2] if not ypos else max(e[2], ypos[-1] + 1.9)
        ypos.append(y)
    for e, y in zip(ends, ypos):
        ax.text(xmax + 2, y, f"Buffer {e[0]:.0%}, facility {e[1]:.0%}", color=cols[e[0]], fontsize=8.8, va="center", ha="left",
                clip_on=False)
    ax.set_xlim(0, xmax)
    ax.set_ylim(30, 60)
    ax.set_xlabel("Commitment fee on the undrawn liquidity facility, bps a year", fontsize=9.5, color=MUTED)
    ax.set_ylabel("Clearing cost c*, bps per year on the covered balance", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    frame(fig, "A pooled vehicle is cheaper only while its liquidity line is cheap",
          "Pooled vehicle clearing cost by commitment fee: 50 banks at 2% each, buffer plus facility = 20% of notional",
          SRC + " PD 0.25%, mu 3, rho 0.20, deposit LGD 25%, advance dividend 50%, frictions 15 bps, buffer lock premium\n"
          "10 bps. Dots mark the swept fees of 5, 10, 20 and 40 bps; circles on the dashed line mark break-even fees. Bank floor: 100% LCR\n"
          "outflow x 40 bps carry plus capital at 20% to 100% CCF x 20% to 100% risk weight. Illustrative parameters, not estimates for any bank.")
    fig.savefig(FIG(6), dpi=200)
    plt.close(fig)

    # ---- fig-07: probability the vehicle cannot pay par, by buffer -------------------------
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(10, 6.2))
    fig.subplots_adjust(left=0.115, right=0.97, top=0.78, bottom=0.31, wspace=0.34)
    thg = np.round(np.arange(0.0, 0.2501, 0.005), 4)
    Pf = pool(LAMBDA_P, V5_RHO_FAIL, "corr")
    Pt = pool(LAMBDA_P, V5_RHO_FAIL, "fixed", copula="t")
    FLOOR = 1e-7

    def curve(fn):
        return [max(fn(t), FLOOR) for t in thg]

    styles = [(0.0, SLATE, "-", 1.8, "No facility"), (0.10, NAVY, "-", 2.4, "Facility 10%"),
              (0.20, "#9DB2CF", "-", 1.8, "Facility 20%")]
    for F_, col, ls, lw, lab in styles:
        axl.plot(thg * 100, curve(lambda t, F_=F_: p_fail(Pf, t, F_)), color=col, ls=ls, lw=lw, drawstyle="steps-post", label=lab)
    axl.plot(thg * 100, curve(lambda t: p_fail(Pf, t, 0.10, prov=(V5_PROV_PD, V5_PROV_RHO))), color=ACCENT, ls=(0, (4, 2)),
             lw=1.8, drawstyle="steps-post", label="Facility 10%, bank provider")
    axl.plot(thg * 100, curve(lambda t: p_fail(Pt, t, 0.10)), color=NAVY, ls=(0, (1, 1.5)), lw=1.8, drawstyle="steps-post",
             label="Facility 10%, t(5) copula")
    pref = p_fail(Pf, 0.20, 0.0)
    axl.plot([20], [pref], marker="o", ms=8, mfc="white", mec=ACCENT, mew=2.0, zorder=6)
    axl.annotate(f"Reference design:\nall-funded 20% buffer,\nno facility, {pref * 100:.4f}%", xy=(20, pref), xytext=(9.0, 2.2e-7),
                 fontsize=8.2, color="#9A5A0A", ha="left", va="bottom", arrowprops=dict(arrowstyle="-", color=ACCENT, lw=0.8))
    axl.axhline(LAMBDA_P, color=INK, lw=0.9, ls=(0, (6, 3)))
    axl.text(25, LAMBDA_P * 1.35, "One reference bank's PD, 0.25%", fontsize=8.3, color=INK, ha="right", va="bottom")
    axl.set_title("Cannot pay par at T+0 (protection fails)", loc="left", fontsize=10.5, fontweight="semibold", pad=10)
    for ax_ in (axl, axr):
        ax_.set_yscale("log")
        ax_.set_ylim(FLOOR, 0.1)
        ax_.set_yticks([1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6, 1e-7])
        ax_.set_yticklabels(["10%", "1%", "0.1%", "0.01%", "0.001%", "0.0001%", "0.00001%"])
        ax_.minorticks_off()
        ax_.set_xlim(0, 25)
        ax_.set_xticks([0, 5, 10, 15, 20, 25])
        ax_.set_xticklabels([f"{v}%" for v in [0, 5, 10, 15, 20, 25]])
        ax_.set_xlabel("Funded T-bill buffer, % of covered notional", fontsize=9, color=MUTED)
        ax_.yaxis.grid(True, color=GRID, lw=0.8)
        ax_.set_axisbelow(True)
    axl.set_ylabel("Probability per year (log scale)", fontsize=9.5, color=MUTED)
    axl.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False, fontsize=8.4, handlelength=2.2)
    Pfx = pool(LAMBDA_P, V5_RHO_FAIL, "fixed")
    rstyles = [(Pfx, lambda P_: term_need(P_), STEEL, "-", "Terms out, fixed LGD"),
               (Pf, lambda P_: term_need(P_), STEEL, (0, (4, 2)), "Terms out, correlated LGD"),
               (Pfx, lambda P_: credit_loss(P_), NAVY, "-", "Loss above buffer, fixed LGD"),
               (Pf, lambda P_: credit_loss(P_), NAVY, (0, (4, 2)), "Loss above buffer, correlated LGD")]
    for P_, fn, col, ls, lab in rstyles:
        x_ = fn(P_)
        axr.plot(thg * 100, curve(lambda t, P_=P_, x_=x_: Pr(P_, x_ > t + EPS)), color=col, ls=ls, lw=2.0,
                 drawstyle="steps-post", label=lab)
    axr.set_title("After par is paid: the facility's exposure", loc="left", fontsize=10.5, fontweight="semibold", pad=10)
    axr.legend(loc="upper center", bbox_to_anchor=(0.45, -0.15), ncol=2, frameon=False, fontsize=8.2, handlelength=2.0,
               columnspacing=1.0)
    frame(fig, "A small buffer makes protection fail rarely, and the tail model decides how rarely",
          "50 banks at 2% each, PD 0.25%, rho 0.30, correlated LGD 15% to 40%, all of a year's failures in one advance-dividend window",
          SRC + " Circle: the reference design, a 20% buffer and no facility. Bank provider: PD 0.10% on the same common factor\n"
          "(loading 0.30). Terms out: cash still owed after "
          "the advance dividend exceeds the buffer. Fixed LGD 25%. Left panel does not depend on LGD under this timing standard.\n"
          "Illustrative parameters, not estimates for any bank.")
    fig.savefig(FIG(7), dpi=200)
    plt.close(fig)

    # ---- fig-08: cash timeline of a 2023-like three-failure year --------------------------
    fig, ax = plt.subplots(figsize=(8, 5.6))
    fig.subplots_adjust(left=0.1, right=0.8, top=0.8, bottom=0.3)
    w_ = 1.0 / V5_N
    days = np.arange(0, 121, 0.25)
    adv_part = np.zeros_like(days)
    bridge = np.zeros_like(days)
    loss = np.zeros_like(days)
    for t_ in V5_TIMELINE_DAYS:
        on = days >= t_
        waiting = on & (days < t_ + V5_ADV_LAG_DAYS)
        adv_part += np.where(waiting, w_ * ADV_DIV, 0.0)
        bridge += np.where(on, w_ * (1 - ADV_DIV - LGD_DEP), 0.0)
        loss += np.where(on, w_ * LGD_DEP, 0.0)
    ax.stackplot(days, loss * 100, bridge * 100, adv_part * 100, colors=[NAVY, STEEL, MIST], step="post", lw=0)
    total = (loss + bridge + adv_part) * 100
    ax.plot(days, total, color=INK, lw=0.8, drawstyle="steps-post")
    for th, lab in ((0.05, "Buffer 5%"), (0.10, "Buffer 10%")):
        ax.axhline(th * 100, color=ACCENT, lw=1.6, ls="-" if th == 0.10 else (0, (4, 2)))
        ax.text(121, th * 100, lab, color="#9A5A0A", fontsize=8.8, va="center", ha="left", clip_on=False)
    ax.axhline(3 * w_ * 100, color=INK, lw=1.0, ls=(0, (1, 1.5)))
    ax.text(121, 3 * w_ * 100, "All three on one\nweekend: 6% at T+0", color=INK, fontsize=8.5, va="center", ha="left", clip_on=False)
    pk = float(total.max())
    ax.annotate(f"Peak {pk:.0f}% of notional", xy=(3, pk), xytext=(12, 7.3), fontsize=8.8, color=INK,
                arrowprops=dict(arrowstyle="-", color="#8C96A3", lw=0.7))
    ax.annotate("Third failure", xy=(V5_TIMELINE_DAYS[2], total[np.searchsorted(days, V5_TIMELINE_DAYS[2])]),
                xytext=(V5_TIMELINE_DAYS[2] + 8, 7.3), fontsize=8.8, color=INK,
                arrowprops=dict(arrowstyle="-", color="#8C96A3", lw=0.7))
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 11)
    ax.set_yticks(range(0, 11, 2))
    ax.set_yticklabels([f"{v}%" for v in range(0, 11, 2)])
    ax.set_xlabel("Days after the first failure", fontsize=9.5, color=MUTED)
    ax.set_ylabel("Vehicle cash outstanding, % of covered notional", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    handles = [Patch(color=MIST, label=f"Paid at T+0, advance dividend due in {V5_ADV_LAG_DAYS} days"),
               Patch(color=STEEL, label="Bridge to final recovery (about 2 years)"),
               Patch(color=NAVY, label="Final loss")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.105), ncol=2, frameon=False, fontsize=8.8, handlelength=1.2)
    frame(fig, "A 2023-like year needs 4 to 6 percent of the pool in cash",
          "Cash the pooled vehicle has paid out and not recovered: three failures, each bank 2% of the pool",
          SRC + " Two failures over one weekend and a third about seven weeks later, an illustrative timing modelled\n"
          "on spring 2023. Advance dividend 50% after 7 days (an assumption from FDIC practice), deposit LGD 25%. Recoveries after\n"
          "the advance dividend arrive over about two years, beyond the right edge. Illustrative parameters, not estimates for any bank.")
    fig.savefig(FIG(8), dpi=200)
    plt.close(fig)


# =============================================================================
# 6b. v7 PART III: WHY PRIVATE CAPITAL WOULD WRITE IT, AND WHAT TECHNOLOGY CHANGES
# =============================================================================
# --- v7 parameters (each defined once). All are scenarios or sweep points, not estimates. ---------
V7_FRIC_SET = [15 * BP, 10 * BP, 7.5 * BP, 5 * BP]   # frictions f: base, then automated monitoring, underwriting and
                                                      # standardized documentation (scenarios, not estimates)
V7_FAC_SET = [0.10, 0.075, 0.05, 0.0]                # committed facility at the mid design's 10% buffer
V7_CAPACITY = V5_MID["theta"] + V5_MID["F"]          # same-day capacity held at 20% of notional (v5 design rule)
V7_MARKERS = [31 * BP, 34 * BP]                      # reference prices: 31 (low-end marker), 34 (mid design at f 10)
V7_MARK_TOL = 0.5 * BP                               # "about": rounds to the marker in whole bps
V7_TAIL_Q = 0.995                                    # tail for the return-on-tail-risk ratio
V7_REL_V = [50 * BP, 100 * BP, 150 * BP]             # relationship value, bps a year of the covered balance
V7_REL_LIFE = 5                                      # expected relationship life L, years
V7_REL_DISC = R_FREE + 0.03                          # discount rate r + 3%
V7_DP_RUN = [0.005, 0.01, 0.02, 0.05]                # reduction in the annual probability the depositor leaves in a run
V7_SPLIT = 0.50                                      # bank's share s of the premium, bank-sponsored variant


# --- A. Technology scenarios on the transfer cost ----------------------------------------------------
def pool_price_mobile(F_commit, f=V5_FRIC, **kw):
    """Mid design with same-day capacity held at V7_CAPACITY. The committed facility is F_commit; the rest,
    m x theta with m = (V7_CAPACITY - theta - F_commit) / theta, is same-day cash from the mobile buffer that the
    v6 accounting does not credit. Only the commitment fee is saved: amounts drawn from that same-day source are
    charged at the facility's drawn cost (assumption), so the expected drawn cost is unchanged."""
    th = V5_MID["theta"]
    full = pool_price(**{**V5_MID, "F": V7_CAPACITY - th, "f": f, **kw})
    saved = (V7_CAPACITY - th - F_commit) * V5_MID["fee"]
    out = dict(full)
    out["commit"] = full["commit"] - saved
    out["k"] = full["k"] - saved
    out["c_star"] = full["c_star"] - saved
    out["m"] = (V7_CAPACITY - th - F_commit) / th
    return out


v7_single = {fr: components(k=FUND_K, f=fr)["c_star"] for fr in V7_FRIC_SET}
v7_grid = {(fr, Fc): pool_price_mobile(Fc, f=fr)["c_star"] for fr in V7_FRIC_SET for Fc in V7_FAC_SET}
v7_mob = {}
for Fc in V7_FAC_SET:
    pm = pool_price_mobile(Fc)
    v7_mob[Fc] = dict(m=pm["m"], c=pm["c_star"], commit=pm["commit"],
                      fail_depth=p_fail(P_fail_base, V5_MID["theta"], V7_CAPACITY - V5_MID["theta"]),
                      fail_nodepth=p_fail(P_fail_base, V5_MID["theta"], Fc),
                      fail_depth_t=p_fail(pool(LAMBDA_P, V5_RHO_FAIL, "fixed", copula="t"), V5_MID["theta"],
                                          V7_CAPACITY - V5_MID["theta"]),
                      fail_nodepth_t=p_fail(pool(LAMBDA_P, V5_RHO_FAIL, "fixed", copula="t"), V5_MID["theta"], Fc))
# frictions at which each facility size reaches each marker (c* is linear in f, slope 1)
v7_f_needed = {(Fc, t_): t_ - (pool_price_mobile(Fc, f=0.0)["c_star"]) for Fc in V7_FAC_SET for t_ in V7_MARKERS}
v7_single_f_needed = {t_: t_ - components(k=FUND_K, f=0.0)["c_star"] for t_ in V7_MARKERS}
# Reverse reading: a conventional buffer that is not same-day cash at a weekend trigger
v7_conv = dict(fail_F10=p_fail(P_fail_base, 0.0, V5_MID["F"]),
               c_F20=pool_price(**{**V5_MID, "F": V7_CAPACITY})["c_star"])


def v7_mark(c):
    hits = [t_ for t_ in V7_MARKERS if abs(c - t_) <= V7_MARK_TOL]
    return f"**{b1(c)}** (about {hits[0] / BP:.0f})" if hits else b1(c)


# --- B. Investor return view ----------------------------------------------------------------------
def tail_es(x, p, q=V7_TAIL_Q):
    """Expected loss in the worst (1 - q) of years (expected shortfall), ties split pro rata."""
    order = np.argsort(x)[::-1]
    xs, ps = x[order], p[order]
    alpha = 1.0 - q
    before = np.cumsum(ps) - ps
    take = np.minimum(ps, np.clip(alpha - before, 0.0, None))
    return float((xs * take).sum() / alpha)


v7_inv = []
_Pi = pool(LAMBDA_P, V5_MID["rho"], V5_MID["mode"])
_li = np.broadcast_to(credit_loss(_Pi), _Pi["joint"].shape).ravel()
_pi = _Pi["joint"].ravel()
for tr, sp, sq in tranche_v6[(V5_MID["rho"], V5_MID["mode"])][:3]:          # equity, mezzanine, funded senior
    _, A, Dt = tr
    tl = np.clip(_li - A, 0, Dt - A) / (Dt - A)
    v7_inv.append(dict(name=f"Pooled {tr[0].split(',')[0].lower()} {pc(A, 0)} to {pc(Dt, 0)}", spread=sq["el"],
                       el=sp["el"], p_any=sp["p_hit"], var=quantile(tl, _pi, V7_TAIL_Q), es=tail_es(tl, _pi)))
# single-name first loss (v3 A): loses fl_loss of the tranche with probability lambda_P, nothing otherwise
_x1 = np.array([0.0, tr_base["fl_loss"]])
_p1 = np.array([1.0 - LAMBDA_P, LAMBDA_P])
v7_inv.append(dict(name=f"Single-name first loss 0% to {pc(tr_base['T'], 0)}", spread=tr_base["fl_spread"],
                   el=tr_base["fl_el"], p_any=LAMBDA_P, var=quantile(_x1, _p1, V7_TAIL_Q), es=tail_es(_x1, _p1)))
for row in v7_inv:
    row["excess"] = row["spread"] - row["el"]
    row["r_var"] = row["excess"] / row["var"] if row["var"] > 0 else None
    row["r_es"] = row["excess"] / row["es"] if row["es"] > 0 else None
V7_LOCK_PER_TRANCHE = V5_S_LOCK                       # if the buffer lock premium were paid pro rata to the buffer


# --- C. Bank willingness to pay, bank-sponsored variant ----------------------------------------------
V7_ANNUITY = (1.0 - (1.0 + V7_REL_DISC) ** -V7_REL_LIFE) / V7_REL_DISC     # end-of-year payments
v7_wtp = {(V, dp): dp * V * V7_ANNUITY for V in V7_REL_V for dp in V7_DP_RUN}
v7_bench = [("Single-name vehicle, f 15", v7_single[15 * BP]),
            ("Pooled mid design, f 15", v7_grid[(15 * BP, 0.10)]),
            ("Pooled mid design, f 10", v7_grid[(10 * BP, 0.10)]),
            ("Pooled mid design, f 7.5", v7_grid[(7.5 * BP, 0.10)]),
            ("Pooled, f 5, no committed facility", v7_grid[(5 * BP, 0.0)])]
v7_dp_needed = {(V, name): V7_SPLIT * c / (V * V7_ANNUITY) for V in V7_REL_V for name, c in v7_bench}


def write_results_v7():
    write_results_v6()                                # Parts I and II: v6 lines, unchanged
    L = [RESULTS_MD.read_text(encoding="utf-8").rstrip("\n"), ""]
    L.append("---\n")
    L.append("# Part III. Why private capital would write it, and what technology changes\n")
    L.append("Part III code is unchanged since v7. Every input in it is a scenario or a sweep point, labelled as such; none is calibrated "
             "and none is an estimate for any bank, vehicle or investor.\n")

    # 30. conventions
    L.append("## 30. Conventions for Part III\n")
    L.append(f"- Pooled mid design throughout: theta {pc(V5_MID['theta'], 0)}, F {pc(V5_MID['F'], 0)}, fee_F "
             f"{V5_MID['fee'] / BP:.0f} bps, rho {V5_MID['rho']:.2f}, LGD 25% fixed, lambda_P 0.25%, mu 3 (c* "
             f"{b1(mid['c_star'])} bps, Section 22). Single-name vehicle: k 10, c* {b1(SINGLE)} bps at f 15 (Section 2).")
    L.append(f"- Frictions f of 10, 7.5 and 5 bps are technology scenarios (AI-driven monitoring, automated underwriting, "
             "standardized documentation), not estimates. c* falls one for one with f in both vehicles.")
    L.append(f"- Buffer mobility. v6 counts the whole buffer at par as cash at T+0 and puts every dollar above it on the "
             f"committed facility, so same-day capacity is theta + F = {pc(V7_CAPACITY, 0)}. By assumption, a "
             "buffer held in tokenized T-bills or money-fund shares, monetizable intraday and around the clock, is credited with "
             "an extra share m of theta as same-day cash at the trigger (net of any haircut), beyond the v6 accounting. The "
             f"committed facility is cut by m x theta, so capacity stays at {pc(V7_CAPACITY, 0)}: m = 25%, 50%, 100% gives F = "
             "7.5%, 5%, 0. Only the commitment fee is saved; amounts drawn from the same-day source are charged at the "
             "facility's drawn cost.")
    L.append("- Market-depth caveat. The extra same-day cash is uncommitted. Protection failure is therefore shown twice: "
             "if that depth is there in the stress year (capacity unchanged, so the v6 probability), and if it is not "
             "(capacity = theta + committed F). Failure statistics use the v6 reference: rho 0.30, correlated LGD, Gaussian "
             "copula, simultaneous standard, P-measure; t(5) copula alongside.")
    L.append("- Markers: 31 bps (a low-end reference price, Section 22) and 34 bps (the mid design at f 10). A cell is "
             "marked when it rounds to the marker in whole bps.\n")

    # 31. A
    L.append("## 31. A. Technology sensitivity on the transfer cost (scenarios, not estimates)\n")
    L.append("Frictions alone, bps:\n")
    L.append(table(["Frictions f (scenario)", "Single-name vehicle c*", "Pooled mid design c*", "Transfer cost k + f, pooled"],
                   [[b1(fr), b1(v7_single[fr]), b1(v7_grid[(fr, 0.10)]), b1(mid["k"] + fr)] for fr in V7_FRIC_SET]))
    L.append("")
    L.append("Buffer mobility at f 15 (pooled mid design, same-day capacity held at 20%):\n")
    L.append(table(["Committed facility F", "Extra same-day share of buffer m", "Commitment fee paid (bps)", "c* (bps)",
                    "P(cannot pay par), depth holds", "P(cannot pay par), no depth", "years, no depth",
                    "t(5): depth holds / no depth"],
                   [[pc(Fc, 1), pc(v["m"], 0), b1(v["commit"]), b1(v["c"]), fp(v["fail_depth"]), fp(v["fail_nodepth"]),
                     one_in(v["fail_nodepth"]), f"{fp(v['fail_depth_t'])} / {fp(v['fail_nodepth_t'])}"]
                    for Fc, v in v7_mob.items()]))
    L.append("")
    L.append("Combined grid: c* (bps) by frictions and committed facility. Pooled columns hold same-day capacity at 20% "
             "through buffer mobility (m = 0, 25%, 50%, 100%). Bold marks cells at about 31 or 34 bps.\n")
    L.append(table(["Frictions f (scenario)", "Single-name vehicle"] + [f"Pooled, F {pc(Fc, 1)} (m {pc(v7_mob[Fc]['m'], 0)})"
                                                                     for Fc in V7_FAC_SET],
                   [[b1(fr), v7_mark(v7_single[fr])] + [v7_mark(v7_grid[(fr, Fc)]) for Fc in V7_FAC_SET]
                    for fr in V7_FRIC_SET]))
    L.append("")
    L.append("Frictions (bps) at which each design reaches the markers ('none' = would need negative frictions):\n")
    L.append(table(["Design"] + [f"c* = {t_ / BP:.0f}" for t_ in V7_MARKERS],
                   [["Single-name vehicle"] + [b1(v7_single_f_needed[t_]) if v7_single_f_needed[t_] > 0 else "none"
                                               for t_ in V7_MARKERS]] +
                   [[f"Pooled, F {pc(Fc, 1)}"] + [b1(v7_f_needed[(Fc, t_)]) if v7_f_needed[(Fc, t_)] > 0 else "none"
                                                  for t_ in V7_MARKERS] for Fc in V7_FAC_SET]))
    L.append("")
    L.append(f"Reverse reading (memo). If a conventional buffer is not same-day cash at a weekend or after-hours trigger, the "
             f"v6 mid design's T+0 capacity is the {pc(V5_MID['F'], 0)} facility alone, and P(cannot pay par at T+0) is "
             f"{fp(v7_conv['fail_F10'])} ({one_in(v7_conv['fail_F10'])}) rather than {fp(CR_P0)}. Restoring 20% with a "
             f"conventional buffer needs F = 20%, c* {b1(v7_conv['c_F20'])} bps. On this reading, mobility's first job is to "
             "make the v6 accounting true; cutting the facility is the second.\n")

    # 32. B
    L.append("## 32. B. Investor return view (illustrative)\n")
    L.append(f"Pooled tranches at the mid design (rho {V5_MID['rho']:.2f}, LGD 25% fixed, theta 10%), as modelled in Section 24: "
             "spread over T-bills = the tranche's Q-expected loss on its own size (copula run at mu x lambda_P). Single-name "
             "first loss as in Section 10: earns credit + access on a 25% tranche. Expected loss and the tail are P-measure "
             f"(lambda_P 0.25%). All figures % of the tranche per year. Tail loss at {V7_TAIL_Q:.1%}: the quantile (VaR) and "
             "the expected loss in the worst 0.5% of years (ES). Return on tail risk = excess spread / tail loss. "
             "Illustrative; not a forecast of investor returns.\n")
    rr = lambda x: "n/a (VaR 0)" if x is None else f"{x * 100:.2f}%"
    L.append(table(["Tranche", "Spread over T-bills", "Expected loss", "Excess spread", "P(any loss)",
                    f"{V7_TAIL_Q:.1%} VaR", f"{V7_TAIL_Q:.1%} ES", "Excess / VaR", "Excess / ES"],
                   [[r_["name"], pel(r_["spread"]), pel(r_["el"]), pel(r_["excess"]), fp(r_["p_any"]), pc(r_["var"], 1),
                     pc(r_["es"], 1), rr(r_["r_var"]), rr(r_["r_es"])] for r_ in v7_inv]))
    L.append("")
    L.append(f"As modelled, the buffer lock premium (theta x s_lock = {b1(V5_MID['theta'] * V5_S_LOCK)} bps of notional) and "
             f"the access term are not allocated to the pooled tranches. Paid pro rata on the buffer it would add "
             f"{V7_LOCK_PER_TRANCHE / BP:.0f} bps a year to each pooled tranche's spread and excess spread. A single-name first "
             f"loss loses nothing at the {V7_TAIL_Q:.1%} quantile because one bank's PD (0.25%) is below 0.5%, so its VaR ratio "
             "is undefined and the ES ratio is the comparable measure.\n")

    # 33. C
    L.append("## 33. C. Bank willingness to pay, bank-sponsored variant (illustrative)\n")
    L.append(f"WTP = dP_run x PV(relationship). V is the relationship value in bps a year of the covered balance (net interest "
             f"margin on the deposit, fees, cross-sell). PV = V x annuity factor over L = {V7_REL_LIFE} years at r + 3% = "
             f"{pc(V7_REL_DISC, 1)}, end-of-year payments: factor {V7_ANNUITY:.3f}. dP_run is the cut in the annual probability "
             f"that this depositor leaves in a run. The bank pays a share s = {pc(V7_SPLIT, 0)} of c*. Rational when WTP >= "
             "s x c*. Every input is a sweep point, not a calibration; the run-cost savings to the bank (liquidity held "
             "against the balance, fire-sale risk) are left out, so WTP is a floor on that count.\n")
    L.append("WTP, bps a year of the covered balance:\n")
    L.append(table(["V (bps a year)", "PV of relationship (bps)"] + [f"dP_run {pc(dp, 1)}" for dp in V7_DP_RUN],
                   [[f"{V / BP:.0f}", f"{V * V7_ANNUITY / BP:.0f}"] + [b1(v7_wtp[(V, dp)]) for dp in V7_DP_RUN]
                    for V in V7_REL_V]))
    L.append("")
    L.append("Bank's 50% share of c* (bps a year): " + "; ".join(f"{n_} {b1(V7_SPLIT * c)} (c* {b1(c)})" for n_, c in v7_bench)
             + ".\n")
    L.append("Does WTP cover the bank's share? Y = rational for the bank to sponsor at that price:\n")
    L.append(table(["V", "dP_run", "WTP"] + [n_ for n_, _ in v7_bench],
                   [[f"{V / BP:.0f}", pc(dp, 1), b1(v7_wtp[(V, dp)])] +
                    ["Y" if v7_wtp[(V, dp)] >= V7_SPLIT * c else "-" for _, c in v7_bench]
                    for V in V7_REL_V for dp in V7_DP_RUN]))
    L.append("")
    L.append("Break-even dP_run (the cut in run probability that makes sponsorship pay):\n")
    L.append(table(["V (bps a year)"] + [n_ for n_, _ in v7_bench],
                   [[f"{V / BP:.0f}"] + [pc(v7_dp_needed[(V, n_)], 1) for n_, _ in v7_bench] for V in V7_REL_V]))
    L.append("")

    # 34. summary
    yes = [(V, dp) for V in V7_REL_V for dp in V7_DP_RUN if v7_wtp[(V, dp)] >= V7_SPLIT * v7_bench[1][1]]
    eq, mz, sr, sn = v7_inv
    o = [
        f"Frictions move the price more than the facility. At the pooled mid design, f from 15 to 10, 7.5 and 5 bps takes c* "
        f"from {b1(v7_grid[(15 * BP, 0.10)])} to {b1(v7_grid[(10 * BP, 0.10)])}, {b1(v7_grid[(7.5 * BP, 0.10)])} and "
        f"{b1(v7_grid[(5 * BP, 0.10)])} bps; the single-name vehicle goes from {b1(v7_single[15 * BP])} to "
        f"{b1(v7_single[5 * BP])}. Dropping the committed facility altogether saves {b1(V5_MID['F'] * V5_MID['fee'])} bps.",
        f"The 34 bps marker is the mid design at f 10 ({b1(v7_grid[(10 * BP, 0.10)])}); the 31 bps marker needs f 7.5 "
        f"({b1(v7_grid[(7.5 * BP, 0.10)])}), or f {b1(v7_f_needed[(0.0, 31 * BP)])} with no committed facility. The "
        f"single-name vehicle would need f {b1(v7_single_f_needed[31 * BP])} for 31 and {b1(v7_single_f_needed[34 * BP])} for 34.",
        f"Mobility is a liquidity trade, not a price trade. Cutting F from 10% to 0 leaves P(cannot pay par) at "
        f"{fp(CR_P0)} only if the same-day market is there in the cluster year; without it the probability rises to "
        f"{fp(v7_mob[0.0]['fail_nodepth'])} ({one_in(v7_mob[0.0]['fail_nodepth'])}).",
        f"Investors: the pooled equity earns {pel(eq['excess'])} a year over its expected loss with a {fp(eq['p_any'])} "
        f"chance of any loss, {rr(eq['r_es'])} of its tail loss (ES); the single-name first loss earns {pel(sn['excess'])} "
        f"excess, {rr(sn['r_es'])} of its ES. Per unit of tail the senior ({rr(sr['r_es'])}) is close to the equity, but on "
        f"{pel(sr['excess'])} of excess and a {pc(sr['es'], 1)} ES; the mezzanine ({rr(mz['r_es'])}) and the single-name "
        "first loss trail.",
        "Bank sponsorship is rational against the pooled mid price only at "
        + ", ".join(f"V {V / BP:.0f} with dP_run {pc(dp, 1)}" for V, dp in yes)
        + f". At V 100 the break-even dP_run is {pc(v7_dp_needed[(100 * BP, v7_bench[1][0])], 1)} a year.",
    ]
    L.append("## 34. What the v7 numbers say\n")
    L.extend(f"{i}. {t}" for i, t in enumerate(o, 1))
    L.append("")
    L.append("v7 modelling notes (specification issues and choices):\n")
    flags = [
        "Buffer mobility: v6 already counts the buffer at par as T+0 cash, so a mobile buffer cannot add capacity under "
        "the v6 accounting on its own. The extra m x theta is an author assumption (uncommitted same-day "
        "cash, net of haircut) and the 'no depth' column is its honest downside.",
        "Pooled tranche spreads are Q-expected loss only, as modelled in Section 24; the lock premium and access are not "
        "allocated to tranches. Spreads for a real deal would be set by the market.",
        "WTP omits the bank's own run-cost savings and any brokered-deposit or implicit-support cost.",
    ]
    L.extend(f"{i}. {t}" for i, t in enumerate(flags, 1))
    L.append("")
    RESULTS_MD.write_text("\n".join(L), encoding="utf-8")


def make_figure_v7():
    """fig-09: c* versus frictions for committed facility 10%, 5% and 0, with the single-name line and markers."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    NAVY, STEEL, SLATE, INK, GRID, ACCENT = "#1F3A5F", "#4F74A8", "#8A9AAE", "#2B2B2B", "#E3E7EC", "#D2851F"
    MUTED = "#4A5361"
    plt.rcParams.update({
        "font.family": "Inter", "font.size": 10, "axes.edgecolor": "#8C96A3", "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "text.color": INK,
    })
    SRC = "Source: author's calculations."

    fig, ax = plt.subplots(figsize=(8, 5.6))
    fig.subplots_adjust(left=0.1, right=0.66, top=0.8, bottom=0.24)
    xs = np.linspace(4, 16, 241)
    XR = 3.7                                                 # just right of the plot (the axis runs 16 to 4)
    ax.axhline(SINGLE / BP, color=INK, lw=1.4, ls=(0, (4, 2)))
    ax.text(15.8, SINGLE / BP + 0.4, f"Single-name vehicle at 15 bps frictions, {SINGLE / BP:.0f} bps", fontsize=8.8,
            color=INK, va="bottom")
    for t_ in V7_MARKERS:
        ax.axhline(t_ / BP, color=ACCENT, lw=1.0, ls=(0, (1, 1.5)))
        ax.text(XR, t_ / BP, f"{t_ / BP:.0f} bps", color="#9A5A0A", fontsize=8.8, va="center", ha="left", clip_on=False)
    cols = {0.10: STEEL, 0.0: SLATE}
    ends = []
    c0r = pool_price(**{**V5_MID, "theta": 0.20, "F": 0.0, "f": 0.0})["c_star"] / BP      # all-funded reference, f = 0
    ax.plot(xs, c0r + xs, color=NAVY, lw=2.6)
    ax.plot([fr / BP for fr in V7_FRIC_SET], [c0r + fr / BP for fr in V7_FRIC_SET], ls="none", marker="o", ms=5, color=NAVY)
    for t_ in V7_MARKERS:
        fx = t_ / BP - c0r
        if 4 <= fx <= 16:
            ax.plot([fx], [t_ / BP], marker="o", ms=7, mfc="white", mec=NAVY, mew=1.6, zorder=5)
    ends.append([c0r + 4, "All-funded 20% buffer (reference)", NAVY])
    for Fc in (0.10, 0.0):
        c0 = pool_price_mobile(Fc, f=0.0)["c_star"] / BP
        ax.plot(xs, c0 + xs, color=cols[Fc], lw=1.8)
        sx = [fr / BP for fr in V7_FRIC_SET]
        ax.plot(sx, [c0 + v for v in sx], ls="none", marker="o", ms=4.5, color=cols[Fc])
        for t_ in V7_MARKERS:
            fx = t_ / BP - c0
            if 4 <= fx <= 16:
                ax.plot([fx], [t_ / BP], marker="o", ms=7, mfc="white", mec=cols[Fc], mew=1.6, zorder=5)
        lab = "Buffer 10%, facility 10% (hybrid)" if Fc == 0.10 else "Buffer 10%, tokenized, no facility"
        ends.append([c0 + 4, lab, cols[Fc]])
    ends.sort(key=lambda e: e[0])
    ypos = []
    for e in ends:
        ypos.append(e[0] if not ypos else max(e[0], ypos[-1] + 1.4))
    for e, y in zip(ends, ypos):
        ax.text(XR, y, e[1], color=e[2], fontsize=8.6, va="center", ha="left", clip_on=False)
    ax.set_xlim(16, 4)                                       # frictions fall from left to right
    ax.set_xticks([15, 12.5, 10, 7.5, 5])
    ax.set_xticklabels(["15", "12.5", "10", "7.5", "5"])
    ax.set_ylim(22, 50)
    ax.set_xlabel("Frictions f, bps a year (scenarios: monitoring, underwriting and documentation costs fall)",
                  fontsize=9.5, color=MUTED)
    ax.set_ylabel("Clearing cost c*, bps per year on the covered balance", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    title = "Cheaper frictions move the price more than the choice of facility"
    sub = "Pooled vehicle clearing cost by frictions, same-day capacity held at 20% of notional"
    fig.text(0.06, 0.955, title, fontsize=14, fontweight="semibold", ha="left", va="top", color=INK)
    fig.text(0.06, 0.905, sub, fontsize=10, ha="left", va="top", color="#5A6472")
    fig.text(0.06, 0.03,
             SRC + " Reference design: 20% T-bill buffer, no facility, lock-up premium 10 bps. Hybrid: buffer 10%,\n"
             "facility 10% at a 20 bps fee. Tokenized variant: buffer 10% that is same-day cash at any hour stands in for the\n"
             "facility, which needs market depth in a cluster year. PD 0.25%, mu 3, rho 0.20, deposit LGD 25%. Dots mark frictions\n"
             "of 15, 10, 7.5 and 5 bps; circles mark where a line reaches 31 or 34 bps. The single-name vehicle also falls one for one\n"
             "with frictions. Scenarios and illustrative parameters, not estimates for any bank.",
             fontsize=7.5, ha="left", va="bottom", color="#6B7480")
    fig.savefig(FIG(9), dpi=200)
    plt.close(fig)


# =============================================================================
# 6c. v8 PART IV: REFERENCE DESIGN, RELIABILITY GIVEN THE DEPOSITOR'S OWN BANK FAILS, YEAR 2, CLEARING
# =============================================================================
# --- v8 parameters (each defined once). Design choices and scenarios, not estimates. ------------------
V8_CAP = V5_CAP                                       # capacity: par on 10 simultaneous failures (20% of notional)
V8_REF = dict(pd=LAMBDA_P, rho=V5_RHO_MID, mode="fixed", theta=V8_CAP, F=0.0, fee=20 * BP)   # all-funded reference
V8_HYB = V5_MID                                       # 10/10 hybrid at a 20 bps fee: a variant
V8_SLOCK_SET = [5 * BP, 10 * BP, 15 * BP, 20 * BP, 30 * BP, 45 * BP]   # lock-up premium sweep (45 = a sweep point only)
V8_SPLITS = [(0.20, 0.0), (0.15, 0.05), (0.10, 0.10), (0.05, 0.15)]   # theta / F at 20% capacity
V8_RULE_LGD = [0.25, 0.40]
V8_RULE_ADV = [0.50, 0.30]
V8_CAPS = [0.06, 0.10, 0.12, 0.16, 0.20, 0.24, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
V8_COPULAS = [("gauss", "Gaussian"), ("t", "Student-t(5)")]
V8_STANDARDS = [0.10, 0.05, 0.02, 0.01]               # round conditional reliability standards
V8_N_SET = [10, 20, 25, 40, 50, 80, 100]               # pool size sweep (each bank 1/N of notional)
V8_N_STD = {"gauss": 0.01, "t": 0.05}                  # standards for the pool-size sweep
V8_Y1_N = [3, 6]                                      # year-1 cluster sizes
V8_Y1_LGD, V8_Y1_ADV = LGD_DEP, ADV_DIV               # year-1 cluster: fixed LGD 25%, advance dividend 50%
V8_CERT_ADV = 0.80                                    # scenario: certificate financing at an 80% advance rate (no evidenced market)
V8_REINST_FEE_SET = [5 * BP, 10 * BP, 20 * BP, 40 * BP]   # commitment fee on the reinstatement commitment (sweep)
V8_REINST_FEE = 20 * BP                               # mid case (same as the facility-fee mid; no verified market price)
V8_REINST_LOCK = D_YEARS                              # years the replenishment money doubles up with the locked certificates
V8_XOL_RHO = [0.20, 0.30]
V8_BD = 5                                             # exact check: advance dividend after 5 business days
V8_BD_YEAR = 252


def cpx(x, nd=3):
    """Percent with nd decimals; tail values below that resolution in the fp() style."""
    if x <= 0:
        return "0"
    return f"{x * 100:.{nd}f}%" if x * 100 >= 10 ** -nd else fp(x)


class _trim_cache:
    """Drop pool() cache entries created inside the block (memory only; results are unchanged)."""
    def __enter__(self):
        self.keys = set(_POOL_CACHE)
        return self

    def __exit__(self, *exc):
        for k_ in list(_POOL_CACHE):
            if k_ not in self.keys:
                del _POOL_CACHE[k_]


def cond_short(P, cap, w=None):
    """P(par shortfall at T+0 | a given reference bank fails); each failure needs w of notional."""
    w = P["W"] if w is None else w
    return ref_cond(P, lambda n, PP: (n * w > cap + EPS).astype(float))


def cond_unpaid(P, cap, w=None):
    """E[unpaid share of par | own bank fails], pro rata across the failed names."""
    w = P["W"] if w is None else w
    return ref_cond(P, lambda n, PP: np.clip(1.0 - cap / (n * w), 0.0, None))


def cond_loss(P, cap, w=None):
    """E[unpaid share x LGD | own bank fails]: the unpaid depositor keeps the deposit claim and bears LGD on it."""
    w = P["W"] if w is None else w
    return ref_cond(P, lambda n, PP: np.clip(1.0 - cap / (n * w), 0.0, None) * PP["lgd"][:, None])


def uncond_short(P, cap, w=None):
    w = P["W"] if w is None else w
    return Pr(P, P["n"] * w > cap + EPS)


def k_needed(P, std, kmax=None):
    """Smallest number of simultaneous failures covered so that P(shortfall | own bank fails) <= std."""
    kmax = P["pmf"].shape[1] - 1 if kmax is None else kmax
    for k_ in range(kmax + 1):
        if ref_cond(P, lambda n, PP, k_=k_: (n > k_ + 1e-9).astype(float)) <= std:
            return k_
    return None


# --- 35. risk-free rate update: v7 (r 3.9%) versus v8 (r 4.3%) ---------------------------------------
def headline_at(r):
    sn = components(r=r, k=FUND_K, f=FUND_F)
    cap_r = CCF * RW * CET1_RATIO * (HURDLE - r)
    bq = components(r=r, k=bank_k(), f=BANK_F)["c_star"]
    bp_ = components(mu=1.0, r=r, k=bank_k(), f=BANK_F)["c_star"] + cap_r
    fac_r = lambda ccf, rw: BANK_FAC_LCR + ccf * rw * CET1_RATIO * (HURDLE - r)
    fees = [fac_r(V5_FAC_CCF, V5_FAC_RW), fac_r(0.20, V5_FAC_RW), fac_r(0.50, V5_FAC_RW), fac_r(V5_FAC_CCF, V5_FAC_RW_ALT)]
    hyb = pool_price(**V8_HYB, r=r)["c_star"]
    rf = pool_price(**V8_REF, r=r)["c_star"]
    fns = {
        "Self-insured (credit + access)": lambda lp: components(lambda_p=lp, r=r, k=0.0, f=0.0)["c_star"],
        "Single-name funded vehicle": lambda lp: components(lambda_p=lp, r=r, k=FUND_K, f=FUND_F)["c_star"],
        "Pooled all-funded reference (theta 20%, F 0)": lambda lp: pool_price(**{**V8_REF, "pd": lp}, r=r)["c_star"],
        "Pooled 10/10 hybrid, 20 bps fee": lambda lp: pool_price(**{**V8_HYB, "pd": lp}, r=r)["c_star"],
        "Bank SBLC": lambda lp: max(components(lambda_p=lp, r=r, k=bank_k(), f=BANK_F)["c_star"],
                                    components(lambda_p=lp, mu=1.0, r=r, k=bank_k(), f=BANK_F)["c_star"] + cap_r),
    }
    with _trim_cache():
        be_ = {k_: {d_: bisect_lp(fn, d_) for d_ in V5_DELTA_SET} for k_, fn in fns.items()}
    return dict(sn=sn["c_star"], access=sn["access"], cap=cap_r, bq=bq, bp=bp_, ball=max(bq, bp_), fee_lo=min(fees),
                fee_hi=max(fees), hyb=hyb, ref=rf, be=be_)


v8_rcmp = {r_: headline_at(r_) for r_ in (R_FREE_V7, R_FREE)}


# --- 36. reference design, side by side with the hybrid -------------------------------------------------
ref8 = pool_price(**V8_REF)
hyb8 = mid
REF8 = ref8["c_star"]
ref8_rho_corr = {rho: pool_price(**{**V8_REF, "rho": rho, "mode": "corr"})["c_star"] for rho in V5_RHO_SET}
hyb8_rho_corr = {rho: mid_sens[(rho, LAMBDA_P, "corr")] for rho in V5_RHO_SET}
ref8_rho_fixed = {rho: pool_price(**{**V8_REF, "rho": rho})["c_star"] for rho in V5_RHO_SET}
ref8_pd50 = {md: pool_price(**{**V8_REF, "pd": 0.005, "mode": md})["c_star"] for md in ("fixed", "corr")}
hyb8_pd50 = {md: mid_sens[(V5_RHO_MID, 0.005, md)] for md in ("fixed", "corr")}
single_pd50 = components(lambda_p=0.005, k=FUND_K, f=FUND_F)["c_star"]
# break-even lambda_P rows (v8 basis): reuse Section 26 rows and add the reference
be8 = dict(v8_rcmp[R_FREE]["be"])
cost8_base = {"Self-insured (credit + access)": self_ins, "Single-name funded vehicle": SINGLE,
              "Pooled all-funded reference (theta 20%, F 0)": REF8, "Pooled 10/10 hybrid, 20 bps fee": hyb8["c_star"],
              "Bank SBLC": bank["all_in"]}
# stress scenarios, no facility
stress8 = []
for n_ in V5_STRESS_N:
    for lg in V5_STRESS_LGD:
        for a_ in V5_STRESS_ADV:
            th, w_ = V8_REF["theta"], 1.0 / V5_N
            t0 = n_ * w_
            stress8.append(dict(n=n_, lgd=lg, a=a_, t0=t0, buf=min(th, t0), short=max(0.0, t0 - th), term=t0 * (1 - a_),
                                loss=t0 * lg, buf_left=th - t0 * lg, cap_next=max(0.0, th - t0 * (1 - a_))))
# tranches 0-1, 1-3, 3-20 (+ above 20%)
tranche8 = {}
for rho in V5_RHO_SET:
    for mode in ("fixed", "corr"):
        Pp, Qq = pool(LAMBDA_P, rho, mode), pool(MU * LAMBDA_P, rho, mode)
        lp_, pp_ = np.broadcast_to(credit_loss(Pp), Pp["joint"].shape).ravel(), Pp["joint"].ravel()
        lq_, pq_ = np.broadcast_to(credit_loss(Qq), Qq["joint"].shape).ravel(), Qq["joint"].ravel()
        trs = [("Equity", 0.0, 0.01), ("Mezzanine", 0.01, 0.03), ("Senior, funded", 0.03, V8_REF["theta"]),
               ("Above the buffer (unpaid depositors)", V8_REF["theta"], 1.0)]
        tranche8[(rho, mode)] = list(zip(trs, tranche_stats(lp_, pp_, trs), tranche_stats(lq_, pq_, trs)))
tranche8_check = {k_: sum((tr[2] - tr[1]) * q["el"] for tr, _, q in v) for k_, v in tranche8.items()}
inv8 = []
for tr, sp, sq in tranche8[(V5_RHO_MID, "fixed")][:3]:
    _, A, Dt = tr
    tl = np.clip(_li - A, 0, Dt - A) / (Dt - A)
    inv8.append(dict(name=f"Pooled {tr[0].split(',')[0].lower()} {pc(A, 0)} to {pc(Dt, 0)}", spread=sq["el"],
                     el=sp["el"], p_any=sp["p_hit"], var=quantile(tl, _pi, V7_TAIL_Q), es=tail_es(tl, _pi)))
inv8.append(dict(v7_inv[-1]))
for row in inv8:
    row["excess"] = row["spread"] - row["el"]
    row["r_var"] = row["excess"] / row["var"] if row["var"] > 0 else None
    row["r_es"] = row["excess"] / row["es"] if row["es"] > 0 else None
# frictions scenarios
fric8 = {fr: dict(ref=pool_price(**{**V8_REF, "f": fr})["c_star"], hyb=v7_grid[(fr, 0.10)], sn=v7_single[fr])
         for fr in V7_FRIC_SET}
fric8_needed = {t_: t_ - pool_price(**{**V8_REF, "f": 0.0})["c_star"] for t_ in V7_MARKERS}
# bank willingness to pay, reference design
wtp8_bench = [(f"All-funded reference, f {b1(fr)}", fric8[fr]["ref"]) for fr in V7_FRIC_SET] + \
             [("Pooled 10/10 hybrid, f 15", v7_grid[(15 * BP, 0.10)]), ("Single-name vehicle, f 15", v7_single[15 * BP])]
wtp8_dp = {(V, n_): V7_SPLIT * c / (V * V7_ANNUITY) for V in V7_REL_V for n_, c in wtp8_bench}
# challenge register sensitivities, reference design
_cpr = lambda **kw: pool_price(**{**V8_REF, **kw})["c_star"]
_pfr = lambda **kw: _pf(**{"th": V8_REF["theta"], "F": 0.0, **kw})
CRR_P0 = _pfr()
with _trim_cache():
    crr = dict(
        pd=(_cpr(pd=0.005), _pfr(pd=0.005)),
        rho=(_cpr(rho=0.10), _cpr(rho=0.30), ref8_rho_corr[0.10], ref8_rho_corr[0.30], _pfr(rho=0.10), _pfr(rho=0.20)),
        t=(_cpr(copula="t"), _pfr(mode="fixed", copula="t")),
        lgd=(ref8_rho_corr[V5_RHO_MID], _cpr(mode=0.40),
             Pr(pool(LAMBDA_P, V5_RHO_FAIL, "fixed"), credit_loss(pool(LAMBDA_P, V5_RHO_FAIL, "fixed")) > V8_CAP + EPS),
             Pr(P_fail_base, credit_loss(P_fail_base) > V8_CAP + EPS),
             Pr(pool(LAMBDA_P, V5_RHO_FAIL, 0.40), credit_loss(pool(LAMBDA_P, V5_RHO_FAIL, 0.40)) > V8_CAP + EPS)),
        adv=(_cpr(a=0.30), _cpr(a=0.60), _cpr(a=0.0),
             {a_: p_fail(P_, V8_CAP, 0.0, timing="sequential") for a_, P_ in _Pa.items() if a_ > 0}),
        lag=(_cpr(lag=V5_ADV_LAG_ALT),),
        D=(_cpr(d=1), _cpr(d=3)),
        conc=(_cpr(n_names=25), _pfr(n_names=25)),
        timing=(_pfr(timing="sequential"),),
        cap=(_cpr(theta=0.12), _cpr(theta=0.30), _pfr(th=0.12), _pfr(th=0.30)),
        lock=(_cpr(s_lock=V5_S_LOCK_RANGE[0]), _cpr(s_lock=V5_S_LOCK_RANGE[1]), _cpr(s_lock=45 * BP)),
        fric=(_cpr(f=10 * BP), _cpr(f=20 * BP)),
        mu=(_cpr(mu=2), _cpr(mu=5)),
        replen=(_pfr(th=V8_CAP - 3 * (1.0 / V5_N) * (1 - ADV_DIV)), _pfr(th=V8_CAP - 6 * (1.0 / V5_N) * (1 - ADV_DIV))),
        noadv=(_pfr(th=V8_CAP - 3 * (1.0 / V5_N)),),
    )
# failure probability by capacity: only theta + F matters, so the reference equals the hybrid at the same capacity
cap_check = max(abs(p_fail(P_, c, 0.0) - p_fail(P_, c / 2, c / 2))
                for P_ in (P_fail_base, pool(LAMBDA_P, V5_RHO_FAIL, "fixed", copula="t")) for c in cap_list)
# weekend: conventional bills not monetizable before markets reopen
P_fail_t = pool(LAMBDA_P, V5_RHO_FAIL, "fixed", copula="t")
wk8 = dict(ref_none=Pr(P_fail_base, P_fail_base["n"] >= 1), ref_none_t=Pr(P_fail_t, P_fail_t["n"] >= 1),
           hyb_F=v7_conv["fail_F10"], hyb_F_t=p_fail(P_fail_t, 0.0, V5_MID["F"]),
           hyb_F_cond=cond_short(P_fail_base, V5_MID["F"]), mobile=CR_P0, mobile_t=cr["t"][1])

# --- 37. buffer-versus-facility rule -----------------------------------------------------------------
rule_drawn = {}
for th, F_ in V8_SPLITS:
    pz = pool_price(theta=th, F=F_, fee=0.0)
    rule_drawn[(th, F_)] = dict(drawn=pz["drawn"], per_F=(pz["drawn"] / F_ if F_ > 0 else None),
                                draw0=pz["draw0"], termout=pz["termout"])
rule_price = {(sl, fe, th, F_): pool_price(theta=th, F=F_, fee=fe, s_lock=sl)["c_star"]
              for sl in V8_SLOCK_SET for fe in V5_FEE_SET for th, F_ in V8_SPLITS}
rule_marg = {(sl, fe, th, F_): (rule_price[(sl, fe, th, F_)] - rule_price[(sl, fe, 0.20, 0.0)]) / F_
             for sl in V8_SLOCK_SET for fe in V5_FEE_SET for th, F_ in V8_SPLITS if F_ > 0}
rule_full = []
for th, F_ in V8_SPLITS:
    for lg in V8_RULE_LGD:
        for a_ in V8_RULE_ADV:
            cap = th + F_
            rule_full.append(dict(th=th, F=F_, lgd=lg, a=a_, need=(1 - a_) * cap, ok=th >= (1 - a_) * cap - EPS,
                                  termout=max(0.0, (1 - a_) * cap - th), loss=cap * lg, fac_loss=max(0.0, cap * lg - th)))

# --- 38. reliability given the depositor's own bank fails -------------------------------------------
rel8 = {}
for cop, _ in V8_COPULAS:
    for pd in V5_PD_SET:
        for rho in V5_RHO_SET:
            with _trim_cache():
                P_ = pool(pd, rho, "corr", copula=cop)
                for c in V8_CAPS:
                    sf, up, ls = cond_short(P_, c), cond_unpaid(P_, c), cond_loss(P_, c)
                    rel8[(cop, pd, rho, c)] = dict(sf=sf, sev=(up / sf if sf > 0 else 0.0), unpaid=up, loss=ls,
                                                   uncond=uncond_short(P_, c))
# curves for fig-10 and the iso-reliability table (rho 0.30, PD 0.25%): k = 0..50 failures covered
rel8_curve = {}
for cop, _ in V8_COPULAS:
    with _trim_cache():
        P_ = pool(LAMBDA_P, V5_RHO_FAIL, "corr", copula=cop)
        rel8_curve[cop] = [ref_cond(P_, lambda n, PP, k_=k_: (n > k_ + 1e-9).astype(float)) for k_ in range(V5_N + 1)]


def _k_from_curve(curve, std):
    return next((k_ for k_, v in enumerate(curve) if v <= std), None)


iso8 = {}
for cop, _ in V8_COPULAS:
    for std in V8_STANDARDS:
        k_ = _k_from_curve(rel8_curve[cop], std)
        cap = k_ / V5_N
        iso8[(cop, std)] = dict(k=k_, cap=cap, sf=rel8_curve[cop][k_],
                                ref=pool_price(**{**V8_REF, "theta": cap})["c_star"],
                                hyb=pool_price(**{**V8_HYB, "theta": cap / 2, "F": cap / 2})["c_star"])
nsweep8 = {}
for N_ in V8_N_SET:
    row = {}
    for cop, _ in V8_COPULAS:
        with _trim_cache():
            P_ = pool(LAMBDA_P, V5_RHO_FAIL, "corr", copula=cop, n_names=N_)
            k_ = k_needed(P_, V8_N_STD[cop])
            row[cop] = dict(k=k_, cap=k_ / N_, sf=ref_cond(P_, lambda n, PP, k_=k_: (n > k_ + 1e-9).astype(float)),
                            price=pool_price(**{**V8_REF, "theta": k_ / N_, "n_names": N_})["c_star"])
    nsweep8[N_] = row

# --- 39. Year 2 after a year-1 cluster, and reinstatement ---------------------------------------------
W8 = 1.0 / V5_N                                       # each surviving bank is still 2% of the original notional
y2_cap = {}
for K1 in V8_Y1_N:
    locked = K1 * W8 * (V8_Y1_LGD + (1 - V8_Y1_ADV - V8_Y1_LGD))           # credit loss + certificate lockup
    cert = K1 * W8 * (1 - V8_Y1_ADV - V8_Y1_LGD)
    y2_cap[(K1, "A")] = V8_CAP - locked
    y2_cap[(K1, "B")] = V8_CAP - K1 * W8 * V8_Y1_LGD - cert * (1 - V8_CERT_ADV)
    y2_cap[(K1, "C")] = V8_CAP
Y2_REGIMES = [("A", "Unreplenished"), ("B", f"Certificate financing at {V8_CERT_ADV:.0%} advance (scenario)"),
              ("C", "Contractual reinstatement to full capacity")]
y2 = {}
for K1 in V8_Y1_N:
    for cop, _ in V8_COPULAS:
        for pd in V5_PD_SET:
            with _trim_cache():
                P_ = pool(pd, V5_RHO_FAIL, "corr", copula=cop, n_names=V5_N - K1)
                for reg, _ in Y2_REGIMES:
                    c = y2_cap[(K1, reg)]
                    y2[(K1, cop, pd, reg)] = dict(cond=cond_short(P_, c, W8), uncond=uncond_short(P_, c, W8),
                                                  unpaid=cond_unpaid(P_, c, W8))
y1_ref = {cop: dict(cond=rel8[(cop, LAMBDA_P, V5_RHO_FAIL, V8_CAP)]["sf"], uncond=rel8[(cop, LAMBDA_P, V5_RHO_FAIL, V8_CAP)]["uncond"])
          for cop, _ in V8_COPULAS}
# reinstatement: investors pre-commit at inception to restore the buffer to full capacity at renewal after a loss year
_Qr = pool(MU * LAMBDA_P, V5_RHO_MID, "fixed")
REINST_R = np.minimum(_Qr["n"] * _Qr["W"], V8_CAP) * (1 - ADV_DIV)          # replenishment needed: paid out less advance dividend
REINST_EQ = E(_Qr, REINST_R)                         # Q-expected replenishment amount
REINST_K = V8_CAP * (1 - ADV_DIV)                                             # committed amount = largest replenishment
REINST_P_CALL = Pr(_Qr, _Qr["n"] >= 1)
reinst = {fe: dict(double_lock=REINST_EQ * V5_S_LOCK * V8_REINST_LOCK, commit=fe * REINST_K) for fe in V8_REINST_FEE_SET}
for v in reinst.values():
    v["total"] = v["double_lock"] + v["commit"]
REINST_PREFUND = REINST_K * V5_S_LOCK                                         # alternative: pre-fund the same amount
REINST_PREFUND_CSTAR = pool_price(theta=0.20 + REINST_K, F=0.0)["c_star"]     # v9: all-funded buffer of 20% + K, pre-funded
# excess-of-loss layer above 10 failures (pays the par shortfall above capacity), Q measure, fixed LGD 25%
xol8 = {}
for cop, _ in V8_COPULAS:
    for rho in V8_XOL_RHO:
        with _trim_cache():
            Qx = pool(MU * LAMBDA_P, rho, "fixed", copula=cop)
            ex = E(Qx, np.clip(t0_cash(Qx) - V8_CAP, 0, None))
            Px = pool(LAMBDA_P, rho, "fixed", copula=cop)
            xol8[(cop, rho)] = dict(par=ex, loss=ex * LGD_DEP, p_q=Pr(Qx, t0_cash(Qx) > V8_CAP + EPS),
                                    par_p=E(Px, np.clip(t0_cash(Px) - V8_CAP, 0, None)))

# --- 40. three-party clearing: price <= Delta + bank retention value ---------------------------------
tp8 = {(V, dp, d_): d_ + v7_wtp[(V, dp)] - REF8 for V in V7_REL_V for dp in V7_DP_RUN for d_ in V5_DELTA_SET}
tp8_min = {(V, dp): {nm: max(0.0, c - v7_wtp[(V, dp)]) for nm, c in
                     [("ref", REF8), ("hyb", hyb8["c_star"]), ("sn", SINGLE)]} for V in V7_REL_V for dp in V7_DP_RUN}


# --- 41. exact cash-flow check -------------------------------------------------------------------------
def exact_terms(lq=None, lgd=LGD_DEP, a=ADV_DIV, d=D_YEARS, r=None):
    """Constant hazard h = -ln(1 - lambda_Q) (so the one-year default probability is lambda_Q); premium paid
    continuously until default or expiry, discounted at r; at default the provider pays par, receives a after
    5 business days and 1 - a - LGD after D years, both bridges financed at r + s_b with continuous discounting.
    With a running premium the premium and protection legs share the survival discount, so the exact running
    spread is h x (cost per default, valued at the default date)."""
    lq = lambda_q() if lq is None else lq
    r = R_FREE if r is None else r
    y = r + S_B
    t1 = V8_BD / V8_BD_YEAR
    h = -math.log(1.0 - lq)
    return dict(h=h, credit=h * lgd, adv=h * a * (1 - math.exp(-y * t1)),
                cert=h * max(0.0, 1 - a - lgd) * (1 - math.exp(-y * d)),
                credit4=lq * lgd, adv4=0.0, cert4=lq * max(0.0, 1 - a - lgd) * y * d,
                annuity=(1 - math.exp(-(h + r))) / (h + r))


ex8 = exact_terms()
exact8 = {}
for nm, kk in (("Single-name funded vehicle", FUND_K), ("All-funded reference (theta 20%, F 0)", ref8["k"])):
    four = ex8["credit4"] + ex8["adv4"] + ex8["cert4"] + kk + V5_FRIC
    exact = ex8["credit"] + ex8["adv"] + ex8["cert"] + kk + V5_FRIC
    exact8[nm] = dict(k=kk, four=four, exact=exact, diff=exact - four, upfront=exact * ex8["annuity"])
exact8_model = {"Single-name funded vehicle": SINGLE, "All-funded reference (theta 20%, F 0)": REF8}

# --- 44. settlement regimes at the trigger, and the banker's term-premium value (pilot hypothesis) -------
# Each failed bank's covered balance is W = 1/N of pool notional. Three ways the vehicle can settle:
#   gross:  buy the whole claim at par at T+0; draw W per failure; the vehicle collects the advance dividend.
#   net:    the depositor collects the FDIC advance dividend a directly and the vehicle pays par less the dividend
#           actually paid, 1 - a, at day 7 against the receivership certificate; draw W (1 - a(z)) per failure, with
#           a state-dependent in the correlated mode (a = (2/3)(1 - LGD), 40% in the worst states); with no dividend
#           the rule collapses to gross par.
#   junior: the vehicle pays a fixed m of par in cash at day 7 and takes the recoveries above 1 - m (the junior slice
#           of the receivership claim), and pays a carry coupon at r + s_b on the depositor's outstanding certificate
#           until the dividends arrive; draw m W per failure; the vehicle bears LGD up to m, the depositor any excess.
# Reliability is measured as in Sections 38 and 39: conditional on the depositor's own bank failing, rho 0.30,
# PD 0.25%, correlated LGD, simultaneous standard. The price c* uses pool_price at the regime's buffer: the credit
# term is unchanged under net (the vehicle still bears the whole LGD) and under junior while LGD <= m, which holds
# throughout the correlated mapping (15% to 40%); the access term is the same certificate carry in every regime.
V8_JUNIOR_M = 0.40                                   # junior slice bought at day 7; equals the mapping's LGD ceiling
V8_UNB_REGIMES = [("gross", "Gross par at T+0 (reference)"),
                  ("net", "Par less the advance dividend, at day 7"),
                  ("junior", f"Junior {V8_JUNIOR_M:.0%} slice of the claim, at day 7")]
V8_UNB_ADV_SHOW = [ADV_DIV, V5_ADV_SHARE * (1.0 - V5_LGD_BAD)]   # dividends at which "failures covered" is shown


def unb_draw(P, regime):
    """Buffer draw per failed bank, share of pool notional, by common-factor node (column vector)."""
    W = P["W"]
    if regime == "gross":
        return np.full((P["z"].size, 1), W)
    if regime == "net":
        return W * (1.0 - P["adv"][:, None])
    return np.full((P["z"].size, 1), W * V8_JUNIOR_M)


def unb_stats(P, regime, theta):
    """Conditional on own failure: P(shortfall), E[unpaid share of the promise], E[depositor loss, share of par]."""
    d = unb_draw(P, regime)
    borne = (np.minimum(P["lgd"], V8_JUNIOR_M) if regime == "junior" else P["lgd"])[:, None]
    sf = ref_cond(P, lambda n, PP: (n * d > theta + EPS).astype(float))
    unpaid = ref_cond(P, lambda n, PP: np.clip(1.0 - theta / (n * d), 0.0, None))
    loss = ref_cond(P, lambda n, PP: np.clip(1.0 - theta / (n * d), 0.0, None) * borne)
    return dict(sf=sf, unpaid=unpaid, loss=loss)


def unb_theta_star(P, regime, std, hi=1.0, it=40):
    """Smallest buffer with P(shortfall | own failure) <= std, rounded up to 0.1% so the printed buffer meets the standard."""
    f = lambda th: unb_stats(P, regime, th)["sf"]
    if f(hi) > std:
        return None
    lo = 0.0
    for _ in range(it):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > std else (lo, mid)
    return math.ceil(hi * 1e3 - 1e-6) / 1e3


unb8 = {}
unb8_pool = {}
for cop, _ in V8_COPULAS:
    with _trim_cache():
        P_ = pool(LAMBDA_P, V5_RHO_FAIL, "corr", copula=cop)
        unb8_pool[cop] = dict(
            e_adv=ref_cond(P_, lambda n, PP: PP["adv"][:, None] + 0 * n),
            p_adv_lt=ref_cond(P_, lambda n, PP: (PP["adv"][:, None] < ADV_DIV - EPS).astype(float) + 0 * n),
            p_lgd_gt_m=ref_cond(P_, lambda n, PP: (PP["lgd"][:, None] > V8_JUNIOR_M + EPS).astype(float) + 0 * n),
            e_draw_net=ref_cond(P_, lambda n, PP: (1.0 - PP["adv"][:, None]) * PP["W"] + 0 * n),
            sf_net_fixed_a=cond_short(P_, V8_CAP / (1.0 - ADV_DIV)))   # what a fixed 50% dividend would print
        for code, _ in V8_UNB_REGIMES:
            st = unb_stats(P_, code, V8_CAP)
            iso = {}
            for std in V8_STANDARDS:
                th = unb_theta_star(P_, code, std)
                iso[std] = dict(theta=th, c_star=pool_price(**{**V8_REF, "theta": th})["c_star"] if th is not None else None)
            unb8[(cop, code)] = dict(**st, iso=iso)
unb8_c_ref = pool_price(**V8_REF)["c_star"]
unb8_cov = {}                                        # failures covered in full at the reference buffer, by dividend
for code, _ in V8_UNB_REGIMES:
    for a_ in V8_UNB_ADV_SHOW:
        d_ = {"gross": 1.0, "net": 1.0 - a_, "junior": V8_JUNIOR_M}[code] / V5_N
        unb8_cov[(code, a_)] = int(math.floor(V8_CAP / d_ + EPS))

# Banker's term-premium value: a hypothesis for the Section 14 pilot, not a result. If protected balances prove
# stable in an internal liquidity stress test, the bank could move a share phi_rel of the covered balance from
# overnight liquidity into its structural replicating ladder and be credited the term premium s_term through funds
# transfer pricing. s_term of 50 to 80 bps straddles the Kim-Wright term-premium estimates on FRED, 54 bps at 3 years
# and 64 bps at 5 years on 23 October 2026 (THREEFYTP3 0.5353, THREEFYTP5 0.6353), and its top reaches the 1-month to 3-
# and 5-year Treasury slope of 73 to 78 bps on 28 October 2026 (DGS1MO 4.07, DGS3 4.80, DGS5 4.85); the
# expected excess return of the ladder over rolling cash is the term premium, which is smaller than the slope when
# short rates are expected to rise. Asset or credit spread is excluded: it belongs to the asset and
# its capital. The standardized LCR gives no credit for private protection, so the release
# is zero for an LCR-bound bank; the hypothesis applies where an internal stress test binds and recognizes it.
V8_PHI_REL = [0.05, 0.15, 0.25]                      # share of the covered balance released (hypothesis sweep)
V8_S_TERM = [50 * BP, 65 * BP, 80 * BP]              # term premium credited through FTP, bps a year (hypothesis sweep)
V8_BANK_CELLS = [(100 * BP, 0.01), (150 * BP, 0.05)]  # retention-value cells from Section 41 shown beside it
bank_term8 = {(ph, st): ph * st for ph in V8_PHI_REL for st in V8_S_TERM}
bank_tot8 = {(ph, st, V, dp): bank_term8[(ph, st)] + v7_wtp[(V, dp)]
             for ph in V8_PHI_REL for st in V8_S_TERM for V, dp in V8_BANK_CELLS}
bank_min_delta8 = {k_: max(0.0, REF8 - v) for k_, v in bank_tot8.items()}


# --- results ------------------------------------------------------------------------------------------
def write_results_v8(meta):
    write_results_v7()
    txt = RESULTS_MD.read_text(encoding="utf-8").rstrip("\n")
    first, rest = txt.split("\n", 1)
    L = ["# Cash That Never Sleeps, Chapter 3: the clearing cost of an uninsured deposit (clearing_cost.py results)\n",
         f"Run environment: Python {meta['python']}, numpy {meta['numpy']}, matplotlib {meta['matplotlib']}; "
         f"run time {meta['runtime']} on a single process (exact seconds are printed to the console). Command: "
         "`python3 -I model/clearing_cost.py` from the repository root. "
         f"Seeds: {MC_SEED} (Part I Monte Carlo), {V5_MC_SEED} and {V5_MC_SEED + 1} (Part II Monte Carlo check). Quadrature: "
         f"{Z_GRID} points over the common factor on [-8, 8] (Gaussian); 401 x 240 nodes in (z, W) for the Student-t(5) copula. "
         f"Risk-free rate r = {pc(R_FREE, 1)} (3-month Treasury bill, FRED DGS3MO 4.28% on 15 October 2026; verify before "
         "relying on it); model v7 used 3.9%, and Section 35 compares the headline values. Every parameter not tied to a "
         "cited public source is an author assumption, illustrative and not calibrated to any bank.\n"]
    L.append(rest)
    L.append("")
    L.append("---\n")
    L.append("# Part IV. Reference design, reliability given the depositor's own bank fails, Year 2 and clearing\n")
    L.append(f"Conventions. Reference design: all-funded, buffer theta {pc(V8_REF['theta'], 0)} in T-bills, no committed "
             f"facility, capacity {pc(V8_CAP, 0)} (par on {int(round(V8_CAP * V5_N))} simultaneous failures among {V5_N} banks at "
             f"{pc(1 / V5_N, 0)}). The 10/10 hybrid (theta 10%, F 10% at a 20 bps fee) is a variant. Prices: Q measure, rho "
             f"{V5_RHO_MID:.2f}, fixed LGD 25%, Gaussian copula, lock-up premium s_lock {bps(V5_S_LOCK)} bps, frictions "
             f"{bps(V5_FRIC)} bps, unless stated. Failure statistics: P measure, PD 0.25% per bank, rho {V5_RHO_FAIL:.2f}, "
             "state-dependent LGD, simultaneous standard, unless stated. Probabilities are exact (quadrature).\n")

    # 35
    a7, a8 = v8_rcmp[R_FREE_V7], v8_rcmp[R_FREE]
    L.append("## 35. Risk-free rate update: v7 (r 3.9%) versus v8 (r 4.3%)\n")
    L.append("Same code and every other parameter unchanged; only r moves. r enters the access term (r + s_b), the bank's capital "
             "cost (hurdle - r), the facility's drawn cost and the relationship discount rate (r + 3%). The v7 column is "
             "recomputed here at r = 3.9% and reproduces the v7 results file.\n")
    rows = [["Single-name funded vehicle c*", b1(a7["sn"]), b1(a8["sn"])],
            ["Access term (single-name)", f"{a7['access'] / BP:.2f}", f"{a8['access'] / BP:.2f}"],
            ["Bank SBLC: capital cost", f"{a7['cap'] / BP:.2f}", f"{a8['cap'] / BP:.2f}"],
            ["Bank SBLC: Q price", b1(a7["bq"]), b1(a8["bq"])],
            ["Bank SBLC: full P price", b1(a7["bp"]), b1(a8["bp"])],
            ["Bank SBLC: all-in c* = max(Q, P)", b1(a7["ball"]), b1(a8["ball"])],
            ["Bank facility cost floor on undrawn F (low to high)", f"{b1(a7['fee_lo'])} to {b1(a7['fee_hi'])}",
             f"{b1(a8['fee_lo'])} to {b1(a8['fee_hi'])}"],
            ["Pooled 10/10 hybrid (20 bps fee) c*", b1(a7["hyb"]), b1(a8["hyb"])],
            ["Pooled all-funded reference (theta 20%, F 0) c*", b1(a7["ref"]), b1(a8["ref"])]]
    L.append(table(["Headline (bps a year)", "v7, r 3.9%", "v8, r 4.3%"], rows))
    L.append("\nBreak-even lambda_P at which each cost equals the yield advantage Delta (bps); 'none' = cost exceeds Delta at any PD:\n")
    rows = []
    for k_ in a8["be"]:
        for lab, a_ in (("v7", a7), ("v8", a8)):
            rows.append([f"{k_} ({lab})"] + [("none" if a_["be"][k_][d_] is None else pc(a_["be"][k_][d_], 2)) for d_ in V5_DELTA_SET])
    L.append(table(["Cost"] + [f"Delta {d_ / BP:.0f}" for d_ in V5_DELTA_SET], rows))
    L.append("")

    # 36
    L.append("## 36. The reference design: all-funded 20% buffer, side by side with the 10/10 hybrid\n")
    L.append("Price decomposition (bps a year):\n")
    L.append(table(["Component", "All-funded reference (theta 20%, F 0)", "10/10 hybrid (theta 10%, F 10% at 20 bps)",
                    "Single-name vehicle"], [
        ["Credit (Q)", b1(ref8["credit"]), b1(hyb8["credit"]), b1(ref["credit"])],
        ["Access (Q)", b1(ref8["access"]), b1(hyb8["access"]), b1(ref["access"])],
        ["Buffer lock theta x s_lock", b1(ref8["lock"]), b1(hyb8["lock"]), b1(FUND_K) + " (100% locked)"],
        ["Facility commitment F x fee_F", b1(ref8["commit"]), b1(hyb8["commit"]), "0"],
        ["Expected drawn cost", f"{ref8['drawn'] / BP:.3f}", f"{hyb8['drawn'] / BP:.3f}", "0"],
        ["Capacity k", b1(ref8["k"]), b1(hyb8["k"]), b1(FUND_K)],
        ["Frictions f", b1(ref8["f"]), b1(hyb8["f"]), b1(FUND_F)],
        ["**c***", "**" + b1(REF8) + "**", "**" + b1(hyb8["c_star"]) + "**", "**" + b1(SINGLE) + "**"],
    ]))
    L.append("\nPrice by correlation, LGD mode and default probability (bps):\n")
    L.append(table(["Case", "All-funded reference", "10/10 hybrid", "Single-name"], [
        [f"rho {r:.2f}, fixed LGD 25%", b1(ref8_rho_fixed[r]), b1(mid_sens[(r, LAMBDA_P, 'fixed')]), b1(SINGLE)] for r in V5_RHO_SET] + [
        [f"rho {r:.2f}, state-dependent LGD", b1(ref8_rho_corr[r]), b1(hyb8_rho_corr[r]), "n/a"] for r in V5_RHO_SET] + [
        ["PD 0.50%, rho 0.20, fixed LGD", b1(ref8_pd50["fixed"]), b1(hyb8_pd50["fixed"]), b1(single_pd50)],
        ["PD 0.50%, rho 0.20, state-dependent LGD", b1(ref8_pd50["corr"]), b1(hyb8_pd50["corr"]), "n/a"]]))
    L.append("\nBreak-even lambda_P at which the cost equals Delta (bps), v8 basis; 'none' = cost exceeds Delta at any PD:\n")
    L.append(table(["Cost (c* at PD 0.25%)"] + [f"Delta {d_ / BP:.0f}" for d_ in V5_DELTA_SET],
                   [[f"{k_} ({b1(cost8_base[k_])})"] + [("none" if be8[k_][d_] is None else pc(be8[k_][d_], 2)) for d_ in V5_DELTA_SET]
                    for k_ in be8]))
    L.append(f"\nWho pays at the reference price c = {b1(REF8)} bps (relative to the outside-option yield y; Delta values are sweep points):\n")
    rows = []
    for d_ in WHO_DELTA:
        for label, posted, prem_dep, prem_bank in [
                ("Depositor buys protection", d_, REF8, 0.0), ("Bank buys it, passes it through in the rate or ECR", d_ - REF8, 0.0, REF8),
                ("Bank buys it and absorbs it (rate unchanged)", d_, 0.0, REF8), ("Nobody buys it", d_, 0.0, 0.0)]:
            sg = lambda x: f"y {('+' if x >= 0 else '-')} {abs(x) / BP:.1f}"
            rows.append([f"{d_ / BP:.0f}", label, sg(posted), sg(posted - prem_dep), sg(posted + prem_bank),
                         "par" if label != "Nobody buys it" else "par less LGD on failure"])
    L.append(table(["Delta", "Who pays", "Posted rate", "Depositor net yield", "Bank all-in cost", "Depositor gets at failure"], rows))
    L.append(f"\nDeterministic stress, reference design (theta {pc(V8_REF['theta'], 0)}, no facility), % of covered notional, all failures "
             "in one advance-dividend window. With no facility there is nothing to draw or term out: the buffer pays par and "
             "carries the bridge, because the term need after the advance dividend is never more than the cash paid at T+0.\n")
    L.append(table(["Failures", "LGD", "a", "Cash at trigger", "Buffer used", "Shortfall at T+0", "Term need after a",
                    "Credit loss", "Buffer left at the end", "Buffer free for next year until recoveries"],
                   [[s_["n"], pc(s_["lgd"], 0), pc(s_["a"], 0), pc(s_["t0"], 0), pc(s_["buf"], 0), pc(s_["short"], 0),
                     pc(s_["term"], 1), pc(s_["loss"], 1), pc(s_["buf_left"], 1), pc(s_["cap_next"], 1)] for s_ in stress8]))
    L.append("\nTranching the reference design's credit loss (0 to 1, 1 to 3, 3 to 20% of notional). Each cell: P-EL / Q spread "
             "(multiple) / P(any loss), % of tranche per year. Losses above 20% of notional need 40 or more failures at LGD 25%; "
             "in the all-funded design they fall on unpaid depositors, not on a facility. As in Section 24, credit loss counts "
             "every failure in the year, including names the vehicle could not pay in full.\n")
    for mode in ("fixed", "corr"):
        L.append(f"LGD {('fixed 25%' if mode == 'fixed' else 'state-dependent 15% to 40%')}:\n")
        rows = []
        for i, (tr, _, _) in enumerate(tranche8[(V5_RHO_SET[0], mode)]):
            cells = []
            for r in V5_RHO_SET:
                _, sp, sq = tranche8[(r, mode)][i]
                mult = f"{sq['el'] / sp['el']:.1f}x" if sp["el"] > 1e-9 else "n/m"
                cells.append(f"{pel(sp['el'])} / {pel(sq['el'])} ({mult}) / {fp(sp['p_hit'])}")
            rows.append([f"{tr[0]} {pc(tr[1], 0)} to {pc(tr[2], 0)}"] + cells)
        L.append(table(["Tranche"] + [f"rho {r:.2f}" for r in V5_RHO_SET], rows))
        L.append("")
    L.append("n/m = not meaningful (expected loss below 1e-7% of the tranche). Check: thickness-weighted spreads sum to the "
             "credit term (bps): " + "; ".join(f"rho {k_[0]:.2f} {k_[1]} {v / BP:.2f}" for k_, v in tranche8_check.items()) + ".\n")
    rr = lambda x: "n/a (VaR 0)" if x is None else f"{x * 100:.2f}%"
    L.append(f"Investor view, reference design tranches (rho {V5_RHO_MID:.2f}, fixed LGD; as Section 32): % of tranche per year; "
             f"tail at {V7_TAIL_Q:.1%}.\n")
    L.append(table(["Tranche", "Spread over T-bills", "Expected loss", "Excess spread", "P(any loss)", f"{V7_TAIL_Q:.1%} VaR",
                    f"{V7_TAIL_Q:.1%} ES", "Excess / VaR", "Excess / ES"],
                   [[r_["name"], pel(r_["spread"]), pel(r_["el"]), pel(r_["excess"]), fp(r_["p_any"]), pc(r_["var"], 1),
                     pc(r_["es"], 1), rr(r_["r_var"]), rr(r_["r_es"])] for r_ in inv8]))
    L.append(f"\nThe equity and mezzanine are the same as in the hybrid (same attachment points, same loss distribution); only "
             f"the senior is thicker (3% to 20%). The lock-up premium ({b1(ref8['lock'])} bps of notional) is not allocated to the "
             f"tranches; paid pro rata on the buffer it adds {V5_S_LOCK / BP:.0f} bps a year to each tranche.\n")
    L.append("Frictions scenarios (bps; scenarios, not estimates):\n")
    L.append(table(["Frictions f", "All-funded reference c*", "10/10 hybrid c*", "Single-name c*"],
                   [[b1(fr), b1(v["ref"]), b1(v["hyb"]), b1(v["sn"])] for fr, v in fric8.items()]))
    L.append("\nFrictions at which the reference reaches the markers: "
             + "; ".join(f"{t_ / BP:.0f} bps needs f {b1(v)}" if v > 0 else f"{t_ / BP:.0f} bps: none" for t_, v in fric8_needed.items()) + ".\n")
    L.append(f"Bank willingness to pay, bank-sponsored variant (as Section 33: WTP = dP_run x V x {V7_ANNUITY:.3f}; the bank pays "
             f"{pc(V7_SPLIT, 0)} of c*). Break-even dP_run:\n")
    L.append(table(["V (bps a year)"] + [f"{n_} ({b1(c)})" for n_, c in wtp8_bench],
                   [[f"{V / BP:.0f}"] + [pc(wtp8_dp[(V, n_)], 1) for n_, _ in wtp8_bench] for V in V7_REL_V]))
    L.append("")
    L.append(f"Challenge register, reference design. Price base {b1(REF8)} bps; failure base P(cannot pay par) {fp(CRR_P0)} "
             f"({one_in(CRR_P0)}) at capacity 20%, rho 0.30, state-dependent LGD, Gaussian, simultaneous standard, PD 0.25%.\n")
    reg8 = [
        ["Per-bank PD lambda_P", "0.25% (0.50%)", f"{b1(REF8)} -> {b1(crr['pd'][0])}", f"{fp(CRR_P0)} -> {fp(crr['pd'][1])}"],
        ["Asset correlation rho", "0.20 price, 0.30 failure (0.10 to 0.30)",
         f"{b1(crr['rho'][0])} to {b1(crr['rho'][1])} (fixed LGD); {b1(crr['rho'][2])} to {b1(crr['rho'][3])} (state-dependent)",
         f"{fp(crr['rho'][4])} (0.10), {fp(crr['rho'][5])} (0.20), {fp(CRR_P0)} (0.30)"],
        ["Copula family", "Gaussian (Student-t, 5 df)", f"{b1(crr['t'][0])} (t)", f"{fp(CRR_P0)} -> {fp(crr['t'][1])} (t)"],
        ["LGD_dep", "25% fixed; state-dependent 15% to 40%; 40% stress", f"{b1(crr['lgd'][0])} (state-dependent), {b1(crr['lgd'][1])} (40%)",
         f"none at T+0; P(loss above buffer) {fp(crr['lgd'][2])} fixed, {fp(crr['lgd'][3])} state-dependent, {fp(crr['lgd'][4])} at 40%"],
        ["Advance dividend a", "50% (30% to 60%; 0)", f"{b1(crr['adv'][0])} (30%), {b1(crr['adv'][1])} (60%), {b1(crr['adv'][2])} (0)",
         f"T+0 unchanged; no facility to term out; sequential P(fail) {fp(crr['adv'][3][0.30])} at 30%, {fp(crr['adv'][3][0.60])} at 60%"],
        ["T+0 to advance dividend", f"{V5_ADV_LAG_DAYS} days ({V5_ADV_LAG_ALT})", f"{b1(crr['lag'][0])} (no facility, no drawn cost)", "none"],
        ["Years to final dividends D", "2 (1 to 3)", f"{b1(crr['D'][0])} to {b1(crr['D'][1])}", "none in year 1; Year 2 in Section 40"],
        ["Concentration cap per bank", "2% x 50 banks (4% x 25)", f"{b1(crr['conc'][0])}", f"{fp(CRR_P0)} -> {fp(crr['conc'][1])} (25 banks)"],
        ["Timing standard", "simultaneous (sequential)", "none", f"{fp(CRR_P0)} -> {fp(crr['timing'][0])} (sequential)"],
        ["Capacity (all-funded)", "20% (12% to 30%)", f"{b1(crr['cap'][0])} (12%) to {b1(crr['cap'][1])} (30%)",
         f"{fp(crr['cap'][2])} at 12%; {fp(crr['cap'][3])} at 30%"],
        ["Facility fee, provider, conditionality", "no facility", "none", "none: no facility-provider, MAC or term-out failure modes"],
        ["Buffer lock premium s_lock", "10 bps (5 to 15; 45 as a sweep point)",
         f"{b1(crr['lock'][0])} to {b1(crr['lock'][1])}; {b1(crr['lock'][2])} at 45", "none"],
        ["Frictions f", "15 bps (10 to 20)", f"{b1(crr['fric'][0])} to {b1(crr['fric'][1])}", "none"],
        ["Risk-premium multiplier mu", "3 (2 to 5)", f"{b1(crr['mu'][0])} to {b1(crr['mu'][1])}", "none (P measure)"],
        ["Replenishment after a loss year", "unreplenished (Section 40 for regimes)", "Section 40 (reinstatement cost)",
         f"next year at capacity reduced by credit loss and certificates: {fp(crr['replen'][0])} after 3 failures, {fp(crr['replen'][1])} after 6"],
        ["Advance dividend not collected", "vehicle collects it as assignee", "none",
         f"par still paid at T+0 from the buffer; after 3 failures next-year capacity 14%: {fp(crr['noadv'][0])}"],
    ]
    L.append(table(["Assumption", "Value (range)", "c* sensitivity (bps)", "P(cannot pay par) sensitivity"], reg8))
    L.append(f"\nFailure probability by capacity (Section 20) is unchanged by the split: only theta + F matters for the T+0 event, "
             f"so the reference design at 20% fails exactly as the 10/10 hybrid does when its facility performs ({fp(CRR_P0)} "
             f"Gaussian, {fp(crr['t'][1])} t(5); largest difference across the Section 20 capacities, both copulas: {cap_check:.1e}).\n")
    L.append("Weekend and after-hours triggers with conventional bills. Under the term sheet the vehicle has a stated number of "
             "business days to pay, and T-bills sell on any of them, so the buffer is cash. A vehicle that promised par before "
             "markets reopen after a Friday-evening trigger could not count conventional bills: with no facility its "
             "capacity before reopening is zero, so it could pay nothing on such a trigger, and that would happen in every year "
             f"with a failure: P(1+ failures) = {fp(wk8['ref_none'])} a year (t(5): {fp(wk8['ref_none_t'])}), and 100% "
             "conditional on the depositor's own bank failing. The hybrid's facility alone would cover 5 failures: "
             f"{fp(wk8['hyb_F'])} a year (t(5): {fp(wk8['hyb_F_t'])}; {fp(wk8['hyb_F_cond'])} given the own bank fails). A "
             "tokenized buffer that is cash at any hour restores the full 20% before reopening ("
             f"{fp(wk8['mobile'])} Gaussian, {fp(wk8['mobile_t'])} t(5)), provided the depth is there. So the all-funded "
             "design should promise par within stated business days, not before reopening, unless its buffer is mobile.\n")

    # 37
    L.append("## 37. The buffer-versus-facility rule\n")
    L.append("At fixed capacity, substituting one unit of committed facility for one unit of funded buffer changes c* by "
             "fee_F + (expected drawn cost per unit of F) - s_lock. The facility pays only if its fee plus its expected drawn "
             "cost is below the buffer's lock-up premium. Capacity 20%, Q measure, rho 0.20, fixed LGD, f 15.\n")
    L.append("Expected drawn cost per unit of facility (bps a year per unit of F) by split:\n")
    L.append(table(["theta / F", "E_Q[T+0 draw], % of notional", "E_Q[term-out], % of notional", "Drawn cost (bps of notional)",
                    "Drawn cost per unit of F (bps)"],
                   [[f"{pc(th, 0)} / {pc(F_, 0)}", f"{rule_drawn[(th, F_)]['draw0'] * 100:.5f}", f"{rule_drawn[(th, F_)]['termout'] * 100:.5f}",
                     f"{rule_drawn[(th, F_)]['drawn'] / BP:.4f}",
                     "n/a" if rule_drawn[(th, F_)]["per_F"] is None else f"{rule_drawn[(th, F_)]['per_F'] / BP:.3f}"]
                    for th, F_ in V8_SPLITS]))
    L.append("\nc* (bps) by lock-up premium, facility fee and split. Bold = cheapest split in that cell group:\n")
    rows = []
    for sl in V8_SLOCK_SET:
        for fe in V5_FEE_SET:
            vals = [rule_price[(sl, fe, th, F_)] for th, F_ in V8_SPLITS]
            best = min(vals)
            rows.append([f"{sl / BP:.0f}", f"{fe / BP:.0f}"] + [("**" + b1(v) + "**") if v - best < 1e-12 else b1(v) for v in vals])
    L.append(table(["s_lock", "fee_F"] + [f"theta {pc(th, 0)} / F {pc(F_, 0)}" for th, F_ in V8_SPLITS], rows))
    L.append("\nMarginal cost of substituting one unit of facility for buffer, (c*(split) - c*(20/0)) / F, bps a year per unit "
             "(negative = the facility is cheaper):\n")
    rows = []
    for sl in V8_SLOCK_SET:
        for th, F_ in V8_SPLITS[1:]:
            rows.append([f"{sl / BP:.0f}", f"{pc(th, 0)} / {pc(F_, 0)}"] + [f"{rule_marg[(sl, fe, th, F_)] / BP:+.2f}" for fe in V5_FEE_SET])
    L.append(table(["s_lock", "theta / F"] + [f"fee {fe / BP:.0f}" for fe in V5_FEE_SET], rows))
    L.append("\nThe facility's no-credit-exposure condition at full capacity use. With all 10 failures paid, the facility is "
             "drawn F at T+0 and the advance dividends return a x capacity within the week; it is repaid in full, and never "
             "carries receivership credit risk, if theta >= (1 - a) x capacity. Otherwise it terms out by (1 - a) x capacity - "
             "theta, secured on the receivership claims, and takes a loss only if the credit loss LGD x capacity exceeds theta.\n")
    L.append(table(["theta / F", "LGD", "a", "(1 - a) x capacity", "theta >= (1 - a) x capacity", "Facility terms out",
                    "Credit loss", "Facility loss"],
                   [[f"{pc(x['th'], 0)} / {pc(x['F'], 0)}", pc(x["lgd"], 0), pc(x["a"], 0), pc(x["need"], 0),
                     "yes" if x["ok"] else "no", pc(x["termout"], 0), pc(x["loss"], 0), pc(x["fac_loss"], 0)] for x in rule_full]))
    L.append("")

    # 38
    L.append("## 38. Reliability given the depositor's own bank fails\n")
    L.append("Conditional on a given reference bank failing in the year (P measure): shortfall = P(cash needed at T+0 > capacity); "
             "severity = expected unpaid share of par given a shortfall (pro rata across the failed names); E[unpaid] = "
             "expected unpaid share of par; E[loss] = expected unpaid share x LGD (an unpaid depositor keeps its deposit claim "
             "and loses LGD on the unpaid part; state-dependent LGD, which in the t copula reads the Gaussian common factor). "
             "50 banks at 2%. All figures % of the depositor's covered balance.\n")
    L.append(f"Headline: rho {V5_RHO_FAIL:.2f}, PD 0.25%:\n")
    rows = []
    for c in V8_CAPS:
        cells = [f"{pc(c, 0)} ({int(round(c * V5_N))})"]
        for cop, _ in V8_COPULAS:
            x = rel8[(cop, LAMBDA_P, V5_RHO_FAIL, c)]
            cells += [cpx(x["sf"]), pc(x["sev"], 1), cpx(x["unpaid"], 4), cpx(x["loss"], 4)]
        rows.append(cells)
    L.append(table(["Capacity (failures)", "Gaussian: shortfall", "severity", "E[unpaid]", "E[loss]",
                    "t(5): shortfall", "severity", "E[unpaid]", "E[loss]"], rows))
    for cop, cname in V8_COPULAS:
        for pd in V5_PD_SET:
            L.append(f"\n{cname}, PD {pc(pd, 2)}: shortfall / severity / E[loss] by rho:\n")
            rows = []
            for c in V8_CAPS:
                rows.append([f"{pc(c, 0)} ({int(round(c * V5_N))})"] +
                            [f"{cpx(rel8[(cop, pd, r, c)]['sf'])} / {pc(rel8[(cop, pd, r, c)]['sev'], 1)} / "
                             f"{cpx(rel8[(cop, pd, r, c)]['loss'], 4)}" for r in V5_RHO_SET])
            L.append(table(["Capacity (failures)"] + [f"rho {r:.2f}" for r in V5_RHO_SET], rows))
    L.append("\nE[unpaid] for every case is in the headline table (rho 0.30, PD 0.25%) and equals shortfall x severity.\n")

    # 39
    L.append("## 39. Iso-reliability: capacity and price to meet a stated conditional standard\n")
    L.append(f"Smallest capacity (failures covered) at which P(shortfall | own bank fails) is at or below a round standard; rho "
             f"{V5_RHO_FAIL:.2f}, PD 0.25%, 50 banks. Prices at that capacity on the v8 base spreads (s_lock 10, fee 20, f 15; "
             f"Q, rho 0.20, Gaussian, fixed LGD); the hybrid keeps the 10/10 proportion (theta = F = capacity / 2). Single-name "
             f"vehicle {b1(SINGLE)} bps, which never falls short.\n")
    rows = []
    for cop, cname in V8_COPULAS:
        for std in V8_STANDARDS:
            x = iso8[(cop, std)]
            rows.append([cname, pc(std, 0), f"{x['k']} ({pc(x['cap'], 0)})", f"{x['sf'] * 100:.3f}%", b1(x["ref"]), b1(x["hyb"]),
                         f"{(x['ref'] - SINGLE) / BP:+.1f}"])
    L.append(table(["Copula", "Standard", "Failures covered (capacity)", "Achieved", "All-funded c*", "10/10-proportioned hybrid c*",
                    "All-funded minus single-name"], rows))
    L.append(f"\nAt the reference capacity of 20% the conditional shortfall is {rel8[('gauss', LAMBDA_P, V5_RHO_FAIL, V8_CAP)]['sf'] * 100:.3f}% "
             f"(Gaussian), just above a 1% standard, and {rel8[('t', LAMBDA_P, V5_RHO_FAIL, V8_CAP)]['sf'] * 100:.3f}% (t(5)).\n")
    L.append(f"Pool size: each bank 1/N of notional; capacity needed for a {pc(V8_N_STD['gauss'], 2)} Gaussian and a "
             f"{pc(V8_N_STD['t'], 0)} t(5) conditional standard (rho 0.30, PD 0.25%), and the all-funded price at that capacity "
             "with frictions fixed at 15 bps (no per-bank friction slope is assumed):\n")
    rows = []
    for N_ in V8_N_SET:
        g, t_ = nsweep8[N_]["gauss"], nsweep8[N_]["t"]
        rows.append([N_, pc(1 / N_, 1), f"{g['k']} ({pc(g['cap'], 1)})", f"{g['sf'] * 100:.3f}%", b1(g["price"]),
                     f"{t_['k']} ({pc(t_['cap'], 1)})", f"{t_['sf'] * 100:.2f}%", b1(t_["price"])])
    L.append(table(["Banks N", "Cap per bank", "Gaussian 1%: failures (capacity)", "achieved", "all-funded c*",
                    "t(5) 5%: failures (capacity)", "achieved", "all-funded c*"], rows))
    L.append("")

    # 40
    L.append("## 40. Year 2 after a cluster, and reinstatement\n")
    L.append(f"Year 1 ends with K simultaneous failures at LGD {pc(V8_Y1_LGD, 0)} and a {pc(V8_Y1_ADV, 0)} advance dividend. Per "
             f"failure the buffer has paid 2% and got back {pc(V8_Y1_ADV, 0)} of it; of the rest, LGD is lost and 1 - a - LGD sits in "
             "receivership certificates until final dividends (about 2 years). Regimes for Year-2 capacity: (A) unreplenished, "
             "capacity reduced by credit loss and certificates; (B) certificate financing at an "
             f"{pc(V8_CERT_ADV, 0)} advance rate, a scenario only (there is no evidenced repo market for receivership "
             "certificates); (C) contractual reinstatement to full capacity. Year 2: 50 - K surviving banks, each still 2% of the "
             "original notional; the Year-2 common factor is independent of Year 1; rho 0.30; PD 0.25% (and doubled to 0.50% "
             "as a sensitivity). Capacity is % of the original notional.\n")
    L.append(table(["Year-1 failures", "Surviving banks"] + [f"({reg}) {nm}" for reg, nm in Y2_REGIMES],
                   [[K1, V5_N - K1] + [pc(y2_cap[(K1, reg)], 1) for reg, _ in Y2_REGIMES] for K1 in V8_Y1_N]))
    L.append("")
    for pd in V5_PD_SET:
        L.append(f"Year-2 shortfall, PD {pc(pd, 2)}: conditional on the depositor's own bank failing in Year 2 / unconditional "
                 "(cannot pay par) / E[unpaid share | own bank fails]:\n")
        rows = []
        for K1 in V8_Y1_N:
            for cop, cname in V8_COPULAS:
                rows.append([K1, cname] + [f"{y2[(K1, cop, pd, reg)]['cond'] * 100:.3f}% / {fp(y2[(K1, cop, pd, reg)]['uncond'])} / "
                                           f"{y2[(K1, cop, pd, reg)]['unpaid'] * 100:.4f}%" for reg, _ in Y2_REGIMES])
        L.append(table(["Year-1 failures", "Copula"] + [f"({reg})" for reg, _ in Y2_REGIMES], rows))
        L.append("")
    L.append("Year-1 reference (50 banks, capacity 20%, PD 0.25%): " + "; ".join(
        f"{cname} conditional {y1_ref[cop]['cond'] * 100:.3f}%, unconditional {fp(y1_ref[cop]['uncond'])}" for cop, cname in V8_COPULAS)
             + ". Full reinstatement lowers the conditional shortfall below Year 1 because the pool is smaller while capacity "
             "stays at 20% of the original notional.\n")
    L.append("Pricing the reinstatement (regime C). Method: at inception, investors commit to restore the buffer to full capacity "
             "at renewal after any loss year. The amount called after a year with n failures is R(n) = min(n x 2%, 20%) x (1 - a) "
             f"(paid out less the advance dividend); the committed amount is the largest call, K = 20% x (1 - a) = {pc(REINST_K, 0)}. "
             "Ex-ante annual cost = E_Q[R] x s_lock x T_lock + fee_R x K, where the first term is the Q-expected replenishment "
             f"money locked alongside the old buffer's certificates for T_lock = {V8_REINST_LOCK:g} years at the buffer's lock-up "
             f"premium ({bps(V5_S_LOCK)} bps), and fee_R is a commitment fee on K (no verified market price; swept). Q measure, "
             f"rho 0.20, fixed LGD: E_Q[R] = {REINST_EQ * 100:.3f}% of notional; Q-probability the commitment is called "
             f"{fp(REINST_P_CALL)} a year.\n")
    L.append(table(["Commitment fee fee_R (bps on K)", "E_Q[R] x s_lock x T_lock (bps)", "fee_R x K (bps)", "Reinstatement cost (bps a year)",
                    "All-funded reference with reinstatement c*"],
                   [[f"{fe / BP:.0f}", f"{v['double_lock'] / BP:.3f}", b1(v["commit"]), b1(v["total"]), b1(REF8 + v["total"])]
                    for fe, v in reinst.items()]))
    L.append(f"\nAlternative: pre-fund the same {pc(REINST_K, 0)} as extra buffer, at K x s_lock = {b1(REINST_PREFUND)} bps a year, which "
             "also raises Year-1 capacity to 30%. A commitment is cheaper than pre-funding only if fee_R is below s_lock: the "
             "buffer-versus-facility rule again.\n")
    L.append(f"Pre-funded alternative (v9): an all-funded buffer of {pc(0.20 + REINST_K, 0)} prices at {b1(REINST_PREFUND_CSTAR)} bps "
             f"(rho 0.20, fixed LGD), against {b1(REINST_PREFUND_CSTAR - REINST_PREFUND)} for the 20% reference. Commitment and pre-funding "
             f"cost the same at fee_R = s_lock - E_Q[R] x s_lock x T_lock / K = "
             f"{(REINST_PREFUND - REINST_EQ * V5_S_LOCK * V8_REINST_LOCK) / REINST_K / BP:.2f} bps on K; above that fee pre-funding is cheaper. Year-1 "
             "conditional shortfall at 30% capacity is in Section 38.\n")
    L.append("Excess-of-loss layer above 10 failures (pays the par shortfall above 20% capacity): Q-expected par shortfall and "
             "shortfall x LGD (25%), bps of notional a year:\n")
    L.append(table(["Copula", "rho", "Q-probability the layer pays", "E_Q[par above 20%]", "E_Q[par above 20%] x LGD",
                    "P-measure E[par above 20%]"],
                   [[cname, f"{rho:.2f}", fp(xol8[(cop, rho)]["p_q"]), f"{xol8[(cop, rho)]['par'] / BP:.3f}",
                     f"{xol8[(cop, rho)]['loss'] / BP:.3f}", f"{xol8[(cop, rho)]['par_p'] / BP:.4f}"]
                    for cop, cname in V8_COPULAS for rho in V8_XOL_RHO]))
    L.append("\nThe x LGD column is the expected credit cost of the layer if it buys the claims at par; the par column is the cash "
             "it must stand ready to pay.\n")

    # 41
    L.append("## 41. Three-party clearing: price <= depositor willingness to pay + bank retention value\n")
    L.append(f"Joint surplus = Delta + WTP - c*, with c* the reference design ({b1(REF8)} bps), Delta the depositor's yield "
             f"advantage (swept, no rate levels) and WTP = dP_run x V x {V7_ANNUITY:.3f} the bank's retention value (Section 33: "
             f"relationship value V over {V7_REL_LIFE} years at r + 3%). Protection clears when the surplus is non-negative; how "
             "the surplus is split is a negotiation. bps a year of the covered balance.\n")
    rows = []
    for V in V7_REL_V:
        for dp in V7_DP_RUN:
            rows.append([f"{V / BP:.0f}", pc(dp, 1), b1(v7_wtp[(V, dp)])] + [f"{tp8[(V, dp, d_)] / BP:+.1f}" for d_ in V5_DELTA_SET])
    L.append(table(["V", "dP_run", "WTP"] + [f"Delta {d_ / BP:.0f}" for d_ in V5_DELTA_SET], rows))
    L.append(f"\nWith no bank retention value (WTP 0) the condition is Delta >= {b1(REF8)}. Smallest Delta that clears (bps):\n")
    L.append(table(["V", "dP_run", f"All-funded reference ({b1(REF8)})", f"10/10 hybrid ({b1(hyb8['c_star'])})", f"Single-name ({b1(SINGLE)})"],
                   [[f"{V / BP:.0f}", pc(dp, 1)] + [b1(tp8_min[(V, dp)][k_]) for k_ in ("ref", "hyb", "sn")]
                    for V in V7_REL_V for dp in V7_DP_RUN]))
    L.append("")

    # 42
    L.append("## 42. Exact cash-flow check of the four-term formula\n")
    L.append(f"Exact: constant hazard h = -ln(1 - lambda_Q) = {ex8['h'] * 100:.4f}% (lambda_Q {pc(lambda_q(), 2)} is a one-year "
             "probability in the formula); premium paid continuously until default or expiry and discounted at r; at default "
             f"the provider pays par, receives the advance dividend after {V8_BD} business days ({V8_BD}/{V8_BD_YEAR} years) and "
             f"the remaining recovery after D = {D_YEARS:g} years, each bridge financed at r + s_b = {pc(R_FREE + S_B, 1)} with "
             "continuous discounting. With a running premium the premium and protection legs share the survival discount, so "
             "the exact spread is h x (cost per default valued at the default date). k and f are running charges on the "
             "surviving covered balance in both. For the pooled design with fixed LGD the credit and access terms are the same "
             "expectation per name, so the per-name exact terms apply; the all-funded design has no drawn cost.\n")
    rows = []
    for nm, x in exact8.items():
        rows.append([nm, f"{ex8['credit4'] / BP:.3f} / {ex8['credit'] / BP:.3f}", f"{ex8['adv4'] / BP:.3f} / {ex8['adv'] / BP:.3f}",
                     f"{ex8['cert4'] / BP:.3f} / {ex8['cert'] / BP:.3f}", f"{x['k'] / BP:.2f}", f"{V5_FRIC / BP:.2f}",
                     f"{x['four'] / BP:.3f}", f"{x['exact'] / BP:.3f}", f"{x['diff'] / BP:+.3f}", b1(exact8_model[nm])])
    L.append(table(["Design", "Credit: formula / exact", "Advance-dividend bridge: formula / exact", "Certificate bridge: formula / exact",
                    "k", "f", "Four-term c*", "Exact c*", "Exact minus formula", "Model c* (Section 2 / 36)"], rows))
    L.append(f"\nThe four-term formula sits within {max(abs(x['diff']) for x in exact8.values()) / BP:.2f} bps of full discounting: "
             "the hazard conversion adds to the credit term, while simple interest on the certificate bridge slightly overstates "
             "the access term and the 5-day advance-dividend bridge, which the formula omits, adds a little back. Memo: paid as one "
             f"premium at inception instead of running, the same protection is worth {b1(exact8['Single-name funded vehicle']['upfront'])} "
             f"(single-name) and {b1(exact8['All-funded reference (theta 20%, F 0)']['upfront'])} (reference) bps of notional "
             f"(annuity factor {ex8['annuity']:.4f}); that is a premium-timing convention, not an approximation error.\n")

    # 43
    st = rule_drawn[(0.10, 0.10)]
    g20, t20 = rel8[("gauss", LAMBDA_P, V5_RHO_FAIL, V8_CAP)], rel8[("t", LAMBDA_P, V5_RHO_FAIL, V8_CAP)]
    o = [
        f"Reference design. The all-funded 20% buffer prices at {b1(REF8)} bps (credit {b1(ref8['credit'])}, access "
        f"{b1(ref8['access'])}, lock-up {b1(ref8['lock'])}, frictions {b1(ref8['f'])}); the 10/10 hybrid at a 20 bps fee is "
        f"{b1(hyb8['c_star'])}; the single-name vehicle {b1(SINGLE)}. State-dependent LGD: {b1(ref8_rho_corr[0.10])}, "
        f"{b1(ref8_rho_corr[0.20])}, {b1(ref8_rho_corr[0.30])} at rho 0.10, 0.20, 0.30; PD 0.50%: {b1(ref8_pd50['fixed'])}. "
        f"Failure to pay par: {fp(CRR_P0)} a year Gaussian, {fp(crr['t'][1])} t(5), the same as the hybrid, with no "
        "facility-provider, MAC or term-out failure mode.",
        f"Rule. Replacing buffer with facility changes c* by fee_F + drawn cost per unit of F - s_lock per unit; the drawn cost "
        f"is {st['per_F'] / BP:.3f} bps per unit of F at 10/10, so the facility pays only when its fee is below the lock-up "
        f"premium. At s_lock 10 and fee 20 the all-funded design is cheapest; at s_lock 45 (a sweep point) and fee 20 the 5/15 "
        f"split is {b1(rule_price[(45 * BP, 20 * BP, 0.05, 0.15)])} against {b1(rule_price[(45 * BP, 20 * BP, 0.20, 0.0)])} all-funded. "
        "The facility carries no receivership credit exposure at full use if theta >= (1 - a) x capacity: 10/10 meets it at "
        "a 50% advance dividend and fails it at 30% (terms out 4%, no loss); 5/15 fails it at both and takes a 3% loss at LGD 40%.",
        f"Conditional reliability at 20% capacity (rho 0.30, PD 0.25%, own bank fails): shortfall {g20['sf'] * 100:.3f}% Gaussian, "
        f"{t20['sf'] * 100:.3f}% t(5); severity {pc(g20['sev'], 1)} and {pc(t20['sev'], 1)} of par; expected loss "
        f"{g20['loss'] * 100:.4f}% and {t20['loss'] * 100:.4f}% of the balance. Safe for one, not for all: the bad years are "
        "the ones that call the protection.",
        "Iso-reliability (rho 0.30): " + "; ".join(
            f"{cn} {pc(std, 0)} needs {iso8[(cop, std)]['k']} failures ({pc(iso8[(cop, std)]['cap'], 0)}), all-funded "
            f"{b1(iso8[(cop, std)]['ref'])}, hybrid {b1(iso8[(cop, std)]['hyb'])}"
            for cop, cn in V8_COPULAS for std in V8_STANDARDS) + f"; single-name {b1(SINGLE)}.",
        f"Year 2 (Gaussian, conditional): after 3 failures {y2[(3, 'gauss', LAMBDA_P, 'A')]['cond'] * 100:.3f}% unreplenished "
        f"(capacity {pc(y2_cap[(3, 'A')], 0)}), {y2[(3, 'gauss', LAMBDA_P, 'B')]['cond'] * 100:.3f}% with certificate financing "
        f"({pc(y2_cap[(3, 'B')], 1)}), {y2[(3, 'gauss', LAMBDA_P, 'C')]['cond'] * 100:.3f}% reinstated; after 6: "
        f"{y2[(6, 'gauss', LAMBDA_P, 'A')]['cond'] * 100:.3f}%, {y2[(6, 'gauss', LAMBDA_P, 'B')]['cond'] * 100:.3f}%, "
        f"{y2[(6, 'gauss', LAMBDA_P, 'C')]['cond'] * 100:.3f}%. t(5): after 3 "
        f"{y2[(3, 't', LAMBDA_P, 'A')]['cond'] * 100:.2f}% / {y2[(3, 't', LAMBDA_P, 'B')]['cond'] * 100:.2f}% / "
        f"{y2[(3, 't', LAMBDA_P, 'C')]['cond'] * 100:.2f}%; after 6 {y2[(6, 't', LAMBDA_P, 'A')]['cond'] * 100:.2f}% / "
        f"{y2[(6, 't', LAMBDA_P, 'B')]['cond'] * 100:.2f}% / {y2[(6, 't', LAMBDA_P, 'C')]['cond'] * 100:.2f}%. Reinstatement "
        f"costs {b1(reinst[V8_REINST_FEE]['total'])} bps a year at a 20 bps commitment fee ({b1(reinst[10 * BP]['total'])} at 10), "
        f"against {b1(REINST_PREFUND)} to pre-fund the same amount.",
        f"Excess-of-loss above 10 failures (rho 0.30, Q): expected par shortfall {xol8[('gauss', 0.30)]['par'] / BP:.3f} bps "
        f"Gaussian and {xol8[('t', 0.30)]['par'] / BP:.2f} bps t(5); times LGD {xol8[('gauss', 0.30)]['loss'] / BP:.3f} and "
        f"{xol8[('t', 0.30)]['loss'] / BP:.2f} bps.",
        f"Three-party clearing at the reference price {b1(REF8)}: with no bank retention value the depositor needs Delta >= "
        f"{b1(REF8)}; at V 100 and dP_run 1% (WTP {b1(v7_wtp[(100 * BP, 0.01)])}) Delta >= {b1(tp8_min[(100 * BP, 0.01)]['ref'])}; "
        f"at V 150 and dP_run 5% (WTP {b1(v7_wtp[(150 * BP, 0.05)])}) Delta >= {b1(tp8_min[(150 * BP, 0.05)]['ref'])}. "
        + ("In no cell of the sweep does the bank's retention value alone cover the price." if max(v7_wtp.values()) < REF8
         else "In some cells the bank's retention value alone covers the price."),
        f"Exact check: full discounting moves the single-name price by {exact8['Single-name funded vehicle']['diff'] / BP:+.3f} "
        f"bps and the reference by {exact8['All-funded reference (theta 20%, F 0)']['diff'] / BP:+.3f} bps.",
        f"Rate update: r 4.3% (v7 3.9%) moves the single-name c* from {b1(a7['sn'])} to {b1(a8['sn'])}, the hybrid from "
        f"{b1(a7['hyb'])} to {b1(a8['hyb'])}, the reference from {b1(a7['ref'])} to {b1(a8['ref'])}, and the bank SBLC from "
        f"{b1(a7['ball'])} to {b1(a8['ball'])} (capital cost {a7['cap'] / BP:.2f} to {a8['cap'] / BP:.2f}).",
    ]
    L.append("## 43. What the v8 numbers say\n")
    L.extend(f"{i}. {t}" for i, t in enumerate(o, 1))
    L.append("")
    L.append("v8 modelling notes (choices made in Part IV):\n")
    notes8 = [
        "Conditional statistics condition on the depositor's own bank failing under P; severity and loss use the pro rata "
        "sharing rule of Section 16. Under the t copula the state-dependent LGD reads only the Gaussian common factor z.",
        "Iso-reliability prices use the base pricing measure (rho 0.20, Gaussian, fixed LGD); with no facility the copula "
        "moves the all-funded price only through credit and access expectations, which do not depend on it at fixed LGD.",
        "Year 2 holds each surviving bank at 2% of the original notional and does not admit new banks; capacity is measured "
        "against the original notional. Certificate financing (regime B) is a scenario with no evidenced market.",
        "Reinstatement cost follows the stated method: E_Q[R] x s_lock x T_lock + fee_R x K. It omits any premium investors "
        "would demand for committing to fund in a cluster year beyond the commitment fee.",
        "The run time in the header is rounded to the nearest whole minute so that the results file is identical across runs.",
    ]
    L.extend(f"{i}. {t}" for i, t in enumerate(notes8, 1))
    L.append("")

    # 44
    L.append("## 44. Settlement regimes at the trigger, and the banker's term-premium value (pilot hypothesis)\n")
    L.append("Three ways the vehicle can settle when a reference bank fails, 50 banks at 2% each, rho 0.30, PD 0.25%, "
             "correlated LGD, reliability conditional on the depositor's own bank failing (as Sections 38 and 39). Gross par: "
             "the vehicle buys the whole claim at par at T+0 and collects the advance dividend; each failure draws 2.0% of pool "
             "notional. Net of dividend: the depositor collects the FDIC advance dividend a directly and the vehicle pays par "
             "less the dividend actually paid at day 7 against the receivership certificate; each failure draws 2% x (1 - a), "
             "and a is state-dependent (a = (2/3)(1 - LGD), 40% in the worst states, 50% at the base LGD), so the draw rises "
             "exactly in the states that produce shortfalls; with no dividend the rule collapses to gross par. The figures assume "
             "the dividend has been paid by day seven; a later payment pushes that failure's draw back toward the gross-par row. "
             "Junior slice: "
             f"the vehicle pays a fixed {pc(V8_JUNIOR_M, 0)} of par in cash at day 7, takes the recoveries above "
             f"{pc(1 - V8_JUNIOR_M, 0)} of par and pays a carry coupon at r + s_b on the depositor's outstanding certificate; "
             f"each failure draws {pc(V8_JUNIOR_M / V5_N, 2)} of pool notional; the vehicle bears LGD up to {pc(V8_JUNIOR_M, 0)} "
             "and the depositor any excess. The price c* is the all-funded price at the regime's buffer: the credit term is "
             "unchanged under net (the vehicle still bears the whole LGD) and under the junior slice while LGD stays at or "
             f"below {pc(V8_JUNIOR_M, 0)}, which holds throughout the correlated mapping (15% to 40%); the access term is the "
             "same certificate carry in every regime. What changes is the depositor's position: under gross par it holds "
             "cash at T+0; under net it holds the dividend when the FDIC pays it (usually within 30 days, at the FDIC's "
             "discretion) and the rest at day 7; under the junior slice it holds the dividend, the cash slice and a senior "
             f"claim on recoveries up to {pc(1 - V8_JUNIOR_M, 0)}.\n")
    rows = []
    for code, label in V8_UNB_REGIMES:
        g, t_ = unb8[("gauss", code)], unb8[("t", code)]
        draw = (f"2% x (1 - a): {unb8_pool['gauss']['e_draw_net'] * 100:.2f}% / {unb8_pool['t']['e_draw_net'] * 100:.2f}% mean "
                f"(Gaussian / t, given own failure)" if code == "net"
                else pc(unb_draw(pool(LAMBDA_P, V5_RHO_FAIL, "corr"), code)[0, 0], 2))
        cov = " / ".join(str(unb8_cov[(code, a_)]) for a_ in V8_UNB_ADV_SHOW)
        rows.append([label, draw, cov, pc(V8_CAP, 0), b1(unb8_c_ref), cpx(g["sf"]), cpx(t_["sf"]), cpx(t_["loss"], 4)])
    L.append(table(["Settlement regime", "Pool draw per failure", f"Failures covered in full (a {pc(V8_UNB_ADV_SHOW[0], 0)} / "
                    f"{pc(V8_UNB_ADV_SHOW[1], 0)})", "Buffer theta", "All-funded c*", "Gaussian shortfall", "t(5) shortfall",
                    "t(5) E[depositor loss]"], rows))
    L.append(f"\nState dependence of the advance dividend, conditional on own failure: E[a] "
             f"{pc(unb8_pool['gauss']['e_adv'], 1)} (Gaussian) and {pc(unb8_pool['t']['e_adv'], 1)} (Student-t); "
             f"P(a < 50%) {pc(unb8_pool['gauss']['p_adv_lt'], 0)} and {pc(unb8_pool['t']['p_adv_lt'], 0)}. Holding the dividend "
             f"at a fixed 50% regardless of state, the net rule would print a conditional shortfall of "
             f"{cpx(unb8_pool['gauss']['sf_net_fixed_a'])} (Gaussian) and {cpx(unb8_pool['t']['sf_net_fixed_a'])} (Student-t) "
             f"at the 20% buffer; the state-dependent draw above is the model's figure. Under the junior slice the cap binds "
             f"only if LGD exceeds {pc(V8_JUNIOR_M, 0)}, which the mapping never reaches (P = "
             f"{cpx(unb8_pool['t']['p_lgd_gt_m'])}); an LGD above it, the register's stress, would leave the excess with the "
             "depositor.\n")
    L.append("Iso-reliability across settlement regimes: smallest buffer theta* (rounded up to 0.1%, so the printed buffer meets "
             "the standard) and all-funded price c* (bps) "
             f"meeting round conditional shortfall standards (single-name vehicle {b1(SINGLE)} bps):\n")
    rows = []
    for cop, cname in V8_COPULAS:
        for std in V8_STANDARDS:
            cells = [cname, pc(std, 0)]
            for code, _ in V8_UNB_REGIMES:
                x = unb8[(cop, code)]["iso"][std]
                cells.append("n/a" if x["theta"] is None else f"{pc(x['theta'], 1)} / {b1(x['c_star'])}")
            rows.append(cells)
    L.append(table(["Copula", "Standard"] + [f"{lab}: theta* / c*" for _, lab in V8_UNB_REGIMES], rows))
    L.append("\nBanker's term-premium value, a hypothesis for the Section 14 pilot and not a result. If protected balances prove "
             "stable in the bank's internal liquidity stress test, the bank could move a share phi_rel of the covered balance "
             "from overnight liquidity into its structural replicating ladder and be credited the term premium s_term through "
             "funds transfer pricing. s_term of 50 to 80 bps straddles the Kim-Wright term-premium estimates published on FRED, "
             "54 bps at 3 years and 64 bps at 5 years on 23 October 2026 (THREEFYTP3 0.5353%, THREEFYTP5 0.6353%), and its top "
             "reaches the 1-month to 3- and 5-year Treasury slope of 73 to 78 bps on 28 October 2026 (DGS1MO 4.07%, DGS3 4.80%, "
             "DGS5 4.85%); the expected excess return of a ladder over rolling cash is the term premium, which is smaller than "
             "the slope when short rates are expected to rise, so the upper half of the range is generous. Asset or credit spread "
             "is excluded. The "
             "standardized LCR gives no credit for private protection, so the release is zero for an LCR-bound bank. Shown "
             f"beside two retention-value cells of Section 41 (WTP_run = dP_run x V x {V7_ANNUITY:.3f}) and the smallest "
             f"depositor advantage Delta that then clears the {b1(REF8)} bps reference price:\n")
    rows = []
    for ph in V8_PHI_REL:
        for st in V8_S_TERM:
            cells = [pc(ph, 0), f"{st / BP:.0f}", b1(bank_term8[(ph, st)])]
            for V, dp in V8_BANK_CELLS:
                cells.append(f"{b1(bank_tot8[(ph, st, V, dp)])} / {b1(bank_min_delta8[(ph, st, V, dp)])}")
            rows.append(cells)
    L.append(table(["Released share phi_rel", "Term premium s_term (bps)", "Term value (bps a year)"]
                   + [f"V {V / BP:.0f}, dP_run {pc(dp, 0)}: bank total / min Delta" for V, dp in V8_BANK_CELLS], rows))
    L.append("")
    RESULTS_MD.write_text("\n".join(L), encoding="utf-8")


def make_figures_v8():
    """fig-10 conditional shortfall vs capacity; fig-11 Year-2 conditional shortfall by regime."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    NAVY, STEEL, SLATE, MIST, INK, GRID, ACCENT = "#1F3A5F", "#4F74A8", "#8A9AAE", "#C9D3DF", "#2B2B2B", "#E3E7EC", "#D2851F"
    MUTED = "#4A5361"
    plt.rcParams.update({
        "font.family": "Inter", "font.size": 10, "axes.edgecolor": "#8C96A3", "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "text.color": INK,
    })
    SRC = "Source: author's calculations."

    def frame(fig, title, subtitle, source, sub_y=0.905):
        fig.text(0.06, 0.955, title, fontsize=14, fontweight="semibold", ha="left", va="top", color=INK)
        fig.text(0.06, sub_y, subtitle, fontsize=10, ha="left", va="top", color="#5A6472")
        fig.text(0.06, 0.03, source, fontsize=7.5, ha="left", va="bottom", color="#6B7480")

    # ---- fig-10: conditional shortfall given own bank fails vs capacity ----------------------------
    fig, ax = plt.subplots(figsize=(8, 5.6))
    fig.subplots_adjust(left=0.12, right=0.84, top=0.78, bottom=0.25)     # top lowered for the two-line title
    FLOOR = 1e-5
    ks = np.arange(0, 41)
    caps = ks / V5_N * 100
    for std in V8_STANDARDS:
        ax.axhline(std, color=GRID, lw=1.0, ls=(0, (1, 1.5)), zorder=0)
        ax.text(81, std, f"{std:.0%}", fontsize=8.3, color=MUTED, va="center", ha="left", clip_on=False)
    for cop, col, lab in (("gauss", NAVY, "Gaussian copula"), ("t", ACCENT, "Student-t(5) copula")):
        ys = [max(rel8_curve[cop][k_], FLOOR) for k_ in ks]
        ax.plot(caps, ys, color=col, lw=2.2, drawstyle="steps-post")
        y20 = rel8_curve[cop][int(round(V8_CAP * V5_N))]
        ax.plot([V8_CAP * 100], [y20], marker="o", ms=7, mfc="white", mec=col, mew=1.8, zorder=5)
        ax.annotate(f"{y20 * 100:.1f}%", xy=(V8_CAP * 100, y20),
                    xytext=(V8_CAP * 100 + 5, 0.75) if cop == "t" else (V8_CAP * 100 - 9, 2.5e-3),
                    fontsize=8.8, color=col, ha="left", va="center", arrowprops=dict(arrowstyle="-", color=col, lw=0.7))
        if cop == "t":
            ax.text(81, ys[-1], lab.replace(" copula", "\ncopula"), color=col, fontsize=9, va="center", ha="left",
                    clip_on=False)      # two lines, so the label fits the right margin with the fallback font
        else:
            ax.text(40, 1.6e-3, lab, color=col, fontsize=9, va="center", ha="left")
    for std in (0.05, 0.01):
        x = iso8[("t", std)]
        ax.plot([x["cap"] * 100], [std], marker="D", ms=5, color=ACCENT, zorder=5)
        ax.annotate(f"t(5) {std:.0%}: {x['cap'] * 100:.0f}%", xy=(x["cap"] * 100, std), xytext=(x["cap"] * 100 - 2, std * 0.3),
                    fontsize=8.3, color="#9A5A0A", ha="right", arrowprops=dict(arrowstyle="-", color=ACCENT, lw=0.6))
    ax.axvline(V8_CAP * 100, color=INK, lw=0.9, ls=(0, (4, 2)))
    ax.text(V8_CAP * 100 + 0.8, 2.2e-5, "Reference design:\nall-funded 20% buffer", fontsize=8.5, color=INK, va="bottom", ha="left")
    ax.set_yscale("log")
    ax.set_ylim(FLOOR, 1.3)
    ax.set_yticks([1, 1e-1, 1e-2, 1e-3, 1e-4, 1e-5])
    ax.set_yticklabels(["100%", "10%", "1%", "0.1%", "0.01%", "0.001%"])
    ax.minorticks_off()
    ax.set_xlim(0, 80)
    ax.set_xticks(range(0, 81, 10))
    ax.set_xticklabels([f"{v}%" for v in range(0, 81, 10)])
    ax.set_xlabel("Capacity, % of covered notional (each failure needs 2%)", fontsize=9.5, color=MUTED)
    ax.set_ylabel("P(par shortfall | own bank fails), log scale", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    frame(fig, "Given the depositor's own bank fails,\nthe tail model decides the capacity",
          "Probability the pooled vehicle cannot pay par in a year in which the depositor's own bank fails",
          SRC + " 50 banks at 2% each, default probability 0.25%, asset correlation 0.30, all of a year's failures in one\n"
          "advance-dividend window, real-world measure. Diamonds mark the capacity a t(5) copula needs for 5% and 1% conditional\n"
          "standards. Illustrative parameters, not estimates for any bank.", sub_y=0.855)
    fig.savefig(FIG(10), dpi=200)
    plt.close(fig)

    # ---- fig-11: Year-2 conditional shortfall by regime ------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(10, 5.6))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.76, bottom=0.31, wspace=0.28)
    cols = {"A": SLATE, "B": STEEL, "C": NAVY}
    Wb = 0.26
    for ax, (cop, cname) in zip(axs, V8_COPULAS):
        vmax = 0
        for gi, K1 in enumerate(V8_Y1_N):
            for bi, (reg, _) in enumerate(Y2_REGIMES):
                v = y2[(K1, cop, LAMBDA_P, reg)]["cond"] * 100
                vmax = max(vmax, v)
                x = gi + (bi - 1) * (Wb + 0.02)
                ax.bar(x, v, Wb, color=cols[reg])
                ax.text(x, v, f"{v:.2f}%" if cop == "gauss" else f"{v:.1f}%", ha="center", va="bottom", fontsize=8.5, color=INK)
        y1 = y1_ref[cop]["cond"] * 100
        ax.axhline(y1, color=ACCENT, lw=1.4, ls=(0, (4, 2)))
        ax.set_xticks(range(len(V8_Y1_N)))
        ax.set_xticklabels([f"After {K1} failures in Year 1\n({V5_N - K1} banks left)" for K1 in V8_Y1_N], fontsize=9.5)
        ax.tick_params(axis="x", length=0)
        ax.set_ylim(0, vmax * 1.22)
        ax.set_xlim(-0.55, 1.55)
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _, big=vmax > 5: f"{v:.0f}%" if big else f"{v:.1f}%"))
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_title(f"{cname} copula", loc="left", fontsize=10.5, fontweight="semibold", pad=10)
    axs[0].set_ylabel("P(par shortfall | own bank fails in Year 2)", fontsize=9.5, color=MUTED)
    from matplotlib.lines import Line2D
    handles = [Patch(color=cols[reg], label=f"({reg}) {nm}") for reg, nm in Y2_REGIMES]
    handles.append(Line2D([0], [0], color=ACCENT, lw=1.4, ls=(0, (4, 2)),
                          label=f"Year 1 at full capacity: {y1_ref['gauss']['cond'] * 100:.2f}% Gaussian, {y1_ref['t']['cond'] * 100:.1f}% t(5)"))
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.125), ncol=2, frameon=False, fontsize=8.8, handlelength=1.6)
    frame(fig, "After a cluster, an unreplenished buffer is weaker when the next failure comes",
          "Year-2 shortfall given the depositor's own bank fails, all-funded design, by how the buffer is restored",
          SRC + " Year-1 failures at LGD 25% and a 50% advance dividend. (A) capacity reduced by credit loss and receivership\n"
          "certificates: 17% after 3, 14% after 6; (B) certificates financed at an 80% advance, a scenario with no evidenced market;\n"
          "(C) restored to 20%. Surviving banks each 2% of the original notional, default probability 0.25%, correlation 0.30,\n"
          "Year-2 common factor independent of Year 1. Illustrative parameters, not estimates for any bank.")
    fig.savefig(FIG(11), dpi=200)
    plt.close(fig)


# =============================================================================
# 7. RUN
# =============================================================================
if __name__ == "__main__":
    import matplotlib
    FIGURES.mkdir(parents=True, exist_ok=True)
    make_figures()
    make_figures_v6()
    make_figure_v7()
    make_figures_v8()
    elapsed = time.perf_counter() - _T_START
    mins = max(1, int(elapsed / 60 + 0.5))                    # nearest whole minute, so reruns write the same file
    meta = dict(python=sys.version.split()[0], numpy=np.__version__, matplotlib=matplotlib.__version__,
                runtime=f"about {mins} minute{'s' if mins > 1 else ''}")
    write_results_v8(meta)
    for name, c in base.items():
        print(f"{name:26s} credit {bps(c['credit'])}  access {bps(c['access'])}  capital {bps(c['capital'])}  "
              f"k {bps(c['capacity'])}  f {bps(c['frictions'])}  c* {bps(c['c_star'])}  haircut {bps(c['haircut'])}")
    print(f"Bank: Q {bps(bank['q']['c_star'])}, P {bps(bank['p']['c_star'])}, all-in {bps(bank['all_in'])} ({bank['binding']}); "
          f"floor {bps(floor)}; stress {bps(bank_stress['all_in'])}; zero-k {bps(bank_zero['all_in'])}; cross {pct(bank_cross)}")
    print(f"Pooled 10/10 hybrid c* {b1(mid['c_star'])} (corr {b1(mid_corr['c_star'])}); bank fee floor {b1(BANK_FEE_LO)} to "
          f"{b1(BANK_FEE_HI)}; break-even fee theta 10% {breakeven_fee[(V5_CAP, 0.10, V5_FRIC)] / BP:.0f} bps")
    print(f"All-funded reference c* {b1(REF8)}; P(cannot pay par) at 20% capacity, rho 0.30: {fp(CR_P0)}; t(5) {fp(cr['t'][1])}")
    print(f"Conditional shortfall at 20%, rho 0.30: Gaussian {rel8[('gauss', LAMBDA_P, V5_RHO_FAIL, V8_CAP)]['sf'] * 100:.3f}%, "
          f"t(5) {rel8[('t', LAMBDA_P, V5_RHO_FAIL, V8_CAP)]['sf'] * 100:.3f}%")
    print(f"Wrote {RESULTS_MD}")
    for n in range(1, 12):
        print(f"Wrote {FIG(n)}")
    print(f"Run time {elapsed:.1f} s")
