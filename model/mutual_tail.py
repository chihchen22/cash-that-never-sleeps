"""
mutual_tail.py (Cash That Never Sleeps, Chapter 5): pricing and sizing a three-layer private protection design
for the uninsured excess of large corporate deposits at regional banks.

What it does
    Extends the clearing-cost engine of Chapter 3 (model/clearing_cost.py, beside this script, imported by
    path, never copied) to a stack of three layers over a pool of member banks:
      1. reciprocal placement (FDIC-insured), outside the model: the model covers the excess that is not placed;
      2. a member-owned excess-deposit mutual: a reserve theta_m of covered excess in Treasury bills, paid in as a
         capital contribution at entry (so it stands at target on day one), plus a special assessment on surviving
         members capped at m times the annual assessment;
      3. the clearing-cost engine's Treasury-backed funded vehicle, re-attached above the mutual: it pays from the point where the
         mutual's resources run out, with a funded thickness T = X - A, where A = theta_m + m x assessment is the
         nominal attachment and X the exhaustion point. Above X the loss is public and unprotected.
    The reference design sizes X so that, in a year in which the median member fails, the probability the stack
    cannot make the payment in full is at most 1% under the Gaussian copula at rho 0.30 (the standard of
    results_clearing_cost.md, Section 39); the Student-t(5) 5% design is the disclosed alternative.

Settlement (two rules, mixed)
    Rule M (primary): at closure the stack pays the FDIC the uninsured loss share of the failed member's covered
    excess so that an acquirer assumes every deposit whole on day one. Cash at the trigger = LGD x covered excess;
    no advance dividend, no later receivership dividend (the FDIC keeps the claim); the depositor never waits.
    The special assessment is collected from survivors only within the week, so under rule M the tail advances the
    assessment slice at closure and is repaid from the assessment when it is collected: cash at closure is the
    reserve plus the tail. The tail's funded commitment is therefore X - theta_m (its layer T plus the advance),
    and it carries the advance for up to ADV_DAYS days at ADV_RATE.
    Rule B (fallback, results_clearing_cost.md, Section 44): the depositor collects the FDIC advance dividend a on day one and the
    layers pay par less the dividend on day seven; cash = (1 - a) x covered excess, economic loss LGD, remaining
    recovery 1 - a - LGD funded for D years at r + s_b. a = (2/3)(1 - LGD), the clearing-cost engine's linked dividend.
    Rule M applies with probability q_acq that an acquirer takes all deposits at closure; the draw is common to
    all of a year's failures (acquirer appetite treated as a market-wide state). A Monte Carlo shows the same
    statistics when the draw is independent failure by failure.

Prices, per unit of covered excess per year
    mutual assessment = EL_P(retained) + access_P(retained) + theta_m x reserve opportunity cost + f_m + tail premium
    tail premium      = EL_Q(layer) + access_Q(layer) + (s_lock + tail frictions per unit of thickness) x commitment
                        + q x E_Q[advance] x ADV_RATE x ADV_DAYS / 365      (commitment = T + advance capacity)
    The mutual's members self-insure, so its own layer is priced under the real-world measure P; the tail layer's
    investors price under Q = mu x lambda_P, as in the clearing-cost engine. The special-assessment capacity depends on the
    assessment, so the price is solved as a fixed point.

Method
    With a uniform default probability the names are exchangeable, so given k failures the failed set is a
    uniformly random k-subset. The failed share S is distributed as sum_k P(K = k) x Q_k(S), with P(K = k) the
    clearing-cost engine's exact count distribution from pool() (both copulas) and Q_k the exact subset-sum distribution of the
    member weights on a grid of 1/30,000 of covered excess. Conditioning on a given member failing uses the
    clearing-cost engine's ref_cond weights. The risk-class mix (three default probabilities) uses the same recursion within each
    class, mixed over joint class counts and convolved in the frequency domain (fixed LGD only).

Inputs   The clearing-cost engine's parameter block (imported), plus the parameters below. All are author assumptions,
         illustrative and calibrated to no bank, except figures labelled as reported public benchmarks.
Outputs  model/results_mutual_tail.md and figures/mutual_tail/fig-M01.png to fig-M09.png.
         Importing this module computes every table but writes nothing (run Python with -B so the
         interpreter does not cache bytecode).
Run      python -I -B model/mutual_tail.py   (from the repository root)
Seeds    20261101 (member sizes), 20261102 (risk classes), 20261103 and 20261104 (one-year Monte Carlo check),
         20261105 to 20261107 (ten-year reserve paths), 20261108 and 20261109 (settlement-draw sensitivity).
"""

import sys
import time
import math
import re
from pathlib import Path

_T_START = time.perf_counter()
sys.dont_write_bytecode = True                    # importing the clearing-cost module must leave nothing in its folder

HERE = Path(__file__).resolve().parent            # model/
ROOT = HERE.parent                                # repository root
CC_RESULTS = HERE / "results_clearing_cost.md"    # the clearing-cost engine's results file (read for parity)
RESULTS_MD = HERE / "results_mutual_tail.md"
FIGURES = ROOT / "figures" / "mutual_tail"        # created at run time if absent
SCRIPT_NAME = "mutual_tail.py"
N_FIGS = 9
FIG = lambda n: FIGURES / f"fig-M{n:02d}.png"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import clearing_cost as cc                        # noqa: E402  (the clearing-cost engine; computes its tables, writes nothing)
import numpy as np                                # noqa: E402

# =============================================================================
# 1. PARAMETERS (each defined once; rates as decimals, 1 bp = 0.0001)
# =============================================================================
BP = cc.BP
# --- taken from the clearing-cost engine's parameter block (author assumptions there) ------------------------------
LAMBDA_P, MU, LGD, ADV, D_YEARS = cc.LAMBDA_P, cc.MU, cc.LGD_DEP, cc.ADV_DIV, cc.D_YEARS
R_FREE, S_B = cc.R_FREE, cc.S_B
RHO_PRICE = cc.V5_RHO_MID                         # 0.20: the clearing-cost engine's pricing correlation (base here)
RHO_FAIL = cc.V5_RHO_FAIL                         # 0.30: the clearing-cost engine's failure-statistics correlation
RHO_SET = cc.V5_RHO_SET
NU = cc.V5_T_NU
ADV_SHARE = cc.V5_ADV_SHARE                       # a = (2/3)(1 - LGD)
COPULAS = cc.V8_COPULAS
COPN = dict(COPULAS)
S_LOCK = cc.FUND_K
S_LOCK_SET = [cc.FUND_K_RANGE[0], cc.FUND_K, cc.FUND_K_RANGE[1]]
OPP = cc.POOL_RESERVE_OPP
LGD_SET = cc.LGD_SET
CC_CAP = cc.V8_CAP
TAIL_FRIC = cc.F_BASE / cc.V8_CAP                 # tail frictions per unit of funded thickness: 15 bps per 20%
TAIL_FRIC_SET = sorted(f / cc.V8_CAP for f in cc.V7_FRIC_SET)   # the clearing-cost engine's technology scenarios, per 20%
# --- the mutual [author assumptions, illustrative] ----------------------------------------------------
N_BASE = 150
N_SET = [100, 150, 200]
SIZE_SIGMA = 1.0                                  # lognormal sigma of member size
SIGMA_SET = [1.0, 1.5]
SIZE_RANGE = 250.0                                # sizes clipped to a 250:1 range: $1bn to $250bn of assets
ASSET_MIN = 1e9
LIAB_RATIO = 0.90                                 # liabilities / assets
DEMAND = 0.20                                     # covered excess sought, share of liabilities
DEMAND_SET = [0.20, 0.35, 0.50]
TIERS = [(5e9, 0.50), (5e9, 0.40), (math.inf, 0.30)]   # tiered cap on covered excess: 50% of the first $5bn of
TIER_MAX = 30e9                                   # liabilities, 40% of the next $5bn, 30% above; at most $30bn
WEIGHT_SEED = 20261101
CAP_BASE = 0.05                                   # concentration cap, applied after the tiered cap
CAP_SET = [0.02, 0.05, 0.10]
THETA_M = 0.03                                    # reserve target, paid in as capital at entry
THETA_SET = [0.02, 0.03, 0.05]
M_SA = 2
M_SET = [0, 1, 2, 3]
OPP_SET = [50 * BP, 100 * BP, 150 * BP]
F_M = 5 * BP                                      # the mutual's frictions
F_M_SET = [2 * BP, 5 * BP, 10 * BP]
F_M_V1 = 10 * BP                                  # the v1 value, for the step-by-step comparison
Q_ACQ = 0.50                                      # probability an acquirer takes all deposits at closure (rule M)
ADV_DAYS = 7                                      # rule M: days the tail carries its advance of the assessment slice
ADV_RATE = R_FREE + S_B                           # rule M: carry rate on the advance [author assumption: r + s_b]
CLOSE_S, CLOSE_LGD = 0.10, 0.40                   # illustration of cash at closure (Section 4): failed share, LGD
Q_SET = [0.0, 0.25, 0.50, 0.75, 1.0]              # 0 = rule B only, 1 = rule M only
X_CLUSTER = 10                                    # memo: exhaustion at the payout of 10 base-weight members
STD_REF = ("gauss", cc.V8_N_STD["gauss"])         # reference design: 1% Gaussian conditional standard
STD_ALT = ("t", cc.V8_N_STD["t"])                 # disclosed alternative: 5% Student-t(5)
LP_SET = [0.0010, 0.0025, 0.0050, 0.0100]
LP_FIG = [0.0005, 0.0010, 0.0025, 0.0050, 0.0075, 0.0100, 0.0150]
MIX = [(0.60, 0.0015), (0.30, 0.0035), (0.10, 0.0075)]
MIX_SEED = 20261102
THETA_FIG = [0.01 * i for i in range(1, 11)]
REPL_SET = [1, 3, 5]                              # replenishment assessment spread over 1, 3 or 5 years
REPL_BASE = 3
CLUSTER_2023 = ["B", "B", "M"]                    # 2023: two bridge banks and one whole-bank acquisition [reported fact]
# --- public benchmarks, reported, not model numbers ------------------------------------------------------
MDIF_EXP = 3.45e6                                 # Massachusetts DIF 2025 net expenses
MDIF_ASSESS = 4.61e6                              # Massachusetts DIF 2025 assessments
MDIF_EXCESS = 21.92e9                             # insured excess deposits
ESIC_PREM = 8.81e6                                # Excess Share Insurance Corp 2025 premiums earned
ESIC_LIMITS = 8e9                                 # about $8bn of excess limits
# --- numerics -------------------------------------------------------------------------------------------
GU = 30_000
LGD_BUCKET = 0.002
EPS = cc.EPS
CHK_YEARS, CHK_CHUNK, CHK_SEED = 1_000_000, 50_000, 20261103
PATH_N, PATH_YEARS, PATH_SEED = 100_000, 10, 20261105
PATH_R0_V1 = 0.01                                 # v1 start, kept as a memo row
PATH_REPORT = [1, 5, 10]
DRAW_YEARS, DRAW_SEED = 400_000, 20261108
# --- the bank's side [author assumptions] -----------------------------------------------------------------
S_REP_SET = [20 * BP, 40 * BP, 60 * BP, 80 * BP]
WTP_CELLS = [(0.0, 0.0), (100 * BP, 0.01), (150 * BP, 0.05)]
ANNUITY = cc.V7_ANNUITY
ACC = (R_FREE + S_B) * D_YEARS
SG = np.arange(GU + 1) / GU


def adv_linked(lgd):
    return ADV_SHARE * (1.0 - np.asarray(lgd, dtype=float))


A_BASE = float(adv_linked(LGD))


def tiered_cap(liab):
    cap, lo = np.zeros_like(liab), 0.0
    for width, share in TIERS:
        cap += share * np.clip(liab - lo, 0.0, width)
        lo += width
    return np.minimum(cap, TIER_MAX)


# =============================================================================
# 2. MEMBER WEIGHTS
# =============================================================================
class Profile:
    """Covered-excess weights of the members on the grid (units of 1/GU), sorted largest first."""

    def __init__(self, kind, n, cap, sigma=SIZE_SIGMA, tier=True, demand=DEMAND, units=None, key=None):
        self.kind, self.n, self.cap, self.sigma, self.tier, self.demand = kind, n, cap, sigma, tier, demand
        self.n_tier = self.n_conc = 0
        self.cov_total = self.dem_total = None
        if units is not None:
            self.units = np.asarray(units, dtype=int)
        elif kind == "equal":
            self.units = np.full(n, GU // n, dtype=int)
        else:
            rng = np.random.default_rng(WEIGHT_SEED)
            x = rng.lognormal(0.0, sigma, n)
            half = math.log(SIZE_RANGE) / 2
            x = np.clip(x, math.exp(-half), math.exp(half))
            liab = LIAB_RATIO * ASSET_MIN * x * math.exp(half)
            dem = demand * liab
            cov = np.minimum(dem, tiered_cap(liab)) if tier else dem
            self.n_tier = int((cov < dem - 1e-6).sum())
            self.cov_total, self.dem_total = float(cov.sum()), float(dem.sum())
            w = cov / cov.sum()
            for _ in range(1000):
                over = w > cap + 1e-15
                if not over.any():
                    break
                ex = (w[over] - cap).sum()
                w[over] = cap
                free = w < cap - 1e-15
                w[free] += ex * w[free] / w[free].sum()
            self.n_conc = int((w >= cap - 1e-12).sum())
            raw = np.sort(w)[::-1] * GU
            u = np.floor(raw + 1e-9).astype(int)
            rem = GU - int(u.sum())
            order = np.argsort(-(raw - u), kind="stable")
            u[order[:rem]] += 1
            self.units = np.maximum(u, 1)
        self.n = self.units.size
        self.w = self.units / GU
        self.W = float(self.units.sum()) / GU
        self.key = key if key is not None else (kind, n, cap, sigma, tier, demand)
        self.largest, self.median = 0, self.n // 2
        self.n_eff = self.W ** 2 / float((self.w ** 2).sum())
        self.top5 = float(self.w[:5].sum())


_PROF = {}


def profile(kind="lognormal", n=N_BASE, cap=CAP_BASE, sigma=SIZE_SIGMA, tier=True, demand=DEMAND):
    k = (kind, n) + ((cap, sigma, tier, demand) if kind != "equal" else ())
    if k not in _PROF:
        _PROF[k] = Profile(kind, n, cap, sigma, tier, demand)
    return _PROF[k]


# =============================================================================
# 3. ENGINE
# =============================================================================
def subset_sums(units):
    """Q[k, s] = P(weight of a uniformly random k-subset of the names = s grid units), exact."""
    units = np.asarray(units, dtype=int)
    n, G = units.size, int(units.sum()) + 1
    C = np.zeros((n + 1, G))
    C[0, 0] = 1.0
    for i, u in enumerate(units):
        C[1:i + 2, u:] += C[0:i + 1, :G - u].copy()
    return C / C.sum(axis=1, keepdims=True)


_SUB = {}


def subsets(prof, excl=None):
    k = (prof.key, excl)
    if k not in _SUB:
        u = prof.units if excl is None else np.delete(prof.units, excl)
        _SUB[k] = subset_sums(u)
    return _SUB[k]


_CNT = {}


def counts(pd, rho, cop, n, cond=False, mode="fixed"):
    """Count distribution from the clearing-cost engine's pool() (exact quadrature), unconditional or given a reference name
    fails (the clearing-cost engine's ref_cond weights), grouped by state-dependent LGD bucket in the correlated mode."""
    key = (round(pd, 12), rho, cop, n, cond, mode)
    if key in _CNT:
        return _CNT[key]
    with cc._trim_cache():
        P = cc.pool(min(pd, 0.999), rho, "fixed", copula=cop, n_names=n)
        J = (P["w"] * P["p"])[:, None] * P["pmf_others"] if cond else P["joint"]
        J = J / J.sum()
        if mode == "fixed":
            out = (J.sum(axis=0)[None, :], None)
        else:
            lg = cc.lgd_of_z(P["z"], "corr")
            b = np.rint((lg - lg.min()) / LGD_BUCKET).astype(int)
            order = np.argsort(b, kind="stable")
            starts = np.r_[0, np.nonzero(np.diff(b[order]))[0] + 1]
            Jb = np.add.reduceat(J[order], starts, axis=0)
            nw = J.sum(axis=1)[order]
            lgd_b = np.add.reduceat(nw * lg[order], starts) / np.add.reduceat(nw, starts)
            keep = Jb.sum(axis=1) > 0
            out = (Jb[keep], lgd_b[keep])
    _CNT[key] = out
    return out


def dist(prof, pd, rho, cop, cond=None, mode="fixed", lgd=LGD):
    """Joint distribution D[b, s] of the LGD state b and the failed share S = s / GU."""
    Jb, lgd_b = counts(pd, rho, cop, prof.n, cond is not None, mode)
    D = np.zeros((Jb.shape[0], GU + 1))
    if cond is None:
        Q = subsets(prof)
        D[:, :Q.shape[1]] = Jb @ Q
    else:
        u = int(prof.units[cond])
        Q = subsets(prof, cond)
        D[:, u:u + Q.shape[1]] = Jb @ Q
    if mode == "fixed":
        lgd_b = np.array([lgd])
    lgd_b = np.asarray(lgd_b, dtype=float)
    return dict(D=D, lgd=lgd_b, a=adv_linked(lgd_b), W=prof.W)


def mix_dist(prof, cls, pds, rho, cop, cond=None, lgd=LGD):
    """Failed-share distribution with three risk classes (fixed LGD): subset-sum recursion within each class,
    mixed over the joint class counts given the factor, convolved in the frequency domain."""
    groups = []
    for c_ in range(len(pds)):
        idx = np.nonzero(cls == c_)[0]
        if cond is not None:
            idx = idx[idx != cond]
        groups.append(prof.units[idx])
    Qs = [subset_sums(g) for g in groups]
    L = 1 << int(math.ceil(math.log2(GU + 1)))
    FQ = [np.fft.rfft(q, L, axis=1) for q in Qs]
    if cop == "gauss":
        wn = cc._WZ5
        ps = [cc.ncdf((cc._ND.inv_cdf(pd) - math.sqrt(rho) * cc._Z5) / math.sqrt(1 - rho)) for pd in pds]
    else:
        ps = []
        for pd in pds:
            _, wn, p_, _ = cc._t_nodes(pd, rho)
            ps.append(p_)
    wt = wn * (ps[cls[cond]] if cond is not None else 1.0)
    wt = wt / wt.sum()
    B = [cc._binom_rows(p_, len(g)) for p_, g in zip(ps, groups)]
    n0, n1, n2 = (b.shape[1] for b in B)
    P3 = np.zeros((n0 * n1, n2))
    CH = 3000
    for s in range(0, wt.size, CH):
        e = slice(s, s + CH)
        M = (wt[e, None] * B[0][e])[:, :, None] * B[1][e][:, None, :]
        P3 += M.reshape(M.shape[0], -1).T @ B[2][e]
    P3 = P3.reshape(n0, n1, n2)
    tot = np.zeros(FQ[0].shape[1], dtype=complex)
    for k2 in range(n2):
        tot += FQ[2][k2] * (FQ[0] * (P3[:, :, k2] @ FQ[1])).sum(axis=0)
    d = np.clip(np.fft.irfft(tot, L), 0.0, None)
    D = np.zeros((1, GU + 1))
    u = 0 if cond is None else int(prof.units[cond])
    D[0, u:] = d[:GU + 1 - u]
    D /= D.sum()
    lg = np.array([lgd])
    return dict(D=D, lgd=lg, a=adv_linked(lg), W=prof.W)


def stack(Dd, settle, theta, mpi, T, full=False, adv=None):
    """Layer cash and losses over the distribution Dd under one settlement rule.
    'M': cash = LGD x covered excess at closure, no later dividend. 'B': cash = (1 - a) x covered excess on day
    seven, the layers own the claim. 'gross': par at T+0 (the clearing-cost engine's reference). The mutual pays first from the
    reserve theta, then from a special assessment of up to mpi x (W - S) collectable from survivors; the tail pays
    the next T; the rest is unpaid (public tail).
    Timing under rule M: the assessment is collected within the week, after closure, so it is not cash at closure.
    The tail advances the assessment slice at closure, up to its advance capacity adv (default mpi x W, the whole
    collectable call), and is repaid from the assessment when collected; cash at closure = reserve + tail advance +
    tail layer. With adv below the slice (a tail thinner than the call, or no tail) the rest of the slice is not cash
    at closure and counts as unpaid. Under rule B the assessment is assumed collectable by day seven."""
    D, lgd_b, a_b, W = Dd["D"], Dd["lgd"], Dd["a"], Dd["W"]
    adv = mpi * W if adv is None else adv
    S = SG[None, :]
    if settle == "M":
        c, lr, ar = lgd_b.copy(), np.ones_like(lgd_b), np.zeros_like(lgd_b)
    elif settle == "B":
        c = 1.0 - a_b
        lr, ar = lgd_b / c, np.clip(1.0 - a_b - lgd_b, 0.0, None) / c
    else:
        c = np.ones_like(a_b)
        lr, ar = lgd_b, np.clip(1.0 - a_b - lgd_b, 0.0, None)
    C = c[:, None] * S
    Rv = theta + mpi * (W - S)
    over = C - Rv
    tail = np.clip(over, 0.0, T)
    if settle == "M":
        slice_ = np.minimum(np.clip(C - theta, 0.0, None), mpi * (W - S))   # assessment slice the call must fund
        advance = np.minimum(slice_, adv)                                    # advanced by the tail at closure
        mut = np.minimum(C, theta) + advance                                 # reserve + slice (repaid by the call)
        unp = np.clip(C - mut - tail, 0.0, None)
    else:
        advance = np.zeros_like(C)
        mut = np.minimum(C, Rv)
        unp = np.clip(over - T, 0.0, None)
    lr, ar = lr[:, None], ar[:, None]
    o = dict(el_mut=float((D * mut * lr).sum()), acc_mut=float((D * mut * ar).sum()) * ACC,
             el_tail=float((D * tail * lr).sum()), acc_tail=float((D * tail * ar).sum()) * ACC,
             el_pub=float((D * unp * lr).sum()), pay_tail=float((D * tail).sum()), e_S=float((D * S).sum()),
             e_C=float((D * C).sum()), e_adv=float((D * advance).sum()))
    if full:
        o["p_sa"] = float((D * (C > theta + EPS)).sum())
        o["p_tail"] = float((D * (over > EPS)).sum())
        o["p_exh"] = float((D * (unp > EPS)).sum())
        o["p_adv"] = float((D * (advance > EPS)).sum())
        o["max_tail_cash"] = float(np.where(D > 0, advance + tail, 0.0).max())
        u = np.where(C > 0, unp / np.where(C > 0, C, 1.0), 0.0)
        o["e_u"] = float((D * u).sum())
        o["e_loss"] = float((D * u * lgd_b[:, None]).sum())
        o["sev"] = o["e_u"] / o["p_exh"] if o["p_exh"] > 0 else 0.0
    return o


def stackq(Dd, q, theta, mpi, T, full=False, adv=None):
    """Mixed settlement: rule M with probability q (common to the year's failures), else rule B."""
    if q <= 0:
        return stack(Dd, "B", theta, mpi, T, full, adv)
    if q >= 1:
        return stack(Dd, "M", theta, mpi, T, full, adv)
    om, ob = stack(Dd, "M", theta, mpi, T, full, adv), stack(Dd, "B", theta, mpi, T, full, adv)
    o = {k: q * om[k] + (1 - q) * ob[k] for k in om}
    if full:
        o["max_tail_cash"] = max(om["max_tail_cash"], ob["max_tail_cash"])
    if full:
        o["sev"] = o["e_u"] / o["p_exh"] if o["p_exh"] > 0 else 0.0
    return o


def adv_capacity(X, theta, mpi, W, q):
    """The tail's advance capacity under rule M: the whole collectable call mpi x W when the tail reaches above A,
    else what the tail holds above the reserve; none when rule M never applies (q = 0)."""
    return 0.0 if q <= 0 else min(max(X - theta, 0.0), mpi * W)


def solve(Dp, Dq, q=Q_ACQ, theta=THETA_M, m=M_SA, X=0.0, opp=OPP, f_m=F_M, s_lock=S_LOCK, f_tail=TAIL_FRIC):
    """Fixed point in the annual assessment pi (the special-assessment capacity is m x pi). The tail's funded
    commitment is its layer T plus its rule-M advance capacity; lock-up and frictions scale with the commitment, and
    the advance carries ADV_RATE for ADV_DAYS days (expectation under Q, rule M only)."""
    pi = 20 * BP
    W = Dp["W"]
    for _ in range(300):
        A = theta + m * pi
        T = max(X - A, 0.0)
        adv = adv_capacity(X, theta, m * pi, W, q)
        sp, sq = stackq(Dp, q, theta, m * pi, T, adv=adv), stackq(Dq, q, theta, m * pi, T, adv=adv)
        commit = T + adv
        parts = dict(el_mut=sp["el_mut"], acc_mut=sp["acc_mut"], carry=theta * opp, f_m=f_m,
                     el_tail=sq["el_tail"], acc_tail=sq["acc_tail"], lock=s_lock * commit, f_tail=f_tail * commit,
                     adv_carry=sq["e_adv"] * ADV_RATE * ADV_DAYS / 365.0)
        parts["mutual"] = parts["el_mut"] + parts["acc_mut"] + parts["carry"] + parts["f_m"]
        parts["tail"] = parts["el_tail"] + parts["acc_tail"] + parts["lock"] + parts["f_tail"] + parts["adv_carry"]
        new = parts["mutual"] + parts["tail"]
        if abs(new - pi) < 1e-14:
            pi = new
            break
        pi = new
    A = theta + m * pi
    T = max(X - A, 0.0)
    adv = adv_capacity(X, theta, m * pi, W, q)
    return dict(pi=pi, A=A, X=X, T=T, adv=adv, commit=T + adv, mpi=m * pi, theta=theta, q=q, el_pub_p=sp["el_pub"],
                el_pub_q=sq["el_pub"], e_C=sp["e_C"], e_adv_q=sq["e_adv"], **parts)


def price_D(prof, pd=LAMBDA_P, rho=RHO_PRICE, cop="gauss", lgd=LGD, mu=MU):
    return dist(prof, pd, rho, cop, lgd=lgd), dist(prof, min(mu * pd, 0.999), rho, cop, lgd=lgd)


def price(prof=None, pd=LAMBDA_P, rho=RHO_PRICE, cop="gauss", lgd=LGD, theta=THETA_M, m=M_SA, X=0.0, q=Q_ACQ,
          opp=OPP, f_m=F_M, s_lock=S_LOCK, mu=MU, mix=None, f_tail=TAIL_FRIC):
    prof = profile() if prof is None else prof
    Dp, Dq = price_D(prof, pd, rho, cop, lgd, mu) if mix is None else (mix["P"][cop], mix["Q"][cop])
    return solve(Dp, Dq, q, theta, m, X, opp, f_m, s_lock, f_tail)


def reliab(Dc, Du, d, q=None):
    q = d["q"] if q is None else q
    adv = d["adv"] if q == d["q"] else adv_capacity(d["X"], d["theta"], d["mpi"], Dc["W"], q)
    s = stackq(Dc, q, d["theta"], d["mpi"], d["T"], full=True, adv=adv)
    su = stackq(Du, q, d["theta"], d["mpi"], d["T"], full=True, adv=adv)
    return dict(res=1 - s["p_sa"], sa=s["p_sa"] - s["p_tail"], tail=s["p_tail"] - s["p_exh"], short=s["p_exh"],
                full=1 - s["p_exh"], sev=s["sev"], e_u=s["e_u"], e_loss=s["e_loss"], u_tail=su["p_tail"],
                u_exh=su["p_exh"], u_sa=su["p_sa"], p_adv=s["p_adv"], max_tail_cash=s["max_tail_cash"])


def iso_x(cop, std, q=Q_ACQ, prof=None, f_m=F_M, rho=RHO_FAIL):
    """Smallest X (rounded up to 0.1%) meeting a conditional standard, median member, state-dependent LGD."""
    prof = profile() if prof is None else prof
    Dc = dist(prof, LAMBDA_P, rho, cop, prof.median, "corr")
    Du = dist(prof, LAMBDA_P, rho, cop, None, "corr")
    Dp, Dq = price_D(prof)
    des = lambda X: solve(Dp, Dq, q, X=X, f_m=f_m)
    f_ = lambda X: reliab(Dc, Du, des(X), q)["short"]
    lo, hi = 0.0, 1.0
    if f_(hi) > std:
        return None
    while hi - lo > 2e-5:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f_(mid) > std else (lo, mid)
    X = math.ceil(hi * 1e3 - 1e-9) / 1e3
    d = des(X)
    return dict(X=X, d=d, rel=reliab(Dc, Du, d, q), bw=X, prof=prof)


# =============================================================================
# 4. PARITY CHECK AGAINST THE CLEARING-COST ENGINE (equal weights, N 50, all-funded 20% buffer, no mutual)
# =============================================================================
def _cc_printed():
    """Read the clearing-cost engine's printed reference numbers from its results file (not from its code)."""
    txt = CC_RESULTS.read_text(encoding="utf-8")
    m36 = re.search(r"## 36\..*?\| \*\*c\*\*\* \| \*\*([\d.]+)\*\*", txt, re.S)
    row = re.search(r"## 38\..*?\| 20% \(10\) \| ([\d.]+)% \| ([\d.]+)% \| ([\d.]+)% \| ([\d.]+)% \| ([\d.]+)% \| "
                    r"([\d.]+)% \| ([\d.]+)% \| ([\d.]+)% \|", txt, re.S)
    net = re.search(r"\| Par less the advance dividend, at day 7 \|[^|]*\|[^|]*\| 20% \| ([\d.]+) \| ([\d.]+)% \| "
                    r"([\d.]+)% \| ([\d.]+)% \|", txt)
    if not (m36 and row and net):
        raise RuntimeError("could not read the clearing-cost reference rows from model/results_clearing_cost.md")
    g = [row.group(i) for i in range(1, 9)]
    return dict(price=m36.group(1), gauss=g[:4], t=g[4:], net=[net.group(i) for i in range(1, 5)])


def _within(mine_pct, printed):
    nd = len(printed.split(".")[1]) if "." in printed else 0
    return abs(mine_pct - float(printed)) <= 0.5 * 10 ** -nd + 1e-9


CC_PRINTED = _cc_printed()
P50 = profile("equal", 50)
_par_q = dist(P50, MU * LAMBDA_P, RHO_PRICE, "gauss")
_par_s = stack(_par_q, "gross", 0.0, 0.0, CC_CAP)
parity_price = dict(layer=_par_s["el_tail"] + _par_s["acc_tail"] + (S_LOCK + TAIL_FRIC) * CC_CAP)
parity_price["full"] = parity_price["layer"] + _par_s["el_pub"] + float(
    (_par_q["D"] * np.clip(SG - CC_CAP, 0, None)[None, :]).sum()) * (1 - ADV - LGD) * ACC
parity_price["cc_code"] = cc.REF8
parity_price["ok"] = _within(parity_price["full"] / BP, CC_PRINTED["price"]) and _within(parity_price["layer"] / BP, CC_PRINTED["price"])
parity_rel = {}
for cop, _ in COPULAS:
    Dc = dist(P50, LAMBDA_P, RHO_FAIL, cop, cond=0, mode="corr")
    g = stack(Dc, "gross", 0.0, 0.0, CC_CAP, full=True)
    nB = stack(Dc, "B", 0.0, 0.0, CC_CAP, full=True)
    mine = [g["p_exh"] * 100, g["sev"] * 100, g["e_u"] * 100, g["e_loss"] * 100]
    printed = CC_PRINTED["gauss"] if cop == "gauss" else CC_PRINTED["t"]
    code = cc.rel8[(cop, LAMBDA_P, RHO_FAIL, CC_CAP)]
    parity_rel[cop] = dict(mine=mine, printed=printed, code=[code["sf"] * 100, code["sev"] * 100, code["unpaid"] * 100,
                                                             code["loss"] * 100],
                           ok=all(_within(a, b) for a, b in zip(mine, printed)), net=nB, net_code=cc.unb8[(cop, "net")])
net_print = dict(gauss=CC_PRINTED["net"][1], t=CC_PRINTED["net"][2], t_loss=CC_PRINTED["net"][3])
parity_net_ok = (_within(parity_rel["gauss"]["net"]["p_exh"] * 100, net_print["gauss"])
                 and _within(parity_rel["t"]["net"]["p_exh"] * 100, net_print["t"])
                 and _within(parity_rel["t"]["net"]["e_loss"] * 100, net_print["t_loss"]))
PARITY_OK = parity_price["ok"] and all(v["ok"] for v in parity_rel.values()) and parity_net_ok
del _par_q

# =============================================================================
# 5. THE REFERENCE DESIGN, THE ALTERNATIVE, AND THE STEP FROM v1
# =============================================================================
PB = profile()                                     # lognormal, N 150, tiered cap then 5% cap
PB_NT = profile(tier=False)                        # v1 weights (no tiered cap)
PE = profile("equal", N_BASE)
ISO_REF = iso_x(*STD_REF)
ISO_ALT = iso_x(*STD_ALT)
X_REF, X_ALT = ISO_REF["X"], ISO_ALT["X"]
DESIGNS = [("ref", "Reference: X for 1% Gaussian", X_REF), ("alt", "Alternative: X for 5% Student-t(5)", X_ALT)]
base = {k: price(X=X) for k, _, X in DESIGNS}
base_B = {k: price(X=X, q=0.0) for k, _, X in DESIGNS}          # rule B only, same X (comparison)
base_eq = {k: price(PE, X=X) for k, _, X in DESIGNS}
memo_c10 = price(X=X_CLUSTER / N_BASE * (1 - A_BASE))            # memo: X at 10 base-weight members
MDIF_EXP_BP, MDIF_BP, ESIC_BP = MDIF_EXP / MDIF_EXCESS, MDIF_ASSESS / MDIF_EXCESS, ESIC_PREM / ESIC_LIMITS
CC_POOL = cc.base["Regional mutual pool"]

# step by step from v1 (each step re-sizes X to the 1% Gaussian standard)
_v1 = iso_x(*STD_REF, q=0.0, prof=PB_NT, f_m=F_M_V1)
_sA = iso_x(*STD_REF, q=0.0, prof=PB_NT, f_m=F_M)
_sT = iso_x(*STD_REF, q=0.0, prof=PB, f_m=F_M)
steps = [("v1: f_m 10 bps, rule B, no tiered cap (v1's Gaussian 1% design)", _v1),
         ("A: mutual frictions 5 bps", _sA),
         ("B: reserve paid in at entry (price already assumes the reserve at target)", _sA),
         ("Tiered per-member cap applied before the 5% cap", _sT),
         ("D: mixed settlement, q_acq 0.5 (= v2 reference design)", ISO_REF)]

# iso designs by q_acq
iso_q = {}
for q in Q_SET:
    for cop, std in (STD_REF, STD_ALT):
        iso_q[(q, cop)] = ISO_REF if (q == Q_ACQ and cop == "gauss") else ISO_ALT if (q == Q_ACQ and cop == "t") \
            else iso_x(cop, std, q=q)

# layer geometry
def members_to_reach(prof, amount, c=1 - A_BASE):
    cum = np.cumsum(prof.w * c)
    k = int(np.searchsorted(cum, amount - EPS) + 1)
    return k if k <= prof.n else None


PER_BW = {"M": (1.0 / PB.n) * LGD, "B": (1.0 / PB.n) * (1 - A_BASE)}
geo = {}
for k, _, _ in DESIGNS + [("c10", "", 0)]:
    b = base[k] if k != "c10" else memo_c10
    geo[k] = dict(A=b["A"], X=b["X"], T=b["T"], commit=b["commit"], theta=b["theta"], mpi=b["mpi"],
                  bw={r: (b["theta"] / PER_BW[r], b["A"] / PER_BW[r], b["X"] / PER_BW[r]) for r in ("M", "B")},
                  top={r: tuple(members_to_reach(PB, v, LGD if r == "M" else 1 - A_BASE) for v in (b["theta"], b["A"], b["X"]))
                       for r in ("M", "B")})

# sweeps (X fixed at each design's contract value)
sweeps = []
for lp in LP_SET:
    sweeps.append(("lambda_P", f"lambda_P {lp * 100:.2f}%", dict(pd=lp)))
for lg in LGD_SET:
    sweeps.append(("LGD", f"LGD {lg:.0%} (a {float(adv_linked(lg)):.1%})", dict(lgd=lg)))
for rho in RHO_SET:
    sweeps.append(("rho", f"rho {rho:.2f}", dict(rho=rho)))
for cop, nm in COPULAS:
    sweeps.append(("copula", nm, dict(cop=cop)))
for q in Q_SET:
    sweeps.append(("q_acq", "rule B only" if q == 0 else "rule M only" if q == 1 else f"q_acq {q:.2f}", dict(q=q)))
for n_ in N_SET:
    sweeps.append(("N", f"N {n_}", dict(prof=profile(n=n_))))
for cp in CAP_SET:
    sweeps.append(("cap", f"concentration cap {cp:.0%}", dict(prof=profile(cap=cp))))
for dm in DEMAND_SET:
    sweeps.append(("demand", f"covered excess sought {dm:.0%} of liabilities", dict(prof=profile(demand=dm))))
sweeps.append(("tier", "no tiered cap", dict(prof=PB_NT)))
for sg in SIGMA_SET:
    sweeps.append(("sigma", f"size dispersion sigma {sg:.1f}", dict(prof=profile(sigma=sg))))
sweeps.append(("weights", f"equal weights, N {N_BASE}", dict(prof=PE)))
for th in THETA_SET:
    sweeps.append(("theta_m", f"theta_m {th:.0%}", dict(theta=th)))
for m_ in M_SET:
    sweeps.append(("m", f"m {m_}", dict(m=m_)))
for o_ in OPP_SET:
    sweeps.append(("opp", f"reserve opportunity cost {o_ / BP:.0f} bps", dict(opp=o_)))
for f_ in F_M_SET:
    sweeps.append(("f_m", f"mutual frictions {f_ / BP:.0f} bps", dict(f_m=f_)))
for sl in S_LOCK_SET:
    sweeps.append(("s_lock", f"lock-up premium {sl / BP:.0f} bps", dict(s_lock=sl)))
for tf in TAIL_FRIC_SET:
    sweeps.append(("f_tail", f"tail frictions {tf / BP:.1f} bps per unit of thickness", dict(f_tail=tf)))
sweep_res = [(g, lab, {k: price(**{**kw, "X": X}) for k, _, X in DESIGNS}) for g, lab, kw in sweeps]
tornado = {}
for g, lab, r in sweep_res:
    if g in ("weights", "tier"):
        continue
    for k, _, _ in DESIGNS:
        lo, hi = tornado.get((g, k), (9.0, -9.0))
        tornado[(g, k)] = (min(lo, r[k]["pi"]), max(hi, r[k]["pi"]))

lp_curve = {(cop, k): [price(pd=lp, cop=cop, X=X)["pi"] for lp in LP_FIG] for cop, _ in COPULAS for k, _, X in DESIGNS}
lp_cc = [cc.pool_price(**{**cc.V8_REF, "pd": lp})["c_star"] for lp in LP_FIG]

# =============================================================================
# 6. RISK-CLASS MIX (fixed LGD)
# =============================================================================
_rng_mix = np.random.default_rng(MIX_SEED)
MIX_CLS = np.empty(PB.n, dtype=int)
_perm = _rng_mix.permutation(PB.n)
_cuts = np.cumsum([int(round(sh * PB.n)) for sh, _ in MIX])
for c_, (lo_, hi_) in enumerate(zip(np.r_[0, _cuts[:-1]], _cuts)):
    MIX_CLS[_perm[lo_:hi_]] = c_
MIX_PDS = [pd for _, pd in MIX]
MIX_AVG_COUNT = sum(sh * pd for sh, pd in MIX)
MIX_AVG_COV = float(sum(PB.w[MIX_CLS == c_].sum() * pd for c_, pd in enumerate(MIX_PDS)))
MIX_COV = [float(PB.w[MIX_CLS == c_].sum()) for c_ in range(len(MIX))]
mixD = {"P": {}, "Q": {}}
for cop, _ in COPULAS:
    mixD["P"][cop] = mix_dist(PB, MIX_CLS, MIX_PDS, RHO_PRICE, cop)
    mixD["Q"][cop] = mix_dist(PB, MIX_CLS, [MU * p for p in MIX_PDS], RHO_PRICE, cop)
mix_price = {(cop, k): price(cop=cop, X=X, mix=mixD) for cop, _ in COPULAS for k, _, X in DESIGNS}


def class_rates(r, avg):
    risk = r["el_mut"] + r["acc_mut"] + r["el_tail"] + r["acc_tail"]
    fixed = r["carry"] + r["f_m"] + r["lock"] + r["f_tail"] + r["adv_carry"]
    return [risk * pd / avg + fixed for pd in MIX_PDS]


_mx_u = mix_dist(PB, MIX_CLS, [LAMBDA_P] * 3, RHO_FAIL, "gauss")
_ex_u = dist(PB, LAMBDA_P, RHO_FAIL, "gauss")
mix_check = {}
for nm, f_ in (("P(S > 2%)", lambda D: float(D["D"][0, SG > 0.02 + EPS].sum())),
               ("P(S > 6.67%)", lambda D: float(D["D"][0, SG > 10 / 150 + EPS].sum())),
               ("E[S]", lambda D: float((D["D"][0] * SG).sum())),
               ("E[min(S, 6.67%)]", lambda D: float((D["D"][0] * np.minimum(SG, 10 / 150)).sum()))):
    mix_check[nm] = (f_(_mx_u), f_(_ex_u))
MIX_CHECK_MAX = max(abs(a - b) / max(abs(b), 1e-300) for a, b in mix_check.values())
rel_mix = {}
for cop, _ in COPULAS:
    Du = mix_dist(PB, MIX_CLS, MIX_PDS, RHO_FAIL, cop)
    for who, idx in (("median", PB.median), ("largest", PB.largest)):
        Dc = mix_dist(PB, MIX_CLS, MIX_PDS, RHO_FAIL, cop, cond=idx)
        for k, _, _ in DESIGNS:
            rel_mix[(cop, who, k)] = reliab(Dc, Du, mix_price[("gauss", k)])
del _mx_u, _ex_u

# =============================================================================
# 7. RELIABILITY IN THE YEAR A GIVEN MEMBER FAILS (P measure, state-dependent LGD and dividend)
# =============================================================================
_DC = {}
rel = {}
for cop, _ in COPULAS:
    for rho in (RHO_FAIL, RHO_PRICE):
        _DC[("u", cop, rho)] = dist(PB, LAMBDA_P, rho, cop, None, "corr")
        for who, idx in (("median", PB.median), ("largest", PB.largest)):
            _DC[(who, cop, rho)] = dist(PB, LAMBDA_P, rho, cop, idx, "corr")
            for k, _, _ in DESIGNS:
                rel[(cop, rho, who, k)] = reliab(_DC[(who, cop, rho)], _DC[("u", cop, rho)], base[k])
                rel[(cop, rho, who, k + "_B")] = reliab(_DC[(who, cop, rho)], _DC[("u", cop, rho)], base_B[k])
            rel[(cop, rho, who, "c10")] = reliab(_DC[(who, cop, rho)], _DC[("u", cop, rho)], memo_c10)
rel_eq, rel_fixed = {}, {}
for cop, _ in COPULAS:
    _e = (dist(PE, LAMBDA_P, RHO_FAIL, cop, PE.median, "corr"), dist(PE, LAMBDA_P, RHO_FAIL, cop, None, "corr"))
    _f = (dist(PB, LAMBDA_P, RHO_FAIL, cop, PB.median), dist(PB, LAMBDA_P, RHO_FAIL, cop))
    for k, _, _ in DESIGNS:
        rel_eq[(cop, k)] = reliab(*_e, base_eq[k])
        rel_fixed[(cop, k)] = reliab(*_f, base[k])
    del _e, _f
rel_q = {(q, cop): reliab(_DC[("median", cop, RHO_FAIL)], _DC[("u", cop, RHO_FAIL)], price(X=X_REF, q=q))
         for q in Q_SET for cop, _ in COPULAS}


def no_tail(d):
    return {**d, "T": 0.0}


rel_curve = {}
_Dp0, _Dq0 = price_D(PB)
for cop, _ in COPULAS:
    Dc, Du = _DC[("median", cop, RHO_FAIL)], _DC[("u", cop, RHO_FAIL)]
    for m_ in M_SET:
        rel_curve[(cop, m_)] = []
        for th in THETA_FIG:
            d_ = solve(_Dp0, _Dq0, theta=th, m=m_, X=0.0)
            rel_curve[(cop, m_)].append(stackq(Dc, Q_ACQ, th, d_["mpi"], 0.0, full=True, adv=0.0)["p_exh"])
stack_line = {(cop, k): rel[(cop, RHO_FAIL, "median", k)]["short"] for cop, _ in COPULAS for k, _, _ in DESIGNS}

# cash need per failure by LGD state, by rule (figure M08)
LGD_GRID = np.linspace(0.15, 0.40, 26)
cash_rule = {"M": LGD_GRID.copy(), "B": 1 - adv_linked(LGD_GRID)}

# =============================================================================
# 8. SINGLE-MEMBER TEST
# =============================================================================
SINGLE_CASES = [("rule M, LGD 25%", "M", LGD), ("rule M, LGD 40%", "M", 0.40),
                ("rule B, LGD 25% (a 50%)", "B", LGD), ("rule B, LGD 40% (a 40%)", "B", 0.40),
                ("rule B, dividend not paid by day seven (par)", "par", 0.40)]


def cash_per(rule, lg):
    return lg if rule == "M" else (1 - float(adv_linked(lg))) if rule == "B" else 1.0


single = []
for cp in CAP_SET:
    wmax = float(profile(cap=cp).w[0])
    whos = [("member at the cap", cp)] + ([("largest drawn member", wmax)] if wmax < cp - 1e-12 else [])
    for who, wv in whos:
        for case, rule, lg_ in SINGLE_CASES:
            pay = wv * cash_per(rule, lg_)
            single.append(dict(cap=cp, who=who, wmax=wv, case=case, pay=pay, loss=wv * lg_,
                               ok={th: pay <= th + EPS for th in THETA_SET}))
single_prob = {(cop, rho): stackq(_DC[("largest", cop, rho)], Q_ACQ, THETA_M, 0.0, 0.0, full=True)["p_sa"]
               for cop, _ in COPULAS for rho in (RHO_FAIL, RHO_PRICE)}

# =============================================================================
# 9. MONTE CARLO: ONE-YEAR CHECK, SETTLEMENT-DRAW SENSITIVITY
# =============================================================================
def sim_S(prof, pd, rho, cop, n_years, seed, chunk, force=None):
    """Failed share and common factor per simulated year (the clearing-cost engine's latent-variable design, cc._mc).
    force = index of a member forced to fail; the year then carries the weight P(that member fails | factor)."""
    rng = np.random.default_rng(seed)
    thr = cc._ND.inv_cdf(pd) if cop == "gauss" else cc._t_nodes(pd, rho)[3]
    S_, Z_, W_, F_ = [], [], [], []
    done = 0
    while done < n_years:
        m = min(chunk, n_years - done)
        z = rng.standard_normal(m)
        x = math.sqrt(rho) * z[:, None] + math.sqrt(1 - rho) * rng.standard_normal((m, prof.n))
        sc = np.sqrt(NU / rng.chisquare(NU, m)) if cop == "t" else np.ones(m)
        fail = (x * sc[:, None]) < thr
        if force is not None:
            fail[:, force] = True
            W_.append(cc.ncdf((thr / sc - math.sqrt(rho) * z) / math.sqrt(1 - rho)))
        S_.append(fail.astype(float) @ prof.w)
        F_.append(fail if force is not None else None)
        Z_.append(z)
        done += m
    out = dict(S=np.concatenate(S_), z=np.concatenate(Z_))
    if force is not None:
        out["wt"] = np.concatenate(W_)
        out["fail"] = np.concatenate(F_)
    return out


def mc_rows(cop, d):
    sim = sim_S(PB, LAMBDA_P, RHO_FAIL, cop, CHK_YEARS, CHK_SEED + (cop == "t"), CHK_CHUNK)
    S_, z_ = sim["S"], sim["z"]
    rng = np.random.default_rng(CHK_SEED + 10 + (cop == "t"))
    isM = rng.random(S_.size) < Q_ACQ
    lg = cc.lgd_of_z(z_, "corr")
    C_ = S_ * np.where(isM, lg, 1 - adv_linked(lg))
    Rv = d["theta"] + d["mpi"] * (1 - S_)
    ex = stackq(_DC[("u", cop, RHO_FAIL)], Q_ACQ, d["theta"], d["mpi"], d["T"], full=True, adv=d["adv"])
    rows = []
    for nm, x, exact in (("P(reserve alone does not pay)", (C_ > d["theta"] + EPS).astype(float), ex["p_sa"]),
                         ("P(mutual's resources exhausted)", (C_ > Rv + EPS).astype(float), ex["p_tail"]),
                         ("E[tail payout] (% of covered excess)", np.clip(C_ - Rv, 0, d["T"]), ex["pay_tail"]),
                         ("E[cash at the trigger] (% of covered excess)", C_, ex["e_C"])):
        mean, se = float(x.mean()), float(x.std(ddof=1) / math.sqrt(x.size))
        rows.append(dict(name=nm, mc=mean, se=se, exact=exact, z=(mean - exact) / se if se > 0 else 0.0))
    return rows


mc_chk = {cop: mc_rows(cop, base["ref"]) for cop, _ in COPULAS}
MC_CHECK_OK = all(abs(r["z"]) <= 3.0 for v in mc_chk.values() for r in v)


def draw_sensitivity(cop, d):
    """Conditional shortfall given the median member fails, with the rule drawn once a year (the engine's
    convention) and independently for each failure, on the same simulated years (importance weights)."""
    sim = sim_S(PB, LAMBDA_P, RHO_FAIL, cop, DRAW_YEARS, DRAW_SEED + (cop == "t"), CHK_CHUNK, force=PB.median)
    rng = np.random.default_rng(DRAW_SEED + 20 + (cop == "t"))
    wt, fail, z = sim["wt"], sim["fail"], sim["z"]
    lg = cc.lgd_of_z(z, "corr")
    cB = 1 - adv_linked(lg)
    S_ = sim["S"]
    Rv = d["theta"] + d["mpi"] * (1 - S_) + d["T"]
    yearM = rng.random(S_.size) < Q_ACQ
    C_year = S_ * np.where(yearM, lg, cB)
    typM = rng.random(fail.shape) < Q_ACQ
    SM = (fail & typM).astype(float) @ PB.w
    C_ind = SM * lg + (S_ - SM) * cB
    out = {}
    for nm, C_ in (("year", C_year), ("each", C_ind)):
        x = (C_ > Rv + EPS).astype(float)
        mean = float((wt * x).sum() / wt.sum())
        ess = float(wt.sum() ** 2 / (wt ** 2).sum())
        out[nm] = dict(p=mean, se=math.sqrt(max(mean * (1 - mean), 1e-300) / ess))
    out["exact"] = rel[(cop, RHO_FAIL, "median", "ref")]["short"]
    return out


draw_sens = {cop: draw_sensitivity(cop, base["ref"]) for cop, _ in COPULAS}

# =============================================================================
# 10. REPLENISHMENT: TEN-YEAR PATHS FROM TARGET, AND YEAR 2 AFTER A 2023-LIKE CLUSTER
# =============================================================================
def reserve_path(sim, isM, d, repl=REPL_BASE, theta0=THETA_M, replenish=True):
    """Ten years of the mutual. Each year: day-seven or closure payouts from the reserve, then the special
    assessment (up to m x assessment x survivors), then the tail up to T; T-bill income; the expected-loss and
    access parts of the assessment kept as income; receivership recoveries on rule-B claims after D years. At
    year end a reserve below target is restored first by a special assessment up to the unused part of the year's
    cap, then by a replenishment assessment spread over `repl` annual instalments (the first collected at once).
    Reserve above target is rebated."""
    S_all, z_all = sim["S"], sim["z"]
    paths, years = S_all.shape
    theta = d["theta"]
    R = np.full(paths, theta0)
    lag = int(round(D_YEARS))
    rec = np.zeros((paths, years + lag + 1))
    sched = np.zeros((paths, years + max(REPL_SET) + 2))
    Rt, below, short_start, extra, rebate = [R.copy()], [], [], [], []
    ever = {k: np.zeros(paths, bool) for k in ("sa", "tail", "exh", "repl", "tail_short")}
    for t in range(years):
        S, z, m_ = S_all[:, t], z_all[:, t], isM[:, t]
        lg = cc.lgd_of_z(z, "corr")
        a_ = adv_linked(lg)
        C = S * np.where(m_, lg, 1 - a_)
        st = R < theta - 1e-12
        short_start.append(st.mean())
        payR = np.minimum(C, R)
        C1 = C - payR
        capv = d["mpi"] * (1 - S)
        sa = np.minimum(C1, capv)
        C2 = C1 - sa
        tl = np.minimum(C2, d["T"])
        C3 = C2 - tl
        ever["sa"] |= sa > EPS
        ever["tail"] |= tl > EPS
        ever["exh"] |= C3 > EPS
        ever["tail_short"] |= (tl > EPS) & st
        R = (R - payR) * (1 + R_FREE) + d["el_mut"] + d["acc_mut"]
        rec[:, t + lag] += np.where(m_, 0.0, (payR + sa) * np.clip(1 - a_ - lg, 0, None) / (1 - a_))
        R = R + rec[:, t]
        ex_t = np.zeros(paths)
        if replenish:
            gap = np.clip(theta - R - sched[:, t:].sum(axis=1), 0, None)
            sa_r = np.minimum(gap, capv - sa)
            R = R + sa_r
            gap = gap - sa_r
            sched[:, t:t + repl] += (gap / repl)[:, None]
            R = R + sched[:, t]
            ex_t = sa_r + sched[:, t]
            ever["repl"] |= ex_t > EPS
        extra.append(ex_t.mean())
        rebate.append(float(np.clip(R - theta, 0, None).mean()))
        R = np.minimum(R, theta)
        below.append(float((R < theta - 1e-9).mean()))
        Rt.append(R.copy())
    Rt = np.array(Rt)
    return dict(q={y: np.percentile(Rt[y], [5, 50, 95]) for y in PATH_REPORT},
                fan=np.percentile(Rt, [5, 25, 50, 75, 95], axis=1), below=below,
                short_start=float(np.mean(short_start)), extra=float(np.mean(extra)), rebate=float(np.mean(rebate)),
                ever={k: float(v.mean()) for k, v in ever.items()})


PATH_RUNS = [("gauss", RHO_PRICE, "Gaussian, rho 0.20 (base)"), ("gauss", RHO_FAIL, "Gaussian, rho 0.30"),
             ("t", RHO_PRICE, "Student-t(5), rho 0.20")]
paths = {}
for i_, (cop, rho, lab) in enumerate(PATH_RUNS):
    sim = sim_S(PB, LAMBDA_P, rho, cop, PATH_N * PATH_YEARS, PATH_SEED + i_, 200_000)
    sim = {k: v.reshape(PATH_N, PATH_YEARS) for k, v in sim.items()}
    isM = np.random.default_rng(PATH_SEED + 50 + i_).random((PATH_N, PATH_YEARS)) < Q_ACQ
    for rp in REPL_SET:
        paths[(cop, rho, rp)] = reserve_path(sim, isM, base["ref"], repl=rp)
    if (cop, rho) == ("gauss", RHO_PRICE):
        paths["alt"] = reserve_path(sim, isM, base["alt"], repl=REPL_BASE)
        paths["v1start"] = reserve_path(sim, isM, base["ref"], theta0=PATH_R0_V1, replenish=False)
    del sim, isM

# Year 2 after a 2023-like cluster of three base-weight members (two bridge banks under rule B, one acquisition
# under rule M, base LGD), with the reserve not yet restored. Survivors keep their original weights.
_drop = np.argsort(np.abs(PB.w - 1.0 / PB.n), kind="stable")[:len(CLUSTER_2023)]
Y1_PAY = float(sum(PB.w[j] * cash_per(r, LGD) for j, r in zip(_drop, CLUSTER_2023)))
Y1_S = float(PB.w[_drop].sum())
P2 = Profile("year2", PB.n - len(_drop), CAP_BASE, units=np.delete(PB.units, _drop), key=("year2", tuple(_drop)))
_dref = base["ref"]
R_A = THETA_M - Y1_PAY
R_SA = R_A + min(Y1_PAY, _dref["mpi"] * (1 - Y1_S))
y2_regimes = [("A", "Not restored", R_A), ("SA", "Special assessment at year end, up to the cap", R_SA)]
for rp in sorted(REPL_SET, reverse=True):
    y2_regimes.append((f"R{rp}", (f"Special assessment, then the first of {rp} replenishment instalments" if rp > 1 else
                                  "Special assessment, then the rest at once (fully restored)"),
                       R_SA + (THETA_M - R_SA) / rp))
y2 = {}
for cop, _ in COPULAS:
    Dc = dist(P2, LAMBDA_P, RHO_FAIL, cop, P2.median, "corr")
    Du = dist(P2, LAMBDA_P, RHO_FAIL, cop, None, "corr")
    for code, _, R0 in y2_regimes:
        y2[(cop, code)] = reliab(Dc, Du, {**_dref, "theta": R0})
    del Dc, Du
y1_ref = {cop: rel[(cop, RHO_FAIL, "median", "ref")] for cop, _ in COPULAS}

# =============================================================================
# 11. THE BANK'S SIDE: THREE-PARTY CLEARING WITH A REPLACEMENT-COST CEILING, TWO READINGS
# =============================================================================
PRICES_BANK = [("ref", base["ref"]["pi"]), ("alt", base["alt"]["pi"]), ("cc", cc.REF8)]
bank_rows = []
for s_rep in S_REP_SET:
    for V, dp in WTP_CELLS:
        wtp = dp * V * ANNUITY
        row = dict(s_rep=s_rep, V=V, dp=dp, wtp=wtp, full=wtp + s_rep, wtd=wtp + dp * s_rep * ANNUITY)
        for nm, c_ in PRICES_BANK:
            row[("full", nm)] = max(0.0, c_ - row["full"])
            row[("wtd", nm)] = max(0.0, c_ - row["wtd"])
        bank_rows.append(row)


# =============================================================================
# 12. FORMATTING
# =============================================================================
def b1(x):
    return f"{x / BP + 1e-9:.1f}"


def b2(x):
    return f"{x / BP + 1e-12:.2f}"


def pcs(x, nd=2):
    return f"{x * 100:.{nd}f}%"


fp = cc.fp
table = cc.table


def yn(ok):
    return "yes" if ok else "no"


DN = {k: nm for k, nm, _ in DESIGNS}



# =============================================================================
# 13. RESULTS FILE
# =============================================================================
def write_results(meta):
    L = []
    w = L.append
    br, ba = base["ref"], base["alt"]
    w("# Cash That Never Sleeps, Chapter 5: the mutual with a Treasury-backed tail (mutual_tail.py results)")
    w("")
    w(f"Run environment: Python {meta['python']}, numpy {meta['numpy']}, matplotlib {meta['matplotlib']}; a single "
      f"process; the run time is printed to the console and not written here, so two runs give the same file. Command: `python -I -B "
      f"model/{SCRIPT_NAME}` from the repository root. The script imports the clearing-cost engine's "
      f"engine (`model/clearing_cost.py`) by path and reuses its parameters, copulas and quadrature. Seeds: "
      f"{WEIGHT_SEED} (member sizes), {MIX_SEED} (risk classes), {CHK_SEED} and {CHK_SEED + 1} (one-year Monte Carlo "
      f"check), {PATH_SEED} to {PATH_SEED + 2} (reserve paths), {DRAW_SEED} and {DRAW_SEED + 1} (settlement-draw "
      f"sensitivity). Risk-free rate r = {R_FREE:.1%} (the clearing-cost engine's value; verify before relying on it).")
    w("")
    w("All parameters are illustrative. Apart from figures labelled as reported public benchmarks, which are not "
      "model numbers, every parameter is an author assumption, chosen to be plausible and stated openly, and "
      "calibrated to no bank, mutual, vehicle or investor. Units: bps a year per unit of covered excess (the uninsured "
      "excess not placed through reciprocal networks) unless stated. Every number below is computed by "
      f"`{SCRIPT_NAME}`; edit parameters there, not here.")
    w("")
    # ---- 1 ----
    w("## 1. Parameters")
    w("")
    rows = [
        ("Member banks", "N", f"{N_BASE}", ", ".join(str(x) for x in N_SET), "author assumption"),
        ("Member size", "sigma", f"lognormal, sigma {SIZE_SIGMA}", f"{', '.join(f'{x:.1f}' for x in SIGMA_SET)}; clipped to $1bn to $250bn of assets; seed {WEIGHT_SEED}", "author assumption"),
        ("Liabilities / assets", "", pcs(LIAB_RATIO, 0), "", "author assumption"),
        ("Covered excess sought, share of liabilities", "", pcs(DEMAND, 0), ", ".join(pcs(x, 0) for x in DEMAND_SET), "author assumption"),
        ("Tiered per-member cap on covered excess", "", "50% of the first $5bn of liabilities, 40% of the next $5bn, 30% above; at most $30bn", "applied before the concentration cap", "author assumption (shape mirrors the reciprocal-deposit rule; not its parameters)"),
        ("Concentration cap on covered excess", "", pcs(CAP_BASE, 0), ", ".join(pcs(x, 0) for x in CAP_SET), "author assumption (design)"),
        ("Reserve target, paid in as capital at entry, in T-bills", "theta_m", pcs(THETA_M, 0), ", ".join(pcs(x, 0) for x in THETA_SET), "author assumption (design)"),
        ("Special assessment cap, multiple of annual assessment", "m", f"{M_SA}", ", ".join(str(x) for x in M_SET), "author assumption (design)"),
        ("Reserve opportunity cost over T-bills", "", f"{OPP / BP:.0f} bps", ", ".join(f"{x / BP:.0f}" for x in OPP_SET), "author assumption (the clearing-cost engine's Part I pool value)"),
        ("Mutual frictions", "f_m", f"{F_M / BP:.0f} bps", ", ".join(f"{x / BP:.0f}" for x in F_M_SET), "author assumption"),
        ("Probability an acquirer takes all deposits at closure (rule M)", "q_acq", f"{Q_ACQ:.2f}", ", ".join(f"{x:.2f}" for x in Q_SET if 0 < x), "author assumption"),
        ("Rule M: days the tail carries its advance of the assessment slice; carry rate", "", f"{ADV_DAYS}; r + s_b = {ADV_RATE:.1%}", "", "author assumption (the assessment is collected within the week)"),
        ("Exhaustion point X (cash at the trigger)", "X", f"smallest X with P(not paid in full | median member fails) <= {STD_REF[1]:.0%}, Gaussian, rho {RHO_FAIL:.2f}: {pcs(X_REF, 1)}", f"alternative: {STD_ALT[1]:.0%} under Student-t(5): {pcs(X_ALT, 1)}", "author assumption (design; the clearing-cost engine's Section 39 standards)"),
        ("Lock-up premium on the tail's funded thickness", "s_lock", f"{S_LOCK / BP:.0f} bps", ", ".join(f"{x / BP:.0f}" for x in S_LOCK_SET), "author assumption (the clearing-cost engine's FUND_K)"),
        ("Tail frictions per unit of funded thickness", "", f"{TAIL_FRIC / BP:.0f} bps", ", ".join(f"{x / BP:.1f}" for x in TAIL_FRIC_SET), "author assumption (the clearing-cost engine's 15 bps, and its technology scenarios, per 20% of funded capacity)"),
        ("Default probability per member (P)", "lambda_P", pcs(LAMBDA_P), ", ".join(pcs(x) for x in LP_SET), "author assumption (the clearing-cost engine's base)"),
        ("Risk-class mix", "", "; ".join(f"{sh:.0%} of members at {pd * 100:.2f}%" for sh, pd in MIX), f"average {MIX_AVG_COUNT * 100:.3f}% by member count, {MIX_AVG_COV * 100:.3f}% by covered excess; seed {MIX_SEED}", "author assumption"),
        ("Risk premium multiplier (tail investors)", "mu", f"{MU:.0f}", "", "author assumption (the clearing-cost engine's base)"),
        ("Loss on the deposit claim", "LGD", pcs(LGD, 0), ", ".join(pcs(x, 0) for x in LGD_SET), "author assumption (the clearing-cost engine's base)"),
        ("Advance dividend (rule B), linked to LGD", "a", f"(2/3)(1 - LGD) = {A_BASE:.0%}", ", ".join(f"{float(adv_linked(x)):.1%}" for x in LGD_SET), "author assumption (the clearing-cost engine's linked mode)"),
        ("Years to final receivership dividends (rule B)", "D", f"{D_YEARS:.0f}", "", "author assumption (the clearing-cost engine's base)"),
        ("Risk-free rate; bridge funding spread", "r; s_b", f"{R_FREE:.1%}; {S_B:.1%}", "", "the clearing-cost engine's values"),
        ("Asset correlation", "rho", f"{RHO_PRICE:.2f} (prices)", f"{', '.join(f'{x:.2f}' for x in RHO_SET)}; {RHO_FAIL:.2f} for reliability, as the clearing-cost engine", "author assumption (the clearing-cost engine's set)"),
        ("Copulas", "", "Gaussian", f"Student-t({NU})", "the clearing-cost engine's"),
        ("State-dependent LGD (reliability, paths)", "", "LGD 15% for z >= 0, linear to 40% at z = -3", "a = (2/3)(1 - LGD)", "the clearing-cost engine's correlated mode"),
        ("Replenishment assessment", "", f"over {REPL_BASE} years", ", ".join(str(x) for x in REPL_SET) + " years", "author assumption"),
        ("Replacement funding spread", "s_rep", "", ", ".join(f"{x / BP:.0f}" for x in S_REP_SET) + " bps", "author assumption"),
    ]
    w(table(["Parameter", "Symbol", "Base", "Range / set", "Source"], [[a, b, c, d, f"[{e}]"] for a, b, c, d, e in rows]))
    w("")
    w("Reported public benchmarks beside the frictions and price assumptions (reported figures, not model numbers):")
    w("")
    w(table(["Benchmark", "Reported figures", "bps of the base"], [
        ["Massachusetts Depositors Insurance Fund, 2025 net expenses", f"${MDIF_EXP / 1e6:.2f}m on ${MDIF_EXCESS / 1e9:.2f}bn of insured excess deposits", b1(MDIF_EXP_BP)],
        ["Massachusetts Depositors Insurance Fund, 2025 assessments", f"${MDIF_ASSESS / 1e6:.2f}m on ${MDIF_EXCESS / 1e9:.2f}bn", b1(MDIF_BP)],
        ["Excess Share Insurance Corp, 2025 premiums earned (loss and profit included)", f"${ESIC_PREM / 1e6:.2f}m on about ${ESIC_LIMITS / 1e9:.0f}bn of excess limits", f"about {ESIC_BP / BP:.0f}"]]))
    w("")
    w("Conventions [author assumption unless noted]. Every layer is measured in the cash the applicable rule needs at "
      "its trigger date. Rule M (primary): the stack pays the FDIC the uninsured loss share, LGD x covered excess, at "
      "closure, so an acquirer assumes every deposit whole; no advance dividend, no later dividend, no access cost. "
      "Rule B (fallback): the depositor collects the advance dividend and the layers pay (1 - a) x covered excess on "
      "day seven, own the claim and fund the remaining recovery 1 - a - LGD for D years at r + s_b. Rule M applies "
      f"with probability q_acq, drawn once for all of a year's failures (acquirer appetite as a market-wide state); "
      "Section 3 shows the same statistic with the draw independent failure by failure, and q_acq is the same under "
      "P and Q. A reported fact for orientation, not a calibration: of the three failures of spring 2023, one was a "
      "whole-bank acquisition and two went to bridge banks. The special assessment is collectable from surviving "
      "members only, m x assessment x (W - S), within the week, so it is not cash at closure: under rule M the tail "
      "advances the assessment slice at closure and is repaid from the assessment when it is collected, and cash at "
      "closure is the reserve plus the tail. Under rule B the assessment is assumed collectable by day seven, so rule B "
      "is unchanged. The tail's layer attaches where the reserve and the collectable assessment run out and is "
      "T = X - A thick, A = theta_m + m x assessment; its funded commitment is T plus the advance capacity "
      f"m x assessment x W, that is X - theta_m, and it carries the advance for up to {ADV_DAYS} days at r + s_b. The "
      "mutual prices its layer "
      "under P, the tail under Q = mu x lambda_P. All of a year's failures fall inside one settlement window. Prices "
      "use fixed LGD (the clearing-cost engine's pricing convention); reliability and the reserve paths use the state-dependent LGD "
      "and dividend of results_clearing_cost.md, Sections 38 and 44. The clearing-cost engine charges its 15 bps of frictions on the whole covered "
      "notional; here the tail's frictions scale with its funded thickness.")
    w("")
    # ---- 2 ----
    w("## 2. Member weights and caps")
    w("")
    rws = []
    profs = [(f"Base: lognormal, N {N_BASE}, demand {DEMAND:.0%}, tiered cap, cap {CAP_BASE:.0%}", PB),
             ("Same, no tiered cap (v1 weights)", PB_NT)] + \
            [(f"Lognormal, N {n_}", profile(n=n_)) for n_ in N_SET if n_ != N_BASE] + \
            [(f"Lognormal, cap {cp:.0%}", profile(cap=cp)) for cp in CAP_SET if cp != CAP_BASE] + \
            [(f"Lognormal, demand {dm:.0%} of liabilities", profile(demand=dm)) for dm in DEMAND_SET if dm != DEMAND] + \
            [(f"Lognormal, sigma {sg:.1f}", profile(sigma=sg)) for sg in SIGMA_SET if sg != SIZE_SIGMA] + \
            [(f"Equal, N {N_BASE}", PE)]
    for nm, pf in profs:
        tier_txt = (f"{pf.n_tier} / {pcs(1 - pf.cov_total / pf.dem_total, 1)}" if pf.tier and pf.cov_total else "n/a")
        rws.append([nm, f"{pf.n_eff:.1f}", pcs(pf.top5, 1), pcs(pf.w[0], 2), pcs(float(np.median(pf.w)), 3),
                    pcs(pf.w[-1], 3), tier_txt, str(pf.n_conc),
                    f"${pf.cov_total / 1e9:,.0f}bn" if pf.cov_total else "n/a"])
    w(table(["Profile", "Effective names", "Top-5 share", "Largest", "Median", "Smallest",
             "Tiered cap binds: members / share of demand cut", "Members at the 5% cap", "Covered excess"], rws))
    w("")
    w(f"At a demand of {DEMAND:.0%} of liabilities the tiered shape cannot bind (its lowest rate, 30%, is above the "
      f"demand) and the $30bn maximum binds for {PB.n_tier if PB.n_tier else 'no'} member{'' if PB.n_tier == 1 else 's'} "
      f"(the largest member seeks ${PB.w[0] * PB.cov_total / 1e9:,.0f}bn); at {DEMAND_SET[1]:.0%} and {DEMAND_SET[2]:.0%} "
      f"the cap binds for {profile(demand=DEMAND_SET[1]).n_tier} and {profile(demand=DEMAND_SET[2]).n_tier} members. "
      f"Weights are rounded to 1/{GU:,} of covered excess. The median member (rank {PB.median + 1}) and the largest "
      "member are the reference members for reliability.")
    w("")
    # ---- 3 ----
    w("## 3. Method checks")
    w("")
    w("Parity with the clearing-cost engine: the engine configured as the clearing-cost engine's reference design (50 banks at 2% each, all-funded "
      "20% buffer, no mutual, gross par, lambda_P 0.25%, mu 3, LGD 25%, a 50%; price Gaussian rho 0.20 fixed LGD; "
      "reliability conditional on a given bank failing, rho 0.30, state-dependent LGD). Printed values are read from "
      "the clearing-cost engine's results file `model/results_clearing_cost.md`; 'engine code' is its in-memory value.")
    w("")
    rws = [["Price c* (bps), layer only", b2(parity_price["layer"]), CC_PRINTED["price"], b2(parity_price["cc_code"]),
            yn(_within(parity_price["layer"] / BP, CC_PRINTED["price"]))],
           ["Price c* (bps), with the expected loss above 20% added (the clearing-cost engine's credit convention)",
            b2(parity_price["full"]), CC_PRINTED["price"], b2(parity_price["cc_code"]), yn(_within(parity_price["full"] / BP, CC_PRINTED["price"]))]]
    for cop, cn in COPULAS:
        pr = parity_rel[cop]
        for i, nm in enumerate(["shortfall", "severity", "E[unpaid]", "E[loss]"]):
            nd = len(pr["printed"][i].split(".")[1])
            rws.append([f"Section 38, 20% capacity, {cn}: {nm}", f"{pr['mine'][i]:.{nd + 2}f}%", pr["printed"][i] + "%",
                        f"{pr['code'][i]:.{nd + 2}f}%", yn(_within(pr["mine"][i], pr["printed"][i]))])
    nn = parity_rel
    rws.append(["Section 44, rule B, 20% buffer, Gaussian: shortfall", f"{nn['gauss']['net']['p_exh'] * 100:.5f}%",
                net_print["gauss"] + "%", f"{nn['gauss']['net_code']['sf'] * 100:.5f}%", yn(_within(nn['gauss']['net']['p_exh'] * 100, net_print['gauss']))])
    rws.append(["Section 44, rule B, 20% buffer, Student-t(5): shortfall", f"{nn['t']['net']['p_exh'] * 100:.5f}%",
                net_print["t"] + "%", f"{nn['t']['net_code']['sf'] * 100:.5f}%", yn(_within(nn['t']['net']['p_exh'] * 100, net_print['t']))])
    rws.append(["Section 44, rule B, 20% buffer, Student-t(5): E[depositor loss]", f"{nn['t']['net']['e_loss'] * 100:.6f}%",
                net_print["t_loss"] + "%", f"{nn['t']['net_code']['loss'] * 100:.6f}%", yn(_within(nn['t']['net']['e_loss'] * 100, net_print['t_loss']))])
    w(table(["Quantity", "This model", "Clearing-cost (printed)", "Clearing-cost (code)", "Within rounding"], rws))
    w("")
    w(f"Parity result: {'all rows match the printed values within rounding' if PARITY_OK else 'MISMATCH: see the rows marked no'}.")
    w("")
    w(f"Monte Carlo check of the engine: {CHK_YEARS:,} simulated years per copula (the clearing-cost engine's latent-variable "
      f"design), base weights, lambda_P 0.25%, rho 0.30, state-dependent LGD, mixed rule drawn once a year, the "
      "reference design. Exact = the subset-sum engine.")
    w("")
    rws = []
    for cop, cn in COPULAS:
        for r in mc_chk[cop]:
            rws.append([cn, r["name"], f"{r['exact'] * 100:.5f}%", f"{r['mc'] * 100:.5f}% +/- {1.96 * r['se'] * 100:.5f}%", f"{r['z']:+.2f}"])
    w(table(["Copula", "Quantity", "Exact", "Monte Carlo (95% band)", "z"], rws))
    w("")
    w(f"Monte Carlo check: {'every |z| is at most 3' if MC_CHECK_OK else 'at least one |z| exceeds 3'}. Mix engine check "
      f"(risk-class engine with one default probability against the exchangeable engine, rho 0.30, Gaussian): largest "
      f"relative difference {MIX_CHECK_MAX:.1e}.")
    w("")
    w(f"Settlement-draw sensitivity: P(not paid in full | median member fails), reference design, rho 0.30, "
      f"{DRAW_YEARS:,} simulated years with the median member forced to fail and each year weighted by its "
      "conditional default probability. 'Once a year' is the engine's convention; 'each failure' draws rule M or B "
      "independently for every failed member.")
    w("")
    w(table(["Copula", "Exact engine (once a year)", "Monte Carlo, once a year", "Monte Carlo, each failure"],
            [[cn, fp(draw_sens[cop]["exact"]), f"{fp(draw_sens[cop]['year']['p'])} +/- {1.96 * draw_sens[cop]['year']['se'] * 100:.3f}%",
              f"{fp(draw_sens[cop]['each']['p'])} +/- {1.96 * draw_sens[cop]['each']['se'] * 100:.3f}%"] for cop, cn in COPULAS]))
    w("")
    # ---- 4 ----
    w("## 4. Two settlement rules")
    w("")
    w("Cash each failure draws at the trigger, economic loss and access, per unit of the failed member's covered "
      "excess, by LGD:")
    w("")
    rws = []
    for lg in LGD_SET:
        a_ = float(adv_linked(lg))
        rws.append([pcs(lg, 0), f"{pcs(lg, 1)} at closure", pcs(lg, 1), "0", f"{pcs(1 - a_, 1)} on day seven",
                    pcs(lg, 1), f"{pcs(max(0, 1 - a_ - lg), 1)} for {D_YEARS:.0f} years"])
    w(table(["LGD", "Rule M: cash", "Rule M: loss", "Rule M: claim funded", "Rule B: cash", "Rule B: loss",
             "Rule B: claim funded"], rws))
    w("")
    w("Under rule M the depositor never waits and the stack needs only the loss in cash; the receivership claim "
      "stays with the FDIC. Under rule B the stack needs the advance-dividend gap in cash and later recovers part of "
      f"it. Rule M needs {LGD / (1 - A_BASE):.0%} of rule B's cash at the base LGD and "
      f"{0.40 / (1 - float(adv_linked(0.40))):.0%} at LGD 40%.")
    w("")
    br_ = base["ref"]
    S0, L0 = CLOSE_S, CLOSE_LGD
    due = L0 * S0
    res_ = min(due, br_["theta"])
    slc = min(max(due - br_["theta"], 0.0), br_["mpi"] * (PB.W - S0))
    lay = min(max(due - br_["theta"] - br_["mpi"] * (PB.W - S0), 0.0), br_["T"])
    w(f"Cash at closure under rule M, reference design, in a year in which members holding {pcs(S0, 0)} of covered "
      f"excess fail at LGD {pcs(L0, 0)} (share of covered excess). The assessment, {M_SA} x assessment x (W - S), is "
      "collected from survivors within the week, after closure. Without an advance it is a receivable at closure; in "
      "this design the tail advances it and is repaid when it is collected.")
    w("")
    w(table(["Item", "Assessment counted as a receivable", "Tail advances the assessment (this design)"], [
        ["Due to the FDIC at closure (LGD x S)", pcs(due, 4), pcs(due, 4)],
        ["Reserve", pcs(res_, 4), pcs(res_, 4)],
        ["Assessment slice, collected within the week", f"{pcs(slc, 4)} (not cash at closure)", f"{pcs(slc, 4)} (repays the advance)"],
        ["Tail: advance of the slice", "0", pcs(slc, 4)],
        ["Tail: own layer", pcs(lay, 4), pcs(lay, 4)],
        ["Cash at closure", pcs(res_ + lay, 4), pcs(res_ + slc + lay, 4)],
        ["Gap at closure", pcs(max(due - res_ - lay, 0.0), 4), pcs(max(due - res_ - slc - lay, 0.0), 4)],
        ["Tail: funded commitment (T + advance capacity)", pcs(br_["T"], 3), pcs(br_["commit"], 3)]]))
    w("")
    rM = rel[("gauss", RHO_FAIL, "median", "ref")]
    w(f"Across the conditional distribution (median member fails, Gaussian, rho {RHO_FAIL:.2f}) the tail advances in "
      f"{fp(rM['p_adv'])} of years and its largest cash call at closure (advance plus layer) is {pcs(rM['max_tail_cash'], 3)} "
      f"of covered excess, within its funded commitment of {pcs(br_['commit'], 3)}. The advance's expected carry is "
      f"{br_['adv_carry'] / BP:.4f} bps a year (r + s_b for {ADV_DAYS} days on the expected advance under Q).")
    w("")
    # ---- 5 ----
    w("## 5. The reference design: sizing the tail")
    w("")
    w(f"Exhaustion point needed to meet each conditional standard (median member fails, rho {RHO_FAIL:.2f}, "
      "state-dependent LGD), rounded up to 0.1%, by q_acq; all-in price at that X; and the other copula's "
      "performance of the same design.")
    w("")
    rws = []
    for q in Q_SET:
        rg, rt = iso_q[(q, "gauss")], iso_q[(q, "t")]
        lab = "rule B only" if q == 0 else "rule M only" if q == 1 else f"{q:.2f}"
        rows_ = []
        for r_, cop in ((rg, "gauss"), (rt, "t")):
            if r_ is None:
                rows_ += ["n/a"] * 4
                continue
            other = "t" if cop == "gauss" else "gauss"
            ro = reliab(_DC[("median", other, RHO_FAIL)], _DC[("u", other, RHO_FAIL)], r_["d"], q)
            rows_ += [pcs(r_["X"], 1), b2(r_["d"]["pi"]), fp(r_["rel"]["short"]), fp(ro["short"])]
        rws.append([lab + (" (base)" if q == Q_ACQ else "")] + rows_)
    w(table(["q_acq", "Gaussian 1%: X", "all-in", "achieved", "same design under t(5)",
             "t(5) 5%: X", "all-in", "achieved", "same design under Gaussian"], rws))
    w("")
    w("Layer stack (base, q_acq 0.5). Base-weight member = 1/N of covered excess; it draws "
      f"{pcs(PER_BW['M'], 3)} under rule M and {pcs(PER_BW['B'], 3)} under rule B at the base LGD.")
    w("")
    rws = []
    for k, nm in [(k, nm) for k, nm, _ in DESIGNS] + [("c10", f"Memo: X at {X_CLUSTER} base-weight members under rule B")]:
        g = geo[k]
        rws.append([nm, pcs(g["theta"], 2), pcs(g["mpi"], 3), pcs(g["A"], 3), pcs(g["X"], 2), pcs(g["T"], 3), pcs(g["commit"], 3)]
                   + [f"{g['bw'][r][1]:.1f} / {g['bw'][r][2]:.1f}" for r in ("M", "B")]
                   + [f"{g['top'][r][1]} / {g['top'][r][2]}" for r in ("M", "B")])
    w(table(["Design", "Reserve", "Special assessment capacity", "A", "X", "T", "Tail commitment (T + rule-M advance)", "A / X in base-weight members, rule M",
             "rule B", "A / X in largest members, rule M", "rule B"], rws))
    w("")
    w(f"The memo row keeps v1's exhaustion point: {X_CLUSTER} base-weight members under rule B pay "
      f"{pcs(memo_c10['X'], 2)} against the mutual's own attachment of {pcs(memo_c10['A'], 2)}, so the tail is "
      + ("empty" if memo_c10["T"] <= 1e-12 else f"a sliver {pcs(memo_c10['T'], 3)} thick") + f" at N {N_BASE}"
      + ("" if memo_c10["T"] <= 1e-12 else " (it was empty in v1, when the higher assessment put A above X)") + ".")
    w("")
    # ---- 6 ----
    w("## 6. Price by layer")
    w("")
    rws = []
    for key, nm in (("el_mut", "Mutual: expected loss on its retention (P)"), ("acc_mut", "Mutual: access (P)"),
                    ("carry", "Mutual: reserve carry theta_m x opportunity cost"), ("f_m", "Mutual: frictions f_m"),
                    ("mutual", "**Mutual, own layer**"), ("el_tail", "Tail: expected loss in the layer (Q)"),
                    ("acc_tail", "Tail: access (Q)"), ("lock", "Tail: lock-up s_lock x commitment"),
                    ("f_tail", "Tail: frictions on the commitment"), ("adv_carry", "Tail: carry on the rule-M assessment advance"),
                    ("tail", "**Tail premium**"), ("pi", "**All-in assessment**")):
        bold = nm.startswith("**")
        f_ = (lambda v: f"**{b2(v)}**") if bold else b2
        rws.append([nm] + [f_(base[k][key]) for k, _, _ in DESIGNS] + [b2(base_B[k][key]) for k, _, _ in DESIGNS]
                   + [b2(base_eq[k][key]) for k, _, _ in DESIGNS])
    rws.append(["Memo: expected loss above X, unprotected (P)"] + [b2(base[k]["el_pub_p"]) for k, _, _ in DESIGNS]
               + [b2(base_B[k]["el_pub_p"]) for k, _, _ in DESIGNS] + [b2(base_eq[k]["el_pub_p"]) for k, _, _ in DESIGNS])
    w(table(["Component (bps a year)"] + [f"{nm}, mixed rule" for _, nm, _ in DESIGNS]
            + [f"{nm}, rule B only (same X)" for _, nm, _ in DESIGNS] + [f"{nm}, equal weights" for _, nm, _ in DESIGNS], rws))
    w("")
    w("Side by side (bps a year per unit of covered balance):")
    w("")
    w(table(["Comparison", "bps", "Basis"], [
        [f"All-in, reference design (X {pcs(X_REF, 1)})", b2(br["pi"]), "this model"],
        [f"All-in, alternative design (X {pcs(X_ALT, 1)})", b2(ba["pi"]), "this model"],
        [f"Memo: X at {X_CLUSTER} base-weight members (tail {'empty' if memo_c10['T'] <= 1e-12 else pcs(memo_c10['T'], 3) + ' thick'})",
         b2(memo_c10["pi"]), "this model"],
        ["The clearing-cost engine's reference design (all-funded 20% buffer, gross par)", b1(cc.REF8), "results_clearing_cost.md, Section 36"],
        ["The clearing-cost engine's regional mutual pool (Part I), c*; net of its wrong-way haircut",
         f"{cc.bps(CC_POOL['c_star'])}; {cc.bps(CC_POOL['c_star'] - CC_POOL['haircut'])}", "results_clearing_cost.md, Section 7"],
        ["Massachusetts Depositors Insurance Fund, 2025 assessments / insured excess deposits", b1(MDIF_BP), "reported, not a model number"],
        ["Excess Share Insurance Corp, 2025 premiums earned / excess limits", f"about {ESIC_BP / BP:.0f}", "reported, not a model number"]]))
    w("")
    w("Step by step from v1's Gaussian 1% design. Each step re-sizes X to the 1% Gaussian standard (median member, "
      "rho 0.30); C, the choice of that standard as the reference design, is the starting row.")
    w("")
    rws, prev = [], None
    for nm, r in steps:
        rws.append([nm, pcs(r["X"], 1), pcs(r["d"]["T"], 2), b2(r["d"]["mutual"]), b2(r["d"]["tail"]), b2(r["d"]["pi"]),
                    "" if prev is None else f"{(r['d']['pi'] - prev) / BP:+.2f}"])
        prev = r["d"]["pi"]
    w(table(["Step", "X", "T", "Mutual", "Tail", "All-in", "Change"], rws))
    w("")
    # ---- 7 ----
    w("## 7. Sensitivities")
    w("")
    w("One assumption at a time from the base case (X held at each design's contract value). A is the nominal "
      "attachment, T the tail's funded thickness; bps a year except A and T.")
    w("")
    rws = []
    for g, lab, r in sweep_res:
        a, c = r["ref"], r["alt"]
        rws.append([lab, pcs(a["A"], 3), pcs(a["T"], 2), b2(a["mutual"]), b2(a["tail"]), b2(a["pi"]), pcs(c["T"], 2),
                    b2(c["tail"]), b2(c["pi"])])
    w(table(["Case", "A", "Reference: T", "mutual", "tail", "all-in", "Alternative: T", "tail", "all-in"], rws))
    w("")
    w("Range of the all-in assessment across each sweep (bps), largest first for the reference design:")
    w("")
    w(table(["Assumption", "Reference: low to high", "spread", "Alternative: low to high", "spread"],
            [[g, f"{b2(tornado[(g, 'ref')][0])} to {b2(tornado[(g, 'ref')][1])}", b2(tornado[(g, 'ref')][1] - tornado[(g, 'ref')][0]),
              f"{b2(tornado[(g, 'alt')][0])} to {b2(tornado[(g, 'alt')][1])}", b2(tornado[(g, 'alt')][1] - tornado[(g, 'alt')][0])]
             for g in order_tornado_keys()]))
    w("")
    w("All-in against lambda_P (bps), with the clearing-cost engine's reference design at the same default probability:")
    w("")
    rws = [[pcs(lp)] + [b2(lp_curve[(cop, k)][i]) for cop, _ in COPULAS for k, _, _ in DESIGNS] + [b1(lp_cc[i])]
           for i, lp in enumerate(LP_FIG)]
    w(table(["lambda_P"] + [f"{cn}, {nm.split(':')[0].lower()}" for _, cn in COPULAS for _, nm, _ in DESIGNS]
            + ["Pooled-vehicle reference design"], rws))
    w("")
    # ---- 8 ----
    w("## 8. Risk-class mix")
    w("")
    w(f"Members assigned to classes at random (seed {MIX_SEED}), independent of size. Coverage share by class: "
      + ", ".join(f"{pd * 100:.2f}% class {MIX_COV[i]:.1%}" for i, pd in enumerate(MIX_PDS))
      + f". Average lambda_P {MIX_AVG_COUNT * 100:.3f}% by member count, {MIX_AVG_COV * 100:.3f}% by covered excess. "
      "Class rates allocate the risk terms by class lambda_P relative to the coverage-weighted average and the fixed "
      "terms pro rata [allocation convention]. The mix carries fixed LGD 25% throughout: a state-dependent LGD would "
      "need the frequency-domain step once per LGD state, which does not fit the run-time budget.")
    w("")
    rws = []
    for cop, cn in COPULAS:
        for k, nm, _ in DESIGNS:
            r = mix_price[(cop, k)]
            rws.append([cn, nm, pcs(r["A"], 3), b2(r["mutual"]), b2(r["tail"]), b2(r["pi"])] + [b2(x) for x in class_rates(r, MIX_AVG_COV)])
    w(table(["Copula", "Design", "A", "Mutual", "Tail", "All-in (pool)"] + [f"Class {pd * 100:.2f}% rate" for pd in MIX_PDS], rws))
    w("")
    rws = []
    for cop, cn in COPULAS:
        for who in ("median", "largest"):
            for k, nm, _ in DESIGNS:
                r = rel_mix[(cop, who, k)]
                rws.append([cn, who, nm, fp(r["res"]), fp(r["sa"]), fp(r["tail"]), fp(r["short"]), fp(r["u_exh"])])
    w("Reliability with the mix, rho 0.30, fixed LGD, design at the Gaussian mix price:")
    w("")
    w(table(["Copula", "Member", "Design", "Reserve alone", "Plus special assessment", "Plus tail", "Short",
             "Unconditional: stack exhausted"], rws))
    w("")
    # ---- 9 ----
    w("## 9. Reliability in the year a given member fails")
    w("")
    w("Real-world measure, conditional on the reference member failing in the year (the clearing-cost engine's ref_cond logic), "
      "state-dependent LGD and advance dividend, mixed rule; the cash test is at the trigger date of the rule that "
      "applies. 'Reserve alone' = the cash is within the reserve; 'plus special assessment' = the special assessment "
      "completes it; 'plus tail' = the tail is needed and completes it; 'short' = the stack is exhausted (public "
      "tail). The four sum to 100%. E[loss] = expected unpaid share x LGD, % of the member's covered excess. "
      "Unconditional 'stack exhausted' is the probability, in any year, that the public layer is reached.")
    w("")
    for rho in (RHO_FAIL, RHO_PRICE):
        w(f"rho {rho:.2f}:")
        w("")
        rws = []
        for cop, cn in COPULAS:
            for who in ("median", "largest"):
                for k, nm in [(k, nm) for k, nm, _ in DESIGNS] + [("ref_B", "Reference, rule B only (comparison)")]:
                    r = rel[(cop, rho, who, k)]
                    rws.append([cn, f"{who} ({pcs(PB.w[PB.median if who == 'median' else 0], 2)})", nm, fp(r["res"]),
                                fp(r["sa"]), fp(r["tail"]), fp(r["short"]), fp(r["full"]), pcs(r["sev"], 1),
                                f"{r['e_loss'] * 100:.4f}%", fp(r["u_tail"]), fp(r["u_exh"])])
        w(table(["Copula", "Member (weight)", "Design", "Reserve alone", "Plus special assessment", "Plus tail", "Short",
                 "Paid in full", "Severity", "E[loss]", "Unconditional: mutual exhausted",
                 "Unconditional: stack exhausted"], rws))
        w("")
    w("Reference design by q_acq (X held at the reference value), median member, rho 0.30, short / stack exhausted:")
    w("")
    w(table(["q_acq"] + [cn for _, cn in COPULAS],
            [["rule B only" if q == 0 else "rule M only" if q == 1 else f"{q:.2f}"]
             + [f"{fp(rel_q[(q, cop)]['short'])} / {fp(rel_q[(q, cop)]['u_exh'])}" for cop, _ in COPULAS] for q in Q_SET]))
    w("")
    w("Equal weights and fixed-LGD sensitivities, rho 0.30, median member, short / stack exhausted:")
    w("")
    rws = []
    for cop, cn in COPULAS:
        rws.append([cn] + [f"{fp(rel[(cop, RHO_FAIL, 'median', k)]['short'])} / {fp(rel[(cop, RHO_FAIL, 'median', k)]['u_exh'])}" for k, _, _ in DESIGNS]
                   + [f"{fp(rel_eq[(cop, k)]['short'])} / {fp(rel_eq[(cop, k)]['u_exh'])}" for k, _, _ in DESIGNS]
                   + [f"{fp(rel_fixed[(cop, k)]['short'])} / {fp(rel_fixed[(cop, k)]['u_exh'])}" for k, _, _ in DESIGNS])
    w(table(["Copula"] + [f"Base, {k}" for k, _, _ in DESIGNS] + [f"Equal weights, {k}" for k, _, _ in DESIGNS]
            + [f"Fixed LGD 25%, {k}" for k, _, _ in DESIGNS], rws))
    w("")
    w(f"Memo (v1's X at {X_CLUSTER} members, tail empty), median member, rho 0.30, short: "
      + "; ".join(f"{cn} {fp(rel[(cop, RHO_FAIL, 'median', 'c10')]['short'])}" for cop, cn in COPULAS) + ".")
    w("")
    # ---- 10 ----
    w("## 10. Single-member test")
    w("")
    w("One member fails alone: a member sized at the concentration cap, and the largest member actually drawn where "
      "the cap does not bind. Cash at the trigger as % of covered excess against the reserve; 'yes' = the reserve "
      "alone pays. The last case is a rule-B failure whose dividend is not paid by day seven, so the layers pay par.")
    w("")
    rws = [[pcs(r["cap"], 0), r["who"], pcs(r["wmax"], 2), r["case"], pcs(r["pay"], 2), pcs(r["loss"], 2)]
           + [yn(r["ok"][th]) for th in THETA_SET] for r in single]
    w(table(["Cap", "Member", "Weight", "Case", "Cash", "Economic loss"] + [f"Reserve {pcs(th, 0)} pays alone" for th in THETA_SET], rws))
    w("")
    w(f"Probability the reserve alone ({THETA_M:.0%}) does not pay in a year in which the largest member "
      f"({pcs(PB.w[0], 2)}) fails, mixed rule, state-dependent LGD: "
      + "; ".join(f"{COPN[cop]} rho {rho:.2f}: {fp(single_prob[(cop, rho)])}" for cop, _ in COPULAS for rho in (RHO_FAIL, RHO_PRICE)) + ".")
    w("")
    # ---- 11 ----
    w("## 11. Replenishment after a loss year")
    w("")
    w(f"Ten-year paths from the target reserve ({THETA_M:.0%}, paid in at entry), {PATH_N:,} paths, base weights, "
      "lambda_P 0.25%, state-dependent LGD, mixed rule drawn each year, reference design. Each year: cash payouts from "
      "the reserve, then the special assessment (up to the cap), then the tail up to T; T-bill income; the "
      "expected-loss and access parts of the assessment kept as income; rule-B recoveries after D years. At year end "
      "a reserve below target is restored first by a special assessment up to the unused part of that year's cap, "
      "then by a replenishment assessment in equal annual instalments (the first at once). Reserve above target is "
      "rebated; the rebate includes the T-bill income on the members' paid-in reserve. Reserve ratio = liquid "
      "reserve / covered excess at year end, after restoration.")
    w("")
    rws = []
    for cop, rho, lab in PATH_RUNS:
        for rp in REPL_SET:
            p = paths[(cop, rho, rp)]
            rws.append([lab, str(rp)] + [" / ".join(pcs(v, 2) for v in p["q"][y]) for y in PATH_REPORT]
                       + [fp(p["short_start"]), fp(p["ever"]["sa"]), fp(p["ever"]["repl"]), fp(p["ever"]["tail"]),
                          fp(p["ever"]["tail_short"]), fp(p["ever"]["exh"]), b2(p["extra"]), b2(p["rebate"])])
    p = paths["alt"]
    rws.append(["Gaussian, rho 0.20, alternative design", str(REPL_BASE)] + [" / ".join(pcs(v, 2) for v in p["q"][y]) for y in PATH_REPORT]
               + [fp(p["short_start"]), fp(p["ever"]["sa"]), fp(p["ever"]["repl"]), fp(p["ever"]["tail"]),
                  fp(p["ever"]["tail_short"]), fp(p["ever"]["exh"]), b2(p["extra"]), b2(p["rebate"])])
    w(table(["Run", "Replenish over (years)"] + [f"Year {y}: 5th / 50th / 95th" for y in PATH_REPORT]
            + ["Years starting below target", "At least one special assessment for losses", "At least one restoration",
               "Tail pays at least once", "Tail pays in a year started below target", "Stack exhausted at least once",
               "Mean restoration assessment (bps a year)", "Mean rebate (bps a year)"], rws))
    w("")
    w("Probability the reserve is below target at each year end (after restoration):")
    w("")
    w(table(["Run", "Replenish over"] + [f"Year {y}" for y in range(1, PATH_YEARS + 1)],
            [[lab, str(rp)] + [fp(v) for v in paths[(cop, rho, rp)]["below"]] for cop, rho, lab in PATH_RUNS for rp in REPL_SET]))
    w("")
    pv = paths["v1start"]
    w(f"Memo (v1 convention, for comparison): starting at {PATH_R0_V1:.0%} with no capital call and no replenishment, "
      f"Gaussian rho 0.20, the median reserve is {pcs(pv['q'][10][1], 2)} at year 10 and the stack is exhausted at "
      f"least once in {fp(pv['ever']['exh'])} of paths; the tail pays in a year started below target in "
      f"{fp(pv['ever']['tail_short'])} of paths.")
    w("")
    w(f"Year 2 after a 2023-like cluster (the logic of results_clearing_cost.md, Section 40). Year 1: three members of about base weight "
      f"({pcs(Y1_S, 2)} of covered excess together) fail, two settled under rule B and one under rule M at the base "
      f"LGD, taking {pcs(Y1_PAY, 2)} of cash from the reserve; rule-B recoveries have not yet arrived. Year 2: "
      f"{P2.n} surviving members at their original weights, rho 0.30, state-dependent LGD, mixed rule, the "
      "reference design's tail unchanged; the reserve enters Year 2 at the level shown. Conditional on the median "
      "surviving member failing in Year 2: short / E[unpaid share]; unconditional: stack exhausted.")
    w("")
    rws = []
    for code, nm, R0 in y2_regimes:
        rws.append([nm, pcs(R0, 2)] + [f"{fp(y2[(cop, code)]['short'])} / {pcs(y2[(cop, code)]['e_u'], 4)}" for cop, _ in COPULAS]
                   + [fp(y2[(cop, code)]["u_exh"]) for cop, _ in COPULAS])
    rws.append(["Year 1 at full reserve (reference)", pcs(THETA_M, 2)]
               + [f"{fp(y1_ref[cop]['short'])} / {pcs(y1_ref[cop]['e_u'], 4)}" for cop, _ in COPULAS]
               + [fp(y1_ref[cop]["u_exh"]) for cop, _ in COPULAS])
    w(table(["Year-2 reserve regime", "Reserve entering Year 2"] + [f"{cn}: short / E[unpaid]" for _, cn in COPULAS]
            + [f"{cn}: stack exhausted" for _, cn in COPULAS], rws))
    w("")
    # ---- 12 ----
    w("## 12. The bank's side: three-party clearing with a replacement-cost ceiling")
    w("")
    w("The condition of results_clearing_cost.md, Section 41, Delta + bank value >= price, with the bank's replacement funding spread "
      "s_rep (reciprocal fee plus rate uplift, or an FHLB advance, over the deposit's cost) added to the retention "
      f"value WTP = dP_run x V x {ANNUITY:.3f}. Two readings. Full count: s_rep in full each year (the counterfactual "
      "is the balance not held at the bank); this is the ceiling on what the bank should pay to keep the balance. "
      f"Probability-weighted: dP_run x s_rep x {ANNUITY:.3f}, the expected replacement cost avoided. Smallest Delta "
      "that clears (bps):")
    w("")
    for rd, title in (("full", "Full-count reading (ceiling)"), ("wtd", "Probability-weighted reading (expected value)")):
        w(f"{title}:")
        w("")
        rws = []
        for r in bank_rows:
            cell = "none" if r["V"] == 0 else f"V {r['V'] / BP:.0f}, dP_run {r['dp']:.1%}"
            rws.append([f"{r['s_rep'] / BP:.0f}", cell, b1(r["wtp"]), b1(r[rd])] + [b1(r[(rd, nm)]) for nm, _ in PRICES_BANK])
        w(table(["s_rep", "Retention cell", "WTP", "Bank total", f"Min Delta, reference ({b2(br['pi'])})",
                 f"Min Delta, alternative ({b2(ba['pi'])})", f"Min Delta, pooled-vehicle reference ({b1(cc.REF8)})"], rws))
        w("")
    # ---- 13 ----
    w("## 13. What the numbers say")
    w("")
    w(what_numbers_say())
    w("")
    # ---- 14 ----
    w("## 14. Modelling notes")
    w("")
    notes = [
        "Layers are measured in the cash the applicable rule needs at its trigger date (rule M at closure, rule B on "
        "day seven). Economic loss equals the cash under rule M and LGD / (1 - a) of it under rule B.",
        "Rule M or B is drawn once for all of a year's failures; Section 3 shows that drawing it failure by failure "
        "changes the reference design's conditional shortfall by less than the Monte Carlo error.",
        "The special assessment is levied on survivors only and collected within the week. Under rule M it is not cash "
        "at closure: the tail advances it and is repaid when it is collected, so the tail's funded commitment is its "
        "layer T plus the advance capacity (X - theta_m in all), and lock-up and frictions are charged on the "
        "commitment. The tail's layer attaches where the reserve and the collectable assessment run out (fixed "
        "thickness T). While the reserve is below target the tail attaches lower than priced.",
        "The reserve is paid in at entry; its carry is priced as theta_m x the opportunity cost. A year-end special "
        "assessment for restoration uses only the unused part of that year's cap.",
        "Members price their own layer under P; the tail's investors price under Q (mu 3); q_acq is the same under both.",
        "Tail frictions scale with funded thickness at the clearing-cost engine's ratio; the fixed costs of a separate vehicle would "
        "make a thin layer dearer than shown.",
        "The risk-class mix carries fixed LGD; all other reliability figures use the state-dependent LGD.",
        "The tiered cap uses member liabilities derived from the lognormal sizes; its shape mirrors the reciprocal-"
        "deposit rule and its parameters are author assumptions.",
        "The bank's side shows both readings of the replacement spread: the full count as a ceiling, the probability-"
        "weighted count as the expected value.",
        "The run time is printed to the console only, so the results file is identical across runs.",
        "The advance carries no credit charge: the assessment on survivors is assumed collectable within the week. A "
        "survivor that cannot pay would leave the tail with a claim on it; that risk is not priced.",
    ]
    for i, t in enumerate(notes, 1):
        w(f"{i}. {t}")
    w("")
    RESULTS_MD.write_text("\n".join(L), encoding="utf-8")


TORNADO_NAMES = {"lambda_P": "the default probability", "LGD": "LGD", "rho": "correlation", "copula": "the copula",
                 "q_acq": "the acquirer probability", "N": "the member count", "cap": "the concentration cap",
                 "demand": "the covered excess sought", "sigma": "the member size dispersion",
                 "theta_m": "the reserve target", "m": "the special-assessment cap",
                 "opp": "the reserve's opportunity cost", "f_m": "the mutual's frictions", "s_lock": "the lock-up premium",
                 "f_tail": "the tail's frictions"}


def order_tornado_keys(k="ref"):
    return sorted({g for g, _ in tornado}, key=lambda g: -(tornado[(g, k)][1] - tornado[(g, k)][0]))


def what_numbers_say():
    br, ba = base["ref"], base["alt"]
    rg, rt = rel[("gauss", RHO_FAIL, "median", "ref")], rel[("t", RHO_FAIL, "median", "ref")]
    top = [TORNADO_NAMES[g] for g in order_tornado_keys()[:3]]
    pth = paths[("gauss", RHO_PRICE, REPL_BASE)]
    v1 = steps[0][1]["d"]["pi"]
    dA = steps[1][1]["d"]["pi"] - v1
    dD = ISO_REF["d"]["pi"] - steps[3][1]["d"]["pi"]
    dT = steps[3][1]["d"]["pi"] - steps[2][1]["d"]["pi"]
    tier_txt = ("the paid-in reserve and the tiered cap leave the price unchanged" if abs(dT) < 0.005 * BP else
                f"the paid-in reserve leaves the price unchanged and the tiered cap moves it {dT / BP:+.2f} bps")
    s1 = (f"The reference design sizes the tail so that, in the year the median member fails, the stack falls short "
          f"with probability at most 1% under the Gaussian copula. With an acquirer settling under rule M in "
          f"{Q_ACQ:.0%} of loss years, that takes X to {pcs(X_REF, 1)} and the all-in assessment to {b1(br['pi'])} bps "
          f"a year on covered excess: {b1(br['mutual'])} for the mutual and {b1(br['tail'])} for the tail. Expected "
          f"loss and access are {b1(br['el_mut'] + br['acc_mut'] + br['el_tail'] + br['acc_tail'])} of it. From v1's "
          f"{b1(v1)} bps, lower frictions take {abs(dA) / BP:.1f} bps off and the mixed rule {abs(dD) / BP:.1f}; {tier_txt}.")

    s2 = (f"The same design falls short with probability {fp(rt['short'])} under the Student-t(5) copula. Meeting a 5% "
          f"t standard takes X to {pcs(X_ALT, 1)} and the price to {b1(ba['pi'])} bps. The stack is exhausted, and the "
          f"public layer reached, in {fp(rg['u_exh'])} of years (Gaussian) and {fp(rt['u_exh'])} (t).")
    s3 = (f"With the reserve paid in at entry and losses restored by special assessment and then a {REPL_BASE}-year "
          f"replenishment, the reserve is below target at a year end with probability about "
          f"{fp(float(np.mean(pth['below'][1:])))}, and the tail pays in a year started short in "
          f"{fp(pth['ever']['tail_short'])} of ten-year paths. After a 2023-like cluster with the reserve not restored, "
          f"the Year-2 Gaussian shortfall is {fp(y2[('gauss', 'A')]['short'])} against {fp(y1_ref['gauss']['short'])} "
          f"in Year 1.")
    s4 = (f"The clearing-cost engine's all-funded reference is {b1(cc.REF8)} bps; the Massachusetts fund reported {b1(MDIF_BP)} bps of "
          f"assessments. Across the sweeps the reference price moves most with {top[0]}, {top[1]} and {top[2]}.")
    return "\n\n".join([s1, s2, s3, s4])


# =============================================================================
# 14. FIGURES
# =============================================================================
def make_figures():
    import logging
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

    NAVY, STEEL, SLATE, MIST, INK, GRID, ACCENT = "#1F3A5F", "#4F74A8", "#8A9AAE", "#C9D3DF", "#2B2B2B", "#E3E7EC", "#D2851F"
    MUTED, DARKACC = "#4A5361", "#9A5A0A"
    fam = "Inter" if any(f.name == "Inter" for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
    plt.rcParams.update({
        "font.family": fam, "font.size": 10, "axes.edgecolor": "#8C96A3", "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "text.color": INK,
    })
    SRC = "Source: author's calculations."
    ILL = "Illustrative parameters, calibrated to no bank."
    pctfmt = lambda nd: matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.{nd}f}%")

    def frame(fig, title, subtitle, source):
        fig.text(0.06, 0.955, title, fontsize=14, fontweight="semibold", ha="left", va="top", color=INK)
        fig.text(0.06, 0.905, subtitle, fontsize=10, ha="left", va="top", color="#5A6472")
        fig.text(0.06, 0.03, source, fontsize=7.5, ha="left", va="bottom", color="#6B7480")

    def grid_y(ax):
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)

    br, ba = base["ref"], base["alt"]
    dlist = [("ref", br, f"Reference\n(X {pcs(X_REF, 1)})"), ("alt", ba, f"Alternative\n(X {pcs(X_ALT, 1)})")]

    # ---- M01: layer stack and price decomposition ----------------------------------------------------
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(10.5, 5.8), gridspec_kw=dict(width_ratios=[1, 1.7]))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.22, wspace=0.42)
    for i, (k, d, lab) in enumerate(dlist):
        segs = [(d["theta"], NAVY, "Reserve"), (d["mpi"], STEEL, "Assessment, tail-advanced (M)"),
                (d["T"], ACCENT, "Tail layer")]
        y0 = 0.0
        for h, col, nm in segs:
            if h > 0:
                axl.bar(i, h * 100, 0.55, bottom=y0 * 100, color=col, edgecolor="white")
                if i == 1:
                    axl.text(i + 0.31, (y0 + h / 2) * 100, f"{nm} {pcs(h, 1)}", fontsize=8, color=col, va="center", ha="left", clip_on=False)
            y0 += h
        axl.text(i, y0 * 100 + 0.4, pcs(y0, 1), ha="center", va="bottom", fontsize=8.5)
    axl.set_xlim(-0.45, 1.95)
    axl.set_xticks([0, 1])
    axl.set_xticklabels([lab for _, _, lab in dlist], fontsize=9)
    axl.tick_params(axis="x", length=0)
    axl.yaxis.set_major_formatter(pctfmt(0))
    axl.set_ylabel("Cash capacity at the trigger, % of covered excess", fontsize=9, color=MUTED)
    grid_y(axl)
    axl.set_title("The stack", loc="left", fontsize=10.5, fontweight="semibold", pad=8)
    comps = [("el_mut", "Mutual: expected loss (P)", NAVY), ("acc_mut", "Mutual: access", STEEL),
             ("carry", "Mutual: reserve carry", SLATE), ("f_m", "Mutual: frictions", MIST),
             ("el_tail", "Tail: expected loss and access (Q)", DARKACC), ("lock", "Tail: lock-up and advance carry", ACCENT),
             ("f_tail", "Tail: frictions", "#EBC48A")]
    for i, (k, d, lab) in enumerate(dlist):
        y0 = 0.0
        for key, nm, col in comps:
            v = d[key] + (d["acc_tail"] if key == "el_tail" else 0.0) + (d["adv_carry"] if key == "lock" else 0.0)
            axr.bar(i, v / BP, 0.55, bottom=y0, color=col, edgecolor="white")
            y0 += v / BP
        axr.text(i, y0 + 0.6, f"{y0:.1f}", ha="center", va="bottom", fontsize=9.5, fontweight="semibold")
    refs = [(cc.REF8, "Pooled-vehicle\nreference", None), (ESIC_BP, "Excess Share\n(reported)", "///"),
            (MDIF_BP, "Massachusetts\n(reported)", "///")]
    for j, (v, lab, h) in enumerate(refs):
        axr.bar(2 + j, v / BP, 0.55, color="#B9C2CE", hatch=h, edgecolor="white")
        axr.text(2 + j, v / BP + 0.6, f"{v / BP:.1f}", ha="center", va="bottom", fontsize=9.5, fontweight="semibold")
    axr.set_xticks(range(5))
    axr.set_xticklabels([lab for _, _, lab in dlist] + [lab for _, lab, _ in refs], fontsize=8.2)
    axr.tick_params(axis="x", length=0)
    axr.set_ylabel("bps a year on covered excess", fontsize=9, color=MUTED)
    grid_y(axr)
    axr.set_ylim(0, cc.REF8 / BP * 1.15)
    axr.set_title("Price by layer", loc="left", fontsize=10.5, fontweight="semibold", pad=8)
    fig.legend(handles=[Patch(color=col, label=nm) for _, nm, col in comps], loc="lower left", bbox_to_anchor=(0.06, 0.085),
               ncol=4, frameon=False, fontsize=8)
    frame(fig, "The reference stack prices well below the all-funded design",
          f"Layer stack and all-in assessment, {PB.n} members, reserve {THETA_M:.0%} paid in, special assessment cap {M_SA}x, mixed settlement (q_acq {Q_ACQ:.1f})",
          SRC + " Default probability 0.25%, LGD 25%, correlation 0.20, Gaussian copula for prices. The Excess Share and Massachusetts bars are reported\n"
          "premiums or assessments over the insured base, public benchmarks, not model numbers. " + ILL)
    fig.savefig(FIG(1), dpi=200)
    plt.close(fig)

    # ---- M02: price against lambda_P by copula ------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    fig.subplots_adjust(left=0.1, right=0.76, top=0.8, bottom=0.2)
    xs_ = [lp * 100 for lp in LP_FIG]
    sty = {("gauss", "ref"): (NAVY, "-"), ("t", "ref"): (NAVY, (0, (4, 2))), ("gauss", "alt"): (ACCENT, "-"), ("t", "alt"): (ACCENT, (0, (4, 2)))}
    for (cop, k), (col, ls) in sty.items():
        ys = [v / BP for v in lp_curve[(cop, k)]]
        ax.plot(xs_, ys, color=col, ls=ls, lw=2.0, marker="o", ms=3.5)
        dy = {("t", "ref"): 2.5, ("gauss", "ref"): -2.5}.get((cop, k), 0.0)
        ax.text(xs_[-1] + 0.03, ys[-1] + dy, f"{'Gaussian' if cop == 'gauss' else 't(5)'}, {'reference' if k == 'ref' else 'alternative'}",
                color=col, fontsize=8.5, va="center", ha="left", clip_on=False)
    ys = [v / BP for v in lp_cc]
    ax.plot(xs_, ys, color=SLATE, lw=1.6, marker="s", ms=3.5)
    ax.text(xs_[-1] + 0.03, ys[-1], "Pooled-vehicle reference\n(all-funded 20%)", color=SLATE, fontsize=8.5, va="center", ha="left", clip_on=False)
    ax.axvline(LAMBDA_P * 100, color=INK, lw=0.8, ls=(0, (1, 1.5)))
    ax.set_xlabel("Default probability per member, lambda_P (%)", fontsize=9.5, color=MUTED)
    ax.set_ylabel("All-in, bps a year on covered excess", fontsize=9.5, color=MUTED)
    grid_y(ax)
    ax.set_xlim(0, 1.55)
    frame(fig, "Price rises with default risk, more slowly than the all-funded design",
          "All-in assessment against lambda_P, X held at each design's contract value, Gaussian and Student-t(5) copulas",
          SRC + f" {PB.n} members, theta_m {THETA_M:.0%}, m {M_SA}, LGD 25%, correlation 0.20, mixed settlement; dotted line at the base 0.25%.\n" + ILL)
    fig.savefig(FIG(2), dpi=200)
    plt.close(fig)

    # ---- M03: reliability against theta_m and m ------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 5.6))
    fig.subplots_adjust(left=0.09, right=0.97, top=0.76, bottom=0.27, wspace=0.25)
    cols = [SLATE, STEEL, NAVY, "#0E1F36"]
    FLOOR = 1e-4
    for ax, (cop, cn) in zip(axs, COPULAS):
        for m_, col in zip(M_SET, cols):
            ax.plot([t * 100 for t in THETA_FIG], [max(v, FLOOR) for v in rel_curve[(cop, m_)]], color=col, lw=2.0)
        for k, ls in (("ref", (0, (1, 1.5))), ("alt", (0, (4, 2)))):
            v = max(stack_line[(cop, k)], FLOOR)
            ax.axhline(v, color=ACCENT, lw=1.3, ls=ls)
            ax.text(10, v, f"Stack, {'reference' if k == 'ref' else 'alternative'}: {fp(stack_line[(cop, k)])}",
                    color=DARKACC, fontsize=8, va="bottom", ha="right")
        ax.axvline(THETA_M * 100, color=INK, lw=0.8, ls=(0, (1, 1.5)))
        ax.set_yscale("log")
        ax.set_ylim(FLOOR, 1.2)
        ax.set_yticks([1, 1e-1, 1e-2, 1e-3, 1e-4])
        ax.set_yticklabels(["100%", "10%", "1%", "0.1%", "0.01%"])
        ax.minorticks_off()
        ax.set_xlim(1, 10)
        ax.xaxis.set_major_formatter(pctfmt(0))
        ax.set_xlabel("Reserve target theta_m, % of covered excess", fontsize=9, color=MUTED)
        grid_y(ax)
        ax.set_title(f"{cn} copula", loc="left", fontsize=10.5, fontweight="semibold", pad=8)
    axs[0].set_ylabel("P(not paid in full | median member fails)", fontsize=9, color=MUTED)
    handles = [Line2D([0], [0], color=c_, lw=2, label=f"Mutual alone, special assessment cap {m_}x") for m_, c_ in zip(M_SET, cols)]
    handles += [Line2D([0], [0], color=ACCENT, lw=1.3, ls=(0, (1, 1.5)), label="Full stack, reference design"),
                Line2D([0], [0], color=ACCENT, lw=1.3, ls=(0, (4, 2)), label="Full stack, alternative design")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.06, 0.075), ncol=3, frameon=False, fontsize=8.3)
    frame(fig, "The special-assessment cap barely moves reliability; the reserve and the tail do",
          "Probability the cash at the trigger is not paid in full in a year in which the median member fails",
          SRC + f" {PB.n} members, default probability 0.25%, correlation 0.30, state-dependent LGD, mixed settlement, real-world measure; the\n"
          "assessment (and so the special-assessment capacity) is re-solved at each reserve target. " + ILL)
    fig.savefig(FIG(3), dpi=200)
    plt.close(fig)

    # ---- M04: reserve path fan, paid in at entry against built from 1% ------------------------------------
    p = paths[("gauss", RHO_PRICE, REPL_BASE)]
    pv = paths["v1start"]
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    fig.subplots_adjust(left=0.1, right=0.95, top=0.8, bottom=0.24)
    yrs = np.arange(PATH_YEARS + 1)
    f_, fv = p["fan"] * 100, pv["fan"] * 100
    ax.fill_between(yrs, fv[0], fv[4], color=MIST, lw=0, label=f"Built from {PATH_R0_V1:.0%} (v1 memo): 5th to 95th percentile")
    ax.plot(yrs, fv[2], color=SLATE, lw=2.0, label=f"Built from {PATH_R0_V1:.0%}: median")
    ax.fill_between(yrs, f_[0], f_[4], color=STEEL, lw=0, alpha=0.6, label=f"Paid in at entry, replenished over {REPL_BASE} years: 5th to 95th")
    ax.plot(yrs, f_[2], color=NAVY, lw=2.2, label="Paid in at entry: median")
    ax.axhline(THETA_M * 100, color=ACCENT, lw=1.3, ls=(0, (4, 2)))
    ax.text(0.1, THETA_M * 100 + 0.03, f"Target {THETA_M:.0%}", color=DARKACC, fontsize=8.8, va="bottom", ha="left")
    ax.set_xlim(0, PATH_YEARS)
    ax.set_ylim(0, THETA_M * 100 * 1.12)
    ax.set_xticks(yrs)
    ax.yaxis.set_major_formatter(pctfmt(1))
    ax.set_xlabel("Year", fontsize=9.5, color=MUTED)
    ax.set_ylabel("Liquid reserve at year end, % of covered excess", fontsize=9.5, color=MUTED)
    grid_y(ax)
    ax.legend(loc="lower right", frameon=False, fontsize=8.3)
    frame(fig, "A paid-in reserve holds its target; one built from 1% does not reach it",
          f"Liquid reserve over ten years, {PATH_N:,} paths, reference design",
          SRC + f" Gaussian copula, correlation 0.20, default probability 0.25%, state-dependent LGD, mixed\n"
          f"settlement, {PB.n} members. Paid in: losses restored at year end by special assessment, then instalments.\n"
          "Built from 1%: no capital call, no replenishment. Reserve above target is rebated. " + ILL)
    fig.savefig(FIG(4), dpi=200)
    plt.close(fig)

    # ---- M05: single-member test ---------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9.5, 5.4))
    fig.subplots_adjust(left=0.1, right=0.82, top=0.8, bottom=0.22)
    ccol = [STEEL, "#86A1C9", NAVY, "#3A5A85", SLATE]
    Wb = 0.16
    for gi, cp in enumerate(CAP_SET):
        for ci, ((case, _, _), col) in enumerate(zip(SINGLE_CASES, ccol)):
            r = next(r for r in single if r["cap"] == cp and r["case"] == case and r["who"] == "member at the cap")
            x = gi + (ci - 2) * (Wb + 0.01)
            ax.bar(x, r["pay"] * 100, Wb, color=col)
            ax.text(x, r["pay"] * 100 + 0.08, f"{r['pay'] * 100:.1f}", ha="center", va="bottom", fontsize=7.5)
    for th in THETA_SET:
        ax.axhline(th * 100, color=ACCENT, lw=1.1, ls=(0, (4, 2)) if th != THETA_M else "-")
        ax.text(2.62, th * 100, f"Reserve {th:.0%}", color=DARKACC, fontsize=8.5, va="center", ha="left", clip_on=False)
    ax.set_xticks(range(len(CAP_SET)))
    ax.set_xticklabels([f"Member at a {cp:.0%} cap" for cp in CAP_SET], fontsize=9)
    ax.tick_params(axis="x", length=0)
    ax.yaxis.set_major_formatter(pctfmt(0))
    ax.set_ylabel("Cash at the trigger, % of covered excess", fontsize=9.5, color=MUTED)
    grid_y(ax)
    ax.legend(handles=[Patch(color=c_, label=cs) for (cs, _, _), c_ in zip(SINGLE_CASES, ccol)], loc="upper left", frameon=False, fontsize=8.3)
    frame(fig, "One member at a 5% cap fits the reserve unless its dividend is late",

          "A member sized at the concentration cap fails alone: the cash the layers must pay against the reserve",
          SRC + f" Cash = member's share of covered excess x LGD (rule M) or x (1 - a) (rule B); the last bar is a rule-B failure whose dividend is\n"
          f"not paid by day seven. With sigma {SIZE_SIGMA:.1f} the largest drawn member is {pcs(PB.w[0], 2)}. " + ILL)
    fig.savefig(FIG(5), dpi=200)
    plt.close(fig)

    # ---- M06: three-party condition, two readings -------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(10.5, 5.4), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.76, bottom=0.27, wspace=0.12)
    sg = np.arange(0, 81, 1.0)
    lines = [(br["pi"], 0.0, 0.0, NAVY, "-", "Reference, no retention value"),
             (br["pi"], 100 * BP, 0.01, STEEL, "-", "Reference, V 100, dP_run 1%"),
             (br["pi"], 150 * BP, 0.05, SLATE, "-", "Reference, V 150, dP_run 5%"),
             (ba["pi"], 0.0, 0.0, NAVY, (0, (4, 2)), "Alternative, no retention value"),
             (cc.REF8, 0.0, 0.0, ACCENT, "-", "Pooled-vehicle reference, no retention value")]
    for ax, rd, ttl in ((axs[0], "full", "Full count: replacement spread every year (ceiling)"),
                        (axs[1], "wtd", "Probability-weighted: dP_run x spread x annuity")):
        for c_, V, dp, col, ls, lab in lines:
            wtp = dp * V / BP * ANNUITY
            rep = sg if rd == "full" else dp * sg * ANNUITY
            ax.plot(sg, np.maximum(0.0, c_ / BP - wtp - rep), color=col, ls=ls, lw=2.0, label=lab)
        ax.set_xlim(0, 80)
        ax.set_ylim(0, cc.REF8 / BP * 1.08)
        ax.set_xlabel("Replacement funding spread s_rep, bps a year", fontsize=9, color=MUTED)
        grid_y(ax)
        ax.set_title(ttl, loc="left", fontsize=10, fontweight="semibold", pad=8)
    axs[0].set_ylabel("Smallest depositor advantage Delta that clears, bps", fontsize=9, color=MUTED)
    axs[0].legend(loc="lower left", bbox_to_anchor=(0.0, -0.42), ncol=3, frameon=False, fontsize=8.2)
    frame(fig, "Replacement funding clears the price only when counted as a ceiling",

          "Three-party clearing: Delta + retention value + replacement value >= all-in assessment",
          SRC + " Retention value as in results_clearing_cost.md, Section 33 (relationship value V over 5 years at r + 3%). " + ILL)
    fig.savefig(FIG(6), dpi=200)
    plt.close(fig)

    # ---- M07: what moves the price ---------------------------------------------------------------------
    names = {"lambda_P": "Default probability 0.10% to 1.00%", "LGD": "LGD 15% to 40%", "rho": "Correlation 0.10 to 0.30",
             "copula": "Gaussian or Student-t(5)", "q_acq": "Acquirer probability 0 to 1", "N": "Members 100 to 200",
             "cap": "Concentration cap 2% to 10%", "demand": "Covered excess sought 20% to 50% of liabilities",
             "sigma": "Member size dispersion sigma 1.0 to 1.5", "theta_m": "Reserve target 2% to 5%",
             "m": "Special assessment cap 0x to 3x", "opp": "Reserve opportunity cost 50 to 150 bps",
             "f_m": "Mutual frictions 2 to 10 bps", "s_lock": "Lock-up premium 5 to 15 bps",
             "f_tail": "Tail frictions 25 to 75 bps per unit of thickness"}
    gs = order_tornado_keys()[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 6.2))
    fig.subplots_adjust(left=0.36, right=0.95, top=0.82, bottom=0.15)
    for i, g in enumerate(gs):
        for k, col, dy in (("ref", NAVY, 0.18), ("alt", ACCENT, -0.18)):
            lo, hi = tornado[(g, k)]
            ax.barh(i + dy, max((hi - lo) / BP, 0.05), 0.32, left=lo / BP, color=col)
    ax.set_xlim(min(v[0] for v in tornado.values()) / BP - 2, max(v[1] for v in tornado.values()) / BP + 2)
    ax.axvline(br["pi"] / BP, color=NAVY, lw=0.9, ls=(0, (1, 1.5)))
    ax.axvline(ba["pi"] / BP, color=ACCENT, lw=0.9, ls=(0, (1, 1.5)))
    ax.set_yticks(range(len(gs)))
    ax.set_yticklabels([names[g] for g in gs], fontsize=8.8)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("All-in assessment, bps a year on covered excess", fontsize=9.5, color=MUTED)
    ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(handles=[Patch(color=NAVY, label="Reference design"), Patch(color=ACCENT, label="Alternative design")],
              loc="lower right", frameon=False, fontsize=8.8)
    frame(fig, "The default probability and the tail's frictions move the price most",
          "Range of the all-in assessment across each one-at-a-time sweep, X held; dotted lines are the base case",
          SRC + f" Base: {PB.n} members, cap {CAP_BASE:.0%}, theta_m {THETA_M:.0%}, m {M_SA}, default probability 0.25%, LGD 25%, correlation 0.20, Gaussian, q_acq {Q_ACQ:.1f}.\n" + ILL)
    fig.savefig(FIG(7), dpi=200)
    plt.close(fig)

    # ---- M08: rule M against rule B ---------------------------------------------------------------------
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(10.5, 5.6))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.76, bottom=0.25, wspace=0.3)
    axl.plot(LGD_GRID * 100, cash_rule["B"] * 100, color=NAVY, lw=2.2, label="Rule B: par less the advance dividend, day seven")
    axl.plot(LGD_GRID * 100, cash_rule["M"] * 100, color=ACCENT, lw=2.2, label="Rule M: the loss, paid at closure")
    axl.set_xlabel("LGD in the failure state, %", fontsize=9, color=MUTED)
    axl.set_ylabel("Cash per unit of the failed member's covered excess", fontsize=9, color=MUTED)
    axl.yaxis.set_major_formatter(pctfmt(0))
    axl.set_ylim(0, 70)
    grid_y(axl)
    axl.legend(loc="upper left", frameon=False, fontsize=8.3)
    axl.set_title("Cash each failure needs", loc="left", fontsize=10.5, fontweight="semibold", pad=8)
    qx = np.arange(len(Q_SET))
    for j, (cop, cn) in enumerate(COPULAS):
        vals = [rel_q[(q, cop)]["short"] * 100 for q in Q_SET]
        x = qx + (j - 0.5) * 0.36
        axr.bar(x, vals, 0.34, color=NAVY if cop == "gauss" else ACCENT, label=cn)
        for xx, v in zip(x, vals):
            axr.text(xx, v, f"{v:.1f}" if v >= 1 else f"{v:.2f}", ha="center", va="bottom", fontsize=7.8)
    axr.set_xticks(qx)
    axr.set_xticklabels(["Rule B\nonly" if q == 0 else "Rule M\nonly" if q == 1 else f"q_acq\n{q:.2f}" for q in Q_SET], fontsize=8.5)
    axr.tick_params(axis="x", length=0)
    axr.yaxis.set_major_formatter(pctfmt(0))
    axr.set_ylabel("P(not paid in full | median member fails)", fontsize=9, color=MUTED)
    grid_y(axr)
    axr.legend(loc="upper right", frameon=False, fontsize=8.5)
    axr.set_title(f"Reliability of the reference design (X {pcs(X_REF, 1)})", loc="left", fontsize=10.5, fontweight="semibold", pad=8)
    frame(fig, "Paying the loss at closure needs less cash than paying par less the dividend",
          "Rule M (an acquirer takes every deposit, the stack pays the loss) against rule B (the clearing-cost engine's day-seven settlement)",
          SRC + f" Right panel: {PB.n} members, default probability 0.25%, correlation 0.30, state-dependent LGD, X held at the reference value;\n"
          "the acquirer outcome drawn once a year. " + ILL)
    fig.savefig(FIG(8), dpi=200)
    plt.close(fig)

    # ---- M09: replenishment after a loss year -----------------------------------------------------------
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(10.5, 5.6))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.76, bottom=0.27, wspace=0.3)
    for rp, col in zip(REPL_SET, (SLATE, STEEL, NAVY)):
        axl.plot(range(1, PATH_YEARS + 1), [v * 100 for v in paths[("gauss", RHO_PRICE, rp)]["below"]], color=col, lw=2.0,
                 marker="o", ms=3.5, label=f"Replenish over {rp} year{'s' if rp > 1 else ''}")
    axl.set_xlabel("Year", fontsize=9, color=MUTED)
    axl.set_ylabel("P(reserve below target at year end)", fontsize=9, color=MUTED)
    axl.yaxis.set_major_formatter(pctfmt(0))
    axl.set_xticks(range(1, PATH_YEARS + 1))
    axl.set_ylim(bottom=0)
    grid_y(axl)
    axl.legend(loc="center right", frameon=False, fontsize=8.5)
    axl.set_title("Below target, ten-year paths", loc="left", fontsize=10.5, fontweight="semibold", pad=8)
    codes = [c for c, _, _ in y2_regimes]
    for j, (cop, cn) in enumerate(COPULAS):
        base_v = y1_ref[cop]["short"] * 100
        vals = [y2[(cop, c)]["short"] * 100 / base_v for c in codes]
        x = np.arange(len(codes)) + (j - 0.5) * 0.36
        axr.bar(x, vals, 0.34, color=NAVY if cop == "gauss" else ACCENT, label=f"{cn} (Year 1: {fp(y1_ref[cop]['short'])})")
        for xx, v, c in zip(x, vals, codes):
            axr.text(xx, v, fp(y2[(cop, c)]["short"]), ha="center", va="bottom", fontsize=7, rotation=90)
    axr.axhline(1.0, color=INK, lw=0.9, ls=(0, (4, 2)))
    axr.set_xticks(range(len(codes)))
    axr.set_xticklabels(["Not\nrestored", "Special\nassessment", "+ 1/5", "+ 1/3", "Fully\nrestored"], fontsize=8.5)
    axr.tick_params(axis="x", length=0)
    axr.set_ylabel("Year-2 shortfall relative to Year 1", fontsize=9, color=MUTED)
    axr.set_ylim(0, max(y2[(cop, c)]["short"] / y1_ref[cop]["short"] for cop, _ in COPULAS for c in codes) * 1.35)
    grid_y(axr)
    axr.legend(loc="upper right", frameon=False, fontsize=8.3)
    axr.set_title("Year 2 after a 2023-like cluster", loc="left", fontsize=10.5, fontweight="semibold", pad=8)
    frame(fig, "Slower replenishment leaves the reserve short more often, but costs little reliability",
          "Left: reserve paths from target. Right: P(not paid in full | median member fails) in Year 2 against Year 1",
          SRC + f" Gaussian copula, correlation 0.20 (left) and 0.30 (right), state-dependent LGD, mixed settlement. The cluster: three members of\n"
          f"about base weight, two settled under rule B and one under rule M, {pcs(Y1_PAY, 2)} of cash. " + ILL)
    fig.savefig(FIG(9), dpi=200)
    plt.close(fig)


# =============================================================================
# 15. RUN
# =============================================================================
if __name__ == "__main__":
    import matplotlib
    FIGURES.mkdir(parents=True, exist_ok=True)
    make_figures()
    elapsed = time.perf_counter() - _T_START
    mins = max(1, int(elapsed / 60 + 0.5))
    meta = dict(python=sys.version.split()[0], numpy=np.__version__, matplotlib=matplotlib.__version__,
                runtime=f"about {mins} minute{'s' if mins > 1 else ''}")
    write_results(meta)
    for k, nm, X in DESIGNS:
        b = base[k]
        print(f"{nm:38s} X {pcs(X, 1)}  A {pcs(b['A'], 3)}  T {pcs(b['T'], 3)}  mutual {b2(b['mutual'])}  "
              f"tail {b2(b['tail'])}  all-in {b2(b['pi'])} bps")
    print(f"Parity with the clearing-cost engine: {'PASS' if PARITY_OK else 'FAIL'}; Monte Carlo check {'PASS' if MC_CHECK_OK else 'FAIL'}; "
          f"mix check max rel diff {MIX_CHECK_MAX:.1e}")
    print(f"Wrote {RESULTS_MD}")
    for n in range(1, N_FIGS + 1):
        print(f"Wrote {FIG(n)}")
    print(f"Run time {time.perf_counter() - _T_START:.1f} s")
