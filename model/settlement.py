"""
settlement.py (Cash That Never Sleeps, Chapter 6): the settlement clock of the always-on netting facility (route R7).

What it does
    Deepens the routes engine's treatment of the always-on collateralized netting facility in six analyses:
    A  a same-weekend one-factor model of cap binding (Gaussian and Student-t(5) copulas), the queued amount, a cap
       ladder (the backing a member needs to hold its bind frequency at a target, priced) and a median sensitivity;
    B  the closed-window calendar of the Fedwire Funds Service (weekday gaps, weekends, three-day weekends, midweek
       holidays), bind frequency by window, two sizing policies, three schedule scenarios and a daylight-saving check;
    C  a liquidity-buffer sensitivity, with the lendable-share screen S2 kept on the absolute convention;
    D  the price for a non-member reaching the facility through a sponsoring member;
    E  the Monday cash gap of net creditors when a member is closed over a weekend, on the legal stay interval and on
       the operational collateral-to-cash interval;
    F  the Sunday settlement cash source: reserves or collateralized Reserve Bank daylight credit at the Sunday opening.

The simulated variable
    Each member's weekend figure is its PEAK net debit during the closed window to all counterparties, members and
    non-members, as a share of its always-on tier; the lognormal is the distribution of that peak, not of the terminal
    net position. Per-member results (bind probability, the cap ladder's per-member rows, the median boundary) are the
    headline, conditional on the assumed distribution. Every multi-member statistic (system queue, joint cap ladder,
    any-binds, a quarter or more binding, the pooled cap, the system-average secured debit) describes an OPEN debtor
    cohort: M members drawn as net debtors whose receivers sit outside the modelled set. It is not a closed-membership
    result, in which signed net positions would sum to zero.

Imports (by path with importlib, never copied)
    model/routes.py  the routes engine (Chapters 4 to 7); it loads the clearing-cost and mutual-tail engines itself.
                     Its main block is guarded, so importing it computes its tables and writes nothing.
Outputs  model/results_settlement.md; figures/settlement/fig-S01.png to fig-S03.png.
Needs    Python 3.9 or later (zoneinfo, with the America/New_York time zone available) for the daylight-saving check.
Run      python -I -B model/settlement.py   (from the repository root)
         --s2-min BAR runs at an S2 bar of BAR (default 0.90, the rule of record); routes.py reads the same flag on
         import. The S2 bar sensitivity of the cap-ladder boundary (Table A6) is computed in every run.
Seeds    20261120 (same-weekend Monte Carlo). The imported engines carry their own seeds. Results are deterministic; the
         run time is printed to the console only.

All parameters are illustrative and calibrated to no bank. Parameters not imported from routes.py are labelled
"author assumption (illustrative)" in the results file.
"""

import sys
import time
import math
import argparse
import platform
import importlib.util
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

_T_START = time.perf_counter()
sys.dont_write_bytecode = True                       # importing the engines must leave nothing in their folders

HERE = Path(__file__).resolve().parent               # model/
ROOT = HERE.parent                                   # repository root
RESULTS_MD = HERE / "results_settlement.md"
ROUTES_MD = HERE / "results_routes.md"               # read only, for the parity check
FIGURES = ROOT / "figures" / "settlement"
SCRIPT_NAME = "settlement.py"
N_FIGS = 3
FIG = lambda n: FIGURES / f"fig-S{n:02d}.png"


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
    _ap = argparse.ArgumentParser(description="Cash That Never Sleeps: the settlement clock of the netting facility.")
    _ap.add_argument("--s2-min", type=float, default=None, help="lendable-share bar of screen S2 (default 0.90, the rule "
                     "of record); routes.py reads the same flag on import")
    _ap.parse_args()

rt = _load("routes", HERE / "routes.py")
cc = rt.cc
import numpy as np                                   # noqa: E402

_ND = cc._ND
date = dt.date

# =============================================================================
# 0. CALENDAR CONSTANTS: Fedwire Funds hours and Reserve Bank holidays (reported figures, accessed 3 November 2026).
#    Correct them here if the published schedule changes; nothing else in the file needs to change.
# =============================================================================
FEDWIRE_OPEN_HOUR_PREV_DAY = 21     # opens 9:00 p.m. ET on the preceding calendar day, holidays included
                                    # [reported figure, Federal Reserve Financial Services, Fedwire Funds Service operating hours]
FEDWIRE_CLOSE_HOUR = 19             # closes 7:00 p.m. ET [reported figure, same page]
QFC_STAY_END_HOUR = 17              # stay on termination, liquidation and netting rights ends 5:00 p.m. ET on the business
                                    # day after appointment [12 U.S.C. 1821(e)(10)(B)(i); business day in 1821(e)(10)(D)]
SEC_OPEN_HOUR = 8.5                 # Fedwire Securities Service opens 8:30 a.m. ET [reported figure, Federal Reserve
                                    # Financial Services, Fedwire Securities Service schedule]
SEC_CUTOFF_HOUR = 15.25             # secondary-market transfer cutoff 3:15 p.m. ET (3:30 is for reversals and repo
                                    # adjustments) [reported figure, same schedule]
TZ_NY = "America/New_York"          # for the elapsed-hours (daylight-saving) check only; the schedule convention is
                                    # nominal Eastern clock hours
HOLIDAYS_2025_TAIL = [date(2025, 12, 25)]            # only the boundary into 2026 matters
HOLIDAYS_2026 = [                                    # Jul 4 is a Saturday: Reserve Banks open Friday, no weekday closing
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 5, 25), date(2026, 6, 19),
    date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 11), date(2026, 11, 26), date(2026, 12, 25)]
HOLIDAYS_2027 = [                                    # Jun 19 and Dec 25 are Saturdays: open Friday; Jul 4 Sunday: closed Monday
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 5, 31), date(2027, 7, 5),
    date(2027, 9, 6), date(2027, 10, 11), date(2027, 11, 11), date(2027, 11, 25)]
HOLIDAYS_SRC = "Federal Reserve Financial Services, holiday schedules, accessed 3 November 2026"
HOURS_SRC = "Federal Reserve Financial Services, Fedwire Funds Service and NSS operating hours, accessed 3 November 2026"
SIX_DAY_SRC = "90 FR 51356, 17 November 2025"
HOLIDAYS = set(HOLIDAYS_2025_TAIL + HOLIDAYS_2026 + HOLIDAYS_2027)   # Jan 1 2028 is a Saturday: Dec 31 2027 open
YEARS = [2026, 2027]
WEEKDAYS_CURRENT = (0, 1, 2, 3, 4)                   # Monday to Friday (datetime weekday numbers)
WEEKDAYS_SUN_FRI = (6, 0, 1, 2, 3, 4)                # announced 22x6: Sunday to Friday, weekday holidays open
WEEKDAYS_SEVEN = (0, 1, 2, 3, 4, 5, 6)

# =============================================================================
# 1. PARAMETERS
# =============================================================================
BP = rt.BP
# --- imported from routes.py (re-checked in Section 2 of the results) ------------------------------------------
R7_SHARE, R7_HAIRCUT = rt.R7_SHARE, rt.R7_HAIRCUT
R7_OUT_MED, R7_OUT_SIG, SIG_SET = rt.R7_OUT_MED, rt.R7_OUT_SIG, list(rt.R7_OUT_SIG_SET)
R7_CREDIT, R7_ACCESS, R7_ENC, R7_FRIC = rt.R7_CREDIT, rt.R7_ACCESS, rt.R7_ENC, rt.R7_FRIC
R7_WEEKENDS, R7_SHARE_SET = rt.R7_WEEKENDS, list(rt.R7_SHARE_SET)
S2_MIN = rt.S2_MIN
LAMBDA_P = rt.LAMBDA_P                               # real-world annual default intensity (clearing-cost engine)
R7_LO, R7_HI, R7_BASE, R7_LEND = rt.R7_LO, rt.R7_HI, rt.R7_BASE, rt.R7_LEND
r7_price, r7_terms, p_bind = rt.r7_price, rt.r7_terms, rt.p_bind
NU = cc.V5_T_NU                                      # Student-t degrees of freedom, the clearing-cost engine's
# --- A. same-weekend factor model [author assumption (illustrative)] -------------------------------------------
M_SET = [10, 20, 40]
M_BASE = 20
RHO_SET = [0.0, 0.15, 0.30, 0.50]                    # pairwise latent correlation
RHO_REF = 0.30
COPULAS = ["gauss", "t"]
COP_NAME = {"gauss": "Gaussian", "t": f"Student-t({NU})"}
MC_N, MC_CHUNK, MC_SEED = 500_000, 50_000, 20261120
TARGETS = [("1% of weekends", 0.01), ("once in ten years (1 in 520 weekends)", 1.0 / (10 * R7_WEEKENDS))]
Q_YEAR = 0.99 ** (1.0 / R7_WEEKENDS)                 # weekly quantile equal to the 99th percentile of a 52-weekend max
# --- B. calendar [author assumption (illustrative)] -------------------------------------------------------------
H_REF = 50                                           # the normal weekend the routes engine's outflow describes
SCALINGS = ["linear", "sqrt"]                        # outflow median scales with hours / 50, or its square root
# --- C. liquidity buffer [author assumption (illustrative)] ----------------------------------------------------
BUFFER_SET = [0.0, 0.05, 0.10, 0.20, 0.40]
CUSTODY = (0.0, 5 * BP)                              # custody-and-positioning spread on bills drawn from the buffer
# --- D. sponsored non-member [author assumption (illustrative)] ----------------------------------------------
D_SHARES = [0.05, 0.10, 0.20]
SPONSOR_MARGIN = (2 * BP, 6 * BP)                    # per always-on tier dollar of the non-member
SPONSOR_ACCESS = (1 * BP, 3 * BP)                    # sponsor's own extra access cost, on the non-member's whole balance
# --- E. Monday cash [author assumption (illustrative)] ---------------------------------------------------------
SECURED_RATE = 0.043                                 # overnight secured rate
BRIDGE_SPREAD = (10 * BP, 50 * BP)
GAP_H_NORMAL = 20                                    # legal stay interval: scheduled Fedwire opening to the end of the stay,
                                                     # Sunday 21:00 to Monday 17:00; after a Monday holiday, Monday 21:00 to
                                                     # Tuesday 17:00
# operational collateral-to-cash interval: the stay ends after the securities cutoff, so collateral can be delivered
# against cash only when Fedwire Securities next opens: Sunday 21:00 to Tuesday 8:30 (35.5 hours)
GAP_H_OPER = (24 - FEDWIRE_OPEN_HOUR_PREV_DAY) + 24 + SEC_OPEN_HOUR
# --- F. Sunday settlement cash source -------------------------------------------------------------------------
DOD_FEE = 0.0                                        # DAYLIGHT OVERDRAFT FEE, collateralized: 0 bps a year [reported
                                                     # figure, Federal Reserve Policy on Payment System Risk]
DOD_FEE_SET = [0.0, 50 * BP]                         # 50 bps a year: uncollateralized overdrafts (disclosed sensitivity)
PSR_YEAR_DAYS = 360                                  # the fee is quoted on a 24-hour day and a 360-day year; the
PSR_DAILY_DP = 7                                     # effective daily rate (annual / 360) is truncated, 0.0000138 at
                                                     # 50 bps [reported figure, Federal Reserve Policy on Payment System
                                                     # Risk, Section II.C and footnote 58]
DOD_REPAY_HOUR = 12                                  # overdraft from Sunday 21:00 repaid by Monday 12:00 ET: a solvent
                                                     # debtor repays from a delivery-versus-payment sale or bilateral
                                                     # repo of its bills settling Monday morning after the 8:30
                                                     # securities opening [author assumption (illustrative)]
H_SEC_GAP = 24 * 3 + SEC_OPEN_HOUR - SEC_CUTOFF_HOUR       # Friday 15:15 to Monday 8:30: no bill can become reserves


# =============================================================================
# 2. NUMERICAL HELPERS
# =============================================================================
_A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02,
      -3.066479806614716e+01, 2.506628277459239e+00]
_B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01,
      -1.328068155288572e+01]
_C = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00,
      4.374664141464968e+00, 2.938163982698783e+00]
_D = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]


def ninv(p):
    """Vectorized inverse standard normal (Acklam's rational approximation, relative error below 1.2e-9)."""
    p = np.clip(np.asarray(p, dtype=float), 1e-300, 1 - 1e-16)
    x = np.empty_like(p)
    lo, hi = p < 0.02425, p > 1 - 0.02425
    mid = ~(lo | hi)
    q = p[mid] - 0.5
    r = q * q
    x[mid] = ((((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q /
              (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1))
    for mask, sgn, pp in ((lo, 1.0, p[lo]), (hi, -1.0, 1 - p[hi])):
        q = np.sqrt(-2 * np.log(pp))
        x[mask] = sgn * ((((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) /
                         ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1))
    return x


def tcdf(x, nu=NU):
    """Student-t cdf for odd nu, closed form: 1/2 + (1/pi)[theta + sin(theta) * sum of cos powers]."""
    if nu % 2 != 1:
        raise ValueError("closed-form t cdf implemented for odd degrees of freedom only")
    th = np.arctan(np.asarray(x, dtype=float) / math.sqrt(nu))
    c, s = np.cos(th), np.sin(th)
    acc = np.zeros_like(th)
    if nu > 1:
        term = c.copy()
        acc = term.copy()
        for k in range(1, (nu - 3) // 2 + 1):
            term = term * c * c * (2 * k) / (2 * k + 1)
            acc = acc + term
    return 0.5 + (th + s * acc) / math.pi


def t_upper_quantile(p, nu=NU):
    """t with P(T > t) = p, by bisection on the closed-form cdf."""
    lo, hi = -50.0, 1e4
    for _ in range(200):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if 1.0 - float(tcdf(m, nu)) > p else (lo, m)
    return 0.5 * (lo + hi)


def ptail(x):
    """P(Z > x), standard normal."""
    return _ND.cdf(-x)


def pct(x, nd=2):
    return f"{x * 100:.{nd}f}%"


def psig(x):
    """Probability as a percentage with three significant figures, without scientific notation."""
    if x <= 0:
        return "0"
    v = x * 100
    if v < 0.0001:
        return "below 0.0001%"
    nd = max(0, 2 - int(math.floor(math.log10(v))))
    return f"{v:.{nd}f}%"


def b1(x):
    return f"{x / BP + 1e-12:.1f}"


def b2(x):
    return f"{x / BP + 1e-12:.2f}"


def rng_b(lo, hi):
    return f"{b1(lo)} to {b1(hi)}"


def table(header, rows):
    esc = lambda c: str(c).replace("|", "\\|")
    return cc.table([esc(h) for h in header], [[esc(c) for c in r] for r in rows])


def passes_s2(lend):
    return lend >= S2_MIN - 1e-12


def s2_txt(lend):
    return "pass" if passes_s2(lend) else "fail"


def price_rng(share):
    return r7_price(share, 0), r7_price(share, 1)


# =============================================================================
# 3. A. SAME-WEEKEND FACTOR MODEL
# =============================================================================
def quarter(M):
    return math.ceil(M / 4)


def count_pmf(pd, rho, M, cop):
    """Distribution of the number of members whose cap binds on one weekend, by quadrature over the factor
    (Gaussian) or the factor and the chi-square mixing variable (Student-t), each member's bind probability pd."""
    if cop == "gauss":
        if rho == 0:
            p = np.array([pd])
            w = np.array([1.0])
        else:
            c = _ND.inv_cdf(pd)
            p = cc.ncdf((c - math.sqrt(rho) * cc._Z5) / math.sqrt(1 - rho))
            w = cc._WZ5
    else:
        _, w, p, _ = cc._t_nodes(pd, rho)
    return w @ cc._binom_rows(p, M)


def p_atleast(pmf, k):
    return float(pmf[k:].sum())


P_MEMBER = {sg: p_bind(sg) for sg in SIG_SET}        # per-member bind probability, copula invariant
PMF = {}
for cop in COPULAS:
    for rho in RHO_SET:
        for M in M_SET:
            for sg in SIG_SET:
                PMF[(cop, rho, M, sg)] = count_pmf(P_MEMBER[sg], rho, M, cop)


def run_mc():
    """Monte Carlo of MC_N weekends: queued amount, bind counts, secured debit, and a two-member pooled cap."""
    rng = np.random.default_rng(MC_SEED)
    mmax = max(M_SET)
    keys = [(c, r, M, s) for c in COPULAS for r in RHO_SET for M in M_SET for s in SIG_SET]
    qs = {k: [] for k in keys}
    ks = {k: [] for k in keys}
    sec, pair_pool, pair_sep, done = [], 0, 0, 0
    while done < MC_N:
        n = min(MC_CHUNK, MC_N - done)
        F = rng.standard_normal(n)
        W = rng.chisquare(NU, n)
        E = rng.standard_normal((n, mmax))
        scale_t = np.sqrt(NU / W)[:, None]
        for rho in RHO_SET:
            L = math.sqrt(rho) * F[:, None] + math.sqrt(1 - rho) * E
            for cop in COPULAS:
                Z = L if cop == "gauss" else ninv(tcdf(L * scale_t))
                for sg in SIG_SET:
                    X = R7_OUT_MED * np.exp(sg * Z)
                    over = np.clip(X - 1.0, 0.0, None)
                    bind = X > 1.0
                    for M in M_SET:
                        qs[(cop, rho, M, sg)].append((over[:, :M].sum(axis=1) / M).astype(np.float32))
                        ks[(cop, rho, M, sg)].append(bind[:, :M].sum(axis=1).astype(np.int8))
                    if cop == "gauss" and rho == RHO_REF and sg == R7_OUT_SIG:
                        sec.append(np.minimum(X[:, :M_BASE], 1.0).mean(axis=1))
                        pair_pool += int(((X[:, 0] + X[:, 1]) > 2.0).sum())
                        pair_sep += int(((X[:, 0] > 1.0) | (X[:, 1] > 1.0)).sum())
        done += n
    out = {}
    for k in keys:
        q = np.concatenate(qs[k]).astype(float)
        kk = np.concatenate(ks[k]).astype(int)
        M = k[2]
        out[k] = dict(q_mean=float(q.mean()), q99=float(np.quantile(q, 0.99)), q99y=float(np.quantile(q, Q_YEAR)),
                      p1=float((kk >= 1).mean()), p3=float((kk >= 3).mean()), pq=float((kk >= quarter(M)).mean()),
                      pm=float(kk.sum() / (MC_N * M)), pm_se=float((kk / M).std() / math.sqrt(MC_N)))
    s = np.concatenate(sec)
    return out, dict(sec99=float(np.quantile(s, 0.99)), sec_mean=float(s.mean()), pair_pool=pair_pool / MC_N,
                     pair_sep=pair_sep / MC_N)


MC, MC_X = run_mc()


def mc_z(mc, an):
    se = math.sqrt(max(an * (1 - an), 1e-300) / MC_N)
    return (mc - an) / se


# --- cap ladder ---------------------------------------------------------------------------------------------
def backing_for(pd, sig=R7_OUT_SIG):
    """Always-on share a member must back (cap = backing) so that its per-member bind probability is pd, the weekend
    outflow in balance terms held at the routes engine's (median R7_OUT_MED x R7_SHARE of the tokenized balance)."""
    mult = math.exp(sig * -_ND.inv_cdf(pd))
    return mult, mult * R7_OUT_MED * R7_SHARE


def solve_pd(target, k, M, rho, cop):
    """Per-member bind probability at which P(at least k of M bind on a weekend) equals target."""
    lo, hi = math.log(1e-10), math.log(0.6)
    for _ in range(36):
        m = 0.5 * (lo + hi)
        lo, hi = (m, hi) if p_atleast(count_pmf(math.exp(m), rho, M, cop), k) < target else (lo, m)
    return math.exp(0.5 * (lo + hi))


LADDER = []
for tname, tv in TARGETS:
    mult, bk = backing_for(tv)
    LADDER.append(dict(target=tname, crit="per member", cop="any", rho=None, pd=tv, mult=mult, back=bk))
    for crit, kf in (("at least 1 of 20", lambda M: 1), ("at least a quarter (5 of 20)", quarter)):
        for cop in COPULAS:
            for rho in RHO_SET:
                pd = solve_pd(tv, kf(M_BASE), M_BASE, rho, cop)
                mult, bk = backing_for(pd)
                LADDER.append(dict(target=tname, crit=crit, cop=COP_NAME[cop], rho=rho, pd=pd, mult=mult, back=bk))
for row in LADDER:
    row["lo"], row["hi"] = price_rng(row["back"])
    row["lend"] = 1.0 - row["back"]
LADDER_PASS = [r for r in LADDER if passes_s2(r["lend"])]
# the largest median weekend outflow (share of the tokenized balance) compatible with S2 at each per-member target
S2_MED = [(sg, tname, (1.0 - S2_MIN) / math.exp(sg * -_ND.inv_cdf(tv))) for sg in SIG_SET for tname, tv in TARGETS]
S2_MED_P = {sg: ptail(math.log((1.0 - S2_MIN) / (R7_OUT_MED * R7_SHARE)) / sg) for sg in SIG_SET}
# median sensitivity: per-member bind probability at a cap of 10% of the balance (the largest S2 allows), and the
# cap a 1%-of-weekends per-member bind needs, by the median peak debit (share of the balance) and sigma
MED_SET = [0.01, 0.015, 0.02, 0.03, 0.05]
CAP_S2 = 1.0 - S2_MIN
MED_SENS = [dict(sig=sg, med=m, p10=ptail(math.log(CAP_S2 / m) / sg), cap1=m * math.exp(sg * -_ND.inv_cdf(0.01)))
            for sg in SIG_SET for m in MED_SET]
# S2 bar sensitivity of the cap-ladder boundary (Table A6): at each bar the largest cap S2 allows is c = 1 - bar (the
# routes engine's convention), or c (1 - haircut) counting the grossed-up bills as non-lendable (Section 9's
# convention line); the largest median peak debit that keeps a member's cap binding in at most 1% of weekends is
# c / exp(sigma z_0.99), and the cap test passes at the assumed median if that boundary is at least the median
S2_MED_BAR_TARGET = 0.01
_MED_ASSUMED = R7_OUT_MED * R7_SHARE
S2_MED_BAR = []
for _bar in rt.S2_BARS:
    for sg in SIG_SET:
        _c = 1.0 - _bar
        _cg = _c * (1.0 - R7_HAIRCUT)
        _m = math.exp(sg * -_ND.inv_cdf(S2_MED_BAR_TARGET))
        S2_MED_BAR.append(dict(bar=_bar, sig=sg, c=_c, cg=_cg, med=_c / _m, med_g=_cg / _m,
                               p=ptail(math.log(_c / _MED_ASSUMED) / sg)))
_S2_MED_CHECK = max(abs(r["med"] - m) for r in S2_MED_BAR for sg, tn, m in S2_MED
                    if abs(r["bar"] - S2_MIN) < 1e-12 and sg == r["sig"] and tn == TARGETS[0][0]) if any(
    abs(b - S2_MIN) < 1e-12 for b in rt.S2_BARS) else 0.0
if _S2_MED_CHECK > 1e-12:
    raise RuntimeError("Table A6 at this run's bar must reproduce Table A4")


# =============================================================================
# 4. B. CLOSED-WINDOW CALENDAR
# =============================================================================
def operating_days(year, weekdays, holidays_closed):
    d, end, out = date(year - 1, 12, 1), date(year, 12, 31), []
    while d <= end:
        if d.weekday() in weekdays and not (holidays_closed and d in HOLIDAYS):
            out.append(d)
        d += dt.timedelta(days=1)
    return out


_NY = ZoneInfo(TZ_NY)


def elapsed_h(a, b):
    """Elapsed hours from the close on operating day a (19:00 ET) to the opening for operating day b (21:00 ET on the
    calendar day before b), with America/New_York offsets, measured in UTC."""
    o = b - dt.timedelta(days=1)
    st = dt.datetime(a.year, a.month, a.day, FEDWIRE_CLOSE_HOUR, tzinfo=_NY).astimezone(dt.timezone.utc)
    en = dt.datetime(o.year, o.month, o.day, FEDWIRE_OPEN_HOUR_PREV_DAY, tzinfo=_NY).astimezone(dt.timezone.utc)
    return (en - st).total_seconds() / 3600


def windows(year, weekdays=WEEKDAYS_CURRENT, holidays_closed=True):
    """Every closed window that ends at an operating day of the given year (each operating day is preceded by one).
    'hours' is the nominal schedule length (the convention); 'elapsed' adds the daylight-saving offset."""
    ops = operating_days(year, weekdays, holidays_closed)
    out = []
    for a, b in zip(ops, ops[1:]):
        if b.year != year:
            continue
        hours = 24 * ((b - a).days - 1) + FEDWIRE_OPEN_HOUR_PREV_DAY - FEDWIRE_CLOSE_HOUR
        start = dt.datetime(a.year, a.month, a.day, FEDWIRE_CLOSE_HOUR)
        out.append(dict(start=start, hours=hours, elapsed=elapsed_h(a, b), prev=a, next=b))
    span_h = (dt.datetime(ops[-1].year, ops[-1].month, ops[-1].day, FEDWIRE_CLOSE_HOUR)
              - dt.datetime(out[0]["prev"].year, out[0]["prev"].month, out[0]["prev"].day,
                            FEDWIRE_CLOSE_HOUR)).total_seconds() / 3600
    n_ops = sum(1 for d in ops if d.year == year)
    return out, n_ops, span_h


WTYPE = {2: "Weekday evening gap", 26: "Midweek holiday", 50: "Normal weekend", 74: "Three-day weekend"}


def wtype(h):
    return WTYPE.get(h, f"Longer window ({h} hours)" if h > 74 else f"Other ({h} hours)")


def g_scale(h, scaling):
    return h / H_REF if scaling == "linear" else math.sqrt(h / H_REF)


def p_win(h, backing=R7_SHARE, scaling="linear", sig=R7_OUT_SIG):
    """P(cap binds over a closed window of h hours) at a given backing; outflow median scales with the hours."""
    med = R7_OUT_MED * (R7_SHARE / backing) * g_scale(h, scaling)
    return ptail(math.log(1.0 / med) / sig)


CAL = {}
for y in YEARS:
    ws, n_ops, span = windows(y)
    hrs = sorted({w["hours"] for w in ws})
    rows = [(h, sum(1 for w in ws if w["hours"] == h)) for h in hrs]
    for h in (2, 26, 50, 74):
        if h not in hrs:
            rows.append((h, 0))
    rows.sort()
    CAL[y] = dict(ws=ws, n_ops=n_ops, span=span, rows=rows, hmax=max(hrs), total=sum(w["hours"] for w in ws),
                  weekends=sum(1 for w in ws if any((w["prev"] + dt.timedelta(days=i)).weekday() == 5
                                                    for i in range(1, (w["next"] - w["prev"]).days))))
CAL_CHECK = max(abs(CAL[y]["total"] + 22 * CAL[y]["n_ops"] - CAL[y]["span"]) for y in YEARS)


def binds_year(ws, backing, scaling, key="hours"):
    ps = [p_win(w[key], backing, scaling) for w in ws]
    return sum(ps), 1.0 - math.prod(1.0 - p for p in ps)


ROUTES_BINDS = R7_WEEKENDS * p_bind(R7_OUT_SIG)
ROUTES_YEAR = 1.0 - (1.0 - p_bind(R7_OUT_SIG)) ** R7_WEEKENDS
P1 = {}
P2 = {}
for y in YEARS:
    for sc in SCALINGS:
        P1[(y, sc)] = binds_year(CAL[y]["ws"], R7_SHARE, sc)
        bk = R7_SHARE * g_scale(CAL[y]["hmax"], sc)
        P2[(y, sc)] = dict(back=bk, lo=r7_price(bk, 0), hi=r7_price(bk, 1), lend=1.0 - bk,
                           binds=binds_year(CAL[y]["ws"], bk, sc))
HOL_RATIO = {sc: {h: p_win(h, scaling=sc) / p_win(H_REF, scaling=sc) for h in (26, 74)} for sc in SCALINGS}
# daylight-saving check: windows whose elapsed hours differ from the nominal schedule hours
DST_ROWS = [(y, w) for y in YEARS for w in CAL[y]["ws"] if abs(w["elapsed"] - w["hours"]) > 1e-9]
EL_TOTAL = {y: sum(w["elapsed"] for w in CAL[y]["ws"]) for y in YEARS}
P1_EL = {(y, sc): binds_year(CAL[y]["ws"], R7_SHARE, sc, "elapsed") for y in YEARS for sc in SCALINGS}
P2_EL = {(y, sc): R7_SHARE * g_scale(max(w["elapsed"] for w in CAL[y]["ws"]), sc) for y in YEARS for sc in SCALINGS}

SCEN_DEF = [("Current: Monday to Friday, Reserve Bank holidays closed", WEEKDAYS_CURRENT, True),
            (f"Announced 22x6 schedule ({SIX_DAY_SRC}), not yet in effect: Sunday to Friday, weekday holidays open",
             WEEKDAYS_SUN_FRI, False),
            ("Seven days (hypothetical): every day open", WEEKDAYS_SEVEN, False)]
SCEN = []
for name, wd, hol in SCEN_DEF:
    ws, n_ops, _ = windows(2026, wd, hol)
    hcount = {}
    for w in ws:
        hcount[w["hours"]] = hcount.get(w["hours"], 0) + 1
    wk = [w["hours"] for w in ws if any((w["prev"] + dt.timedelta(days=i)).weekday() == 5
                                        for i in range(1, (w["next"] - w["prev"]).days))]
    h_week = max(set(wk), key=wk.count) if wk else min(hcount)          # modal window that spans a Saturday
    h_max = max(hcount)
    rec = dict(name=name, hcount=hcount, h_week=h_week, h_max=h_max, ws=ws)
    for key in ("hours", "elapsed"):
        h_mx = max(w[key] for w in ws)
        for sc in SCALINGS:
            bk_max = R7_SHARE * g_scale(h_mx, sc)                       # longest window at P1's per-window rate
            lo, hi = 1e-4, 1.0                                          # expected binds a year = routes engine's
            for _ in range(80):
                m = 0.5 * (lo + hi)
                lo, hi = (m, hi) if binds_year(ws, m, sc, key)[0] > ROUTES_BINDS else (lo, m)
            for tag, bk in (("max", bk_max), ("year", 0.5 * (lo + hi))):
                rec[(tag, sc) if key == "hours" else (tag, sc, "el")] = dict(
                    back=bk, lo=r7_price(bk, 0), hi=r7_price(bk, 1), lend=1.0 - bk, binds=binds_year(ws, bk, sc, key)[0])
    rec["binds_p1"] = binds_year(ws, R7_SHARE, "linear")[0]
    rec["dst_n"] = sum(1 for w in ws if abs(w["elapsed"] - w["hours"]) > 1e-9)
    SCEN.append(rec)
# printed figures under nominal hours (the convention) and under elapsed hours, at their printed precision
DST_CMP = []
for y in YEARS:
    for sc in SCALINGS:
        DST_CMP.append((f"Calendar {y}, P1, expected binds a year ({sc})", f"{P1[(y, sc)][0]:.2f}", f"{P1_EL[(y, sc)][0]:.2f}"))
        DST_CMP.append((f"Calendar {y}, P1, P(at least one bind in the year) ({sc})", pct(P1[(y, sc)][1], 1),
                        pct(P1_EL[(y, sc)][1], 1)))
        DST_CMP.append((f"Calendar {y}, P2 backing ({sc})", pct(P2[(y, sc)]["back"], 1), pct(P2_EL[(y, sc)], 1)))
for r_ in SCEN:
    nm = r_["name"].split(":")[0].split(" (")[0]
    for tag in ("max", "year"):
        for sc in SCALINGS:
            a_, b_ = r_[(tag, sc)], r_[(tag, sc, "el")]
            DST_CMP.append((f"{nm}, sized to {'the longest window' if tag == 'max' else 'binds a year'}, backing ({sc})",
                            pct(a_["back"], 1), pct(b_["back"], 1)))
            DST_CMP.append((f"{nm}, sized to {'the longest window' if tag == 'max' else 'binds a year'}, lendable ({sc})",
                            f"{a_['lend']:.3f}", f"{b_['lend']:.3f}"))
DST_CHANGED = [r_ for r_ in DST_CMP if r_[1] != r_[2]]


# =============================================================================
# 5. C. LIQUIDITY-BUFFER SENSITIVITY ON S2
# =============================================================================
def buffer_cell(share, buf, end):
    """S2 stays on the absolute convention: bills held for the always-on tier are not lendable whether or not they are
    a pre-existing buffer, so the lendable share is 1 - share at every buffer. 'incr' is 1 minus the incremental
    lending displacement relative to a bank that already holds the buffer, max(0, share - b): not the S2 metric."""
    cov = min(buf, share)                            # the part of the backing drawn from the buffer
    excess = share - cov
    fc = cov / share if share > 0 else 0.0
    t = r7_terms(share, end)
    cap = share * (fc * CUSTODY[end] + (1.0 - fc) * R7_ENC[end])
    return dict(lend=1.0 - share, incr=1.0 - excess, disp=excess, price=t["credit"] + t["access"] + cap + t["frictions"],
                fc=fc)


BUF = {(s, b): (buffer_cell(s, b, 0), buffer_cell(s, b, 1)) for s in R7_SHARE_SET for b in BUFFER_SET}
# smallest buffer at which the incremental displacement is at most 1 - S2_MIN (not an S2 pass)
BUF_MIN = {s: max(0.0, s - (1.0 - S2_MIN)) for s in R7_SHARE_SET}
BUF_MIN_GROSS = {s: max(0.0, s / (1.0 - R7_HAIRCUT) - (1.0 - S2_MIN)) for s in R7_SHARE_SET}   # disclosure only
BUF_CHECK = max(abs(BUF[(s, 0.0)][e]["price"] - r7_price(s, e)) for s in R7_SHARE_SET for e in (0, 1))
D99_BAL = MC_X["sec99"] * R7_SHARE                    # average member's secured debit on the 99th-percentile weekend
DOUBLE = [(b, max(b - D99_BAL, 0.0) / b, max(b - R7_SHARE, 0.0) / b) for b in BUFFER_SET if b > 0]


# =============================================================================
# 6. D. NON-MEMBERS THROUGH A SPONSORING MEMBER
# =============================================================================
SPON = []
for s in D_SHARES:
    lo = r7_price(s, 0) + s * SPONSOR_MARGIN[0] + SPONSOR_ACCESS[0]
    hi = r7_price(s, 1) + s * SPONSOR_MARGIN[1] + SPONSOR_ACCESS[1]
    SPON.append(dict(s=s, mlo=r7_price(s, 0), mhi=r7_price(s, 1), lo=lo, hi=hi))


# =============================================================================
# 7. E. MONDAY CASH FOR NET CREDITORS WHEN A MEMBER IS CLOSED
# =============================================================================
H_GAP = GAP_H_NORMAL


def cash_gap_hours(fri):
    """Legal stay interval and operational collateral-to-cash interval for a member closed on Friday `fri`: from the
    scheduled Fedwire opening for the next business day B1 (21:00 the day before) to the end of the stay (B1 17:00);
    and, since the stay ends after the securities cutoff, to the next Fedwire Securities opening (B2 8:30)."""
    ops = [d for d in operating_days(fri.year + (fri.month == 12), WEEKDAYS_CURRENT, True) if d > fri]
    b1, b2 = ops[0], ops[1]
    o = dt.datetime(b1.year, b1.month, b1.day) - dt.timedelta(hours=24 - FEDWIRE_OPEN_HOUR_PREV_DAY)
    stay = dt.datetime(b1.year, b1.month, b1.day, QFC_STAY_END_HOUR)
    oper = (dt.datetime(b2.year, b2.month, b2.day) + dt.timedelta(hours=SEC_OPEN_HOUR) if QFC_STAY_END_HOUR > SEC_CUTOFF_HOUR
            else stay)
    return dict(fri=fri, b1=b1, b2=b2, open=o, stay=stay, oper=oper, legal=(stay - o).total_seconds() / 3600,
                op=(oper - o).total_seconds() / 3600)


GAP_CASES = [("Normal weekend (Friday 6 March 2026)", cash_gap_hours(date(2026, 3, 6))),
             ("Monday holiday (Friday 16 January 2026, Martin Luther King Jr. Day)", cash_gap_hours(date(2026, 1, 16)))]
DEBITS = [("Closed member at its cap (the full always-on tier)", R7_SHARE),
          ("Cohort-average member on the 99th-percentile weekend (open debtor cohort, A, Gaussian, rho 0.30, M 20)", D99_BAL),
          ("Median weekend peak debit", R7_OUT_MED * R7_SHARE)]
MON = []
for lab, d in DEBITS:
    row = dict(lab=lab, d=d, per=d / (M_BASE - 1))
    for end in (0, 1):
        rate = SECURED_RATE + BRIDGE_SPREAD[end]
        row[("exp", end)] = LAMBDA_P * d * rate * H_GAP / 8760
        row[("exp_spread", end)] = LAMBDA_P * d * BRIDGE_SPREAD[end] * H_GAP / 8760
        row[("event", end)] = d / (M_BASE - 1) * rate * GAP_H_NORMAL / 8760
        row[("exp_op", end)] = LAMBDA_P * d * rate * GAP_H_OPER / 8760
        row[("exp_spread_op", end)] = LAMBDA_P * d * BRIDGE_SPREAD[end] * GAP_H_OPER / 8760
        row[("event_op", end)] = d / (M_BASE - 1) * rate * GAP_H_OPER / 8760
    MON.append(row)


# =============================================================================
# 7b. F. THE SUNDAY SETTLEMENT CASH SOURCE
# =============================================================================
def lognorm_min_mean(med, sig, c):
    """E[min(Y, c)] for Y lognormal with median med and dispersion sig."""
    d2 = math.log(med / c) / sig
    return med * math.exp(sig * sig / 2) * _ND.cdf(-d2 - sig) + c * _ND.cdf(d2)


SUN_DEBIT = R7_SHARE * lognorm_min_mean(R7_OUT_MED, R7_OUT_SIG, 1.0)   # expected secured debit settled at Sunday 21:00
DOD_H = (24 - FEDWIRE_OPEN_HOUR_PREV_DAY) + DOD_REPAY_HOUR              # Sunday 21:00 to Monday repayment


def psr_daily_rate(annual):
    """Effective daily daylight overdraft rate: annual rate / 360, truncated to PSR_DAILY_DP decimals (PSR Section II.C)."""
    return math.floor(annual / PSR_YEAR_DAYS * 10 ** PSR_DAILY_DP + 1e-9) / 10 ** PSR_DAILY_DP


def dod_cost(f, hours):
    """Expected fee a year on the whole balance: daily rate x the average overdraft over the 24-hour day, 52 Sundays."""
    return R7_WEEKENDS * SUN_DEBIT * psr_daily_rate(f) * hours / 24


DOD_COST = {f: dod_cost(f, DOD_H) for f in DOD_FEE_SET}
DOD_H_1700 = (24 - FEDWIRE_OPEN_HOUR_PREV_DAY) + QFC_STAY_END_HOUR      # memo: repaid only at Monday 17:00
DOD_COST_1700 = {f: dod_cost(f, DOD_H_1700) for f in DOD_FEE_SET}
SUN_ROWS = [
    ("Collateralized Reserve Bank daylight overdraft, Reserve Bank collateral already on the book as loans",
     f"Reserve Bank collateral with lendable value of at least the cap ({pct(R7_SHARE, 0)} of the balance), separate "
     "from the bills pledged to the facility", 1.0 - R7_SHARE),
    ("Collateralized Reserve Bank daylight overdraft, collateral bought for the purpose",
     f"securities pledged at the Reserve Bank of at least the cap ({pct(R7_SHARE, 0)} of the balance)", 1.0 - 2 * R7_SHARE),
    ("Reserves held against the weekend outflow", f"reserves of at least the cap ({pct(R7_SHARE, 0)} of the balance)",
     1.0 - 2 * R7_SHARE)]
# seven-day Fedwire Funds with Fedwire Securities and repo on weekdays: weekend net debits settle in reserves before any
# bill can be monetized, so the pass needs weekend Reserve Bank credit or reserves held against the weekend outflow
_sv = SCEN[2]
SEVEN_RES = []
for sc in SCALINGS:
    bills = _sv[("year", sc)]["back"]
    for lab, h in ((f"normal-weekend window, {H_REF} hours (the outflow's calibration window)", H_REF),
                   (f"Friday securities cutoff to Monday securities opening, {H_SEC_GAP:g} hours", H_SEC_GAP)):
        res = R7_SHARE * g_scale(h, sc)
        SEVEN_RES.append(dict(sc=sc, lab=lab, bills=bills, res=res, lend=1.0 - bills - res))
SEVEN_CREDIT = {sc: 1.0 - _sv[("year", sc)]["back"] for sc in SCALINGS}   # with weekend Reserve Bank credit


# =============================================================================
# 8. PARITY AND METHOD CHECKS
# =============================================================================
_ROUTES_TXT = ROUTES_MD.read_text(encoding="utf-8") if ROUTES_MD.is_file() else ""
PARITY = [  # (label, imported value formatted, recorded value, context string in results_routes.md)
    ("R7 price, low end, bps a year on the whole balance", b1(R7_LO), "10.0", "| Facility price, whole balance | 10.0 | 34.0 |"),
    ("R7 price, high end, bps", b1(R7_HI), "34.0", "| Facility price, whole balance | 10.0 | 34.0 |"),
    ("R7 price, base, bps", b1(R7_BASE), "22.0", "10.0 to 34.0 (base 22.0)"),
    ("Per-member bind probability per weekend at sigma 0.8", pct(p_bind(0.8), 3), "4.156%", "| 0.8 | 4.156% |"),
    ("Per-member bind probability at sigma 0.5", pct(p_bind(0.5), 3), "0.278%", "| 0.5 | 0.278% |"),
    ("Per-member bind probability at sigma 1.2", pct(p_bind(1.2), 3), "12.399%", "| 1.2 | 12.399% |"),
    ("R7 lendable share at the 20% always-on share", f"{R7_LEND:.2f}", "0.80",
     f"| 20% | 10.0 to 34.0 | 50.0 to 170.0 | 0.80 | {s2_txt(R7_LEND)} |"),
    ("Haircut on bills", f"{R7_HAIRCUT:.0%}", "2%", "20%; 2% on bills"),
    ("Always-on share", f"{R7_SHARE:.0%}", "20%", "R7 always-on share; haircut | 20%"),
    ("Weekend outflow median / tier; sigma", f"{R7_OUT_MED:.0%}; {R7_OUT_SIG}", "25%; 0.8", "median 25%, sigma 0.8"),
    ("S2 threshold (lendable share at least)", f"{S2_MIN:g}", f"{rt._s2_min_arg():g}",
     f"lendable share >= {rt._s2_min_arg():g}"),
    ("Real-world default intensity lambda_P", pct(LAMBDA_P), "0.25%", "lambda_P; mu; LGD; a; D | 0.25%"),
]
PARITY_ROWS = [(lab, v, rec, v == rec and ctx in _ROUTES_TXT) for lab, v, rec, ctx in PARITY]
PARITY_OK = all(r[3] for r in PARITY_ROWS)

_pg = np.linspace(1e-7, 1 - 1e-7, 2001)
_ninv_err = max(abs(float(a) - _ND.inv_cdf(float(p))) for a, p in zip(ninv(_pg), _pg))
_tq = t_upper_quantile(p_bind(R7_OUT_SIG))
_tq_cc = -cc._t_nodes(p_bind(R7_OUT_SIG), 0.0)[3]
_pm0 = MC[("gauss", 0.0, M_BASE, R7_OUT_SIG)]["pm"]
_binom = {k: 1.0 - sum(math.comb(M_BASE, j) * P_MEMBER[R7_OUT_SIG] ** j * (1 - P_MEMBER[R7_OUT_SIG]) ** (M_BASE - j)
                       for j in range(k)) for k in (1, 3, quarter(M_BASE))}
_q0 = PMF[("gauss", 0.0, M_BASE, R7_OUT_SIG)]
METHOD = [
    ("Inverse normal (vectorized) vs the standard library, largest absolute gap on a 2,001-point grid", _ninv_err, 0.0, 1e-7),
    ("t(5) upper quantile at 4.156%: closed-form cdf vs the clearing-cost engine's threshold", _tq, _tq_cc, 2e-3),
    ("rho 0, Gaussian: quadrature P(at least 1 of 20) vs independent binomial", p_atleast(_q0, 1), _binom[1], 1e-12),
    ("rho 0, Gaussian: quadrature P(at least 3 of 20) vs independent binomial", p_atleast(_q0, 3), _binom[3], 1e-12),
    ("rho 0, Gaussian: quadrature P(at least 5 of 20) vs independent binomial", p_atleast(_q0, 5), _binom[5], 1e-12),
    ("Window of 50 hours at 20% backing vs the routes engine's per-member bind probability", p_win(H_REF), p_bind(R7_OUT_SIG), 1e-12),
    ("Calendar: closed hours + 22 x business days vs hours between the year's bounding closes (largest gap)", CAL_CHECK, 0.0, 1e-9),
    ("Buffer 0: facility price vs the routes engine's r7_price (largest gap, bps)", BUF_CHECK / BP, 0.0, 1e-9),
]
METHOD_ROWS = [(lab, a, b, abs(a - b) <= tol) for lab, a, b, tol in METHOD]
MC_CHECK = []
for cop in COPULAS:
    for rho in RHO_SET:
        k = (cop, rho, M_BASE, R7_OUT_SIG)
        an = PMF[k]
        MC_CHECK.append((COP_NAME[cop], rho, MC[k]["pm"], (MC[k]["pm"] - P_MEMBER[R7_OUT_SIG]) / MC[k]["pm_se"],
                         p_atleast(an, 1), MC[k]["p1"], mc_z(MC[k]["p1"], p_atleast(an, 1)),
                         p_atleast(an, 3), MC[k]["p3"], mc_z(MC[k]["p3"], p_atleast(an, 3)),
                         p_atleast(an, quarter(M_BASE)), MC[k]["pq"], mc_z(MC[k]["pq"], p_atleast(an, quarter(M_BASE)))))
MC_MAXZ = max(max(abs(r[3]), abs(r[6]), abs(r[9]), abs(r[12])) for r in MC_CHECK)
METHOD_OK = all(r[3] for r in METHOD_ROWS)


# =============================================================================
# 9. RESULTS FILE
# =============================================================================
def write_results():
    L = []
    w = L.append
    ps = P_MEMBER[R7_OUT_SIG]
    w("# Cash That Never Sleeps, Chapter 6: the settlement clock of the always-on netting facility (settlement.py results)")
    w("")
    w("Every number is illustrative and calibrated to no bank, facility or member. Parameters not imported from the routes "
      "engine are author assumptions (illustrative). Units: bps a year on the whole tokenized balance unless stated; "
      "shares are of the member's tokenized balance unless stated as a share of its always-on tier. Command: "
      f"`python -I -B model/{SCRIPT_NAME}{'' if rt.S2_DEFAULT_RUN else f' --s2-min {S2_MIN:g}'}` from the repository "
      "root. The script imports the routes engine "
      "(`model/routes.py`) by path, which loads the clearing-cost and mutual-tail engines, and copies no code from them. "
      f"Seed: {MC_SEED} (same-weekend Monte Carlo, {MC_N:,} weekends); the imported engines carry their own. Run "
      f"environment: Python {platform.python_version()}, numpy {np.__version__}; the run time is printed to the console "
      "and not written here, so two runs give the same file. Readings marked [author's reading] are readings, not findings "
      "of law.")
    if not rt.S2_DEFAULT_RUN:
        w("")
        w(f"Run at an S2 bar of {S2_MIN:g}, not the rule of record ({rt.S2_MIN_DEFAULT:.2f}). Tables and S2 columns use "
          "this bar; sentences that name a verdict were written for the rule of record, so read the tables.")
    w("")
    w("The simulated variable is each member's PEAK net debit during the closed window to all counterparties, members "
      "and non-members, as a share of its always-on tier: the lognormal is the distribution of that peak, not of the "
      "terminal net position. Per-member results (bind probability, the per-member cap ladder rows, the median boundary) "
      "are the headline, conditional on the assumed distribution. Every multi-member statistic (system queue, joint cap "
      "ladder, any-binds, a quarter or more binding, the pooled cap, the system-average secured debit) describes an "
      "OPEN debtor cohort: members drawn as net debtors whose receivers sit outside the modelled set. It is not a "
      "closed-membership result, in which signed net positions would sum to zero.")
    w("")
    # ---------------------------------------------------------------- 1
    w("## 1. Parameters")
    w("")
    rows = [
        ("Always-on share; haircut on bills", f"{R7_SHARE:.0%}; {R7_HAIRCUT:.0%}", "imported from routes.py"),
        ("R7 terms: credit; access; encumbrance spread; frictions",
         f"{rng_b(*R7_CREDIT)}; {rng_b(*R7_ACCESS)}; {rng_b(*R7_ENC)} on the bill slice; {rng_b(*R7_FRIC)}",
         "imported from routes.py"),
        ("Weekend peak net debit (to all counterparties, members and non-members) / always-on tier",
         f"lognormal, median {R7_OUT_MED:.0%}, sigma {R7_OUT_SIG} "
         f"(set {', '.join(str(s) for s in SIG_SET)}); {R7_WEEKENDS} weekends a year", "imported from routes.py"),
        ("S2 threshold", f"lendable share at least {S2_MIN:g}", "imported from routes.py"),
        ("Real-world default intensity of a member (lambda_P)", f"{pct(LAMBDA_P)} a year",
         "imported from routes.py (the clearing-cost engine's LAMBDA_P)"),
        ("Student-t degrees of freedom", f"{NU}", "imported (the clearing-cost engine's)"),
        ("Members M in the open debtor cohort", f"{M_BASE} (also {', '.join(str(m) for m in M_SET if m != M_BASE)}), "
         "equal size, receivers outside the modelled set", "author assumption (illustrative)"),
        ("Median peak debit for the sensitivity, share of the balance", ", ".join(pct(m, 1) for m in MED_SET),
         "author assumption (illustrative)"),
        ("Pairwise latent correlation rho", ", ".join(f"{r:.2f}" for r in RHO_SET), "author assumption (illustrative)"),
        ("Copulas", f"one-factor Gaussian and one-factor Student-t({NU}), same lognormal marginal", "author assumption (illustrative)"),
        ("Bind frequency targets for the cap ladder", "1% of weekends; once in ten years (1 in 520 weekends)", "author assumption (illustrative)"),
        ("Fedwire Funds hours", f"opens {FEDWIRE_OPEN_HOUR_PREV_DAY}:00 ET on the preceding calendar day (holidays "
         f"included); closes {FEDWIRE_CLOSE_HOUR}:00 ET on business days", f"reported figure, {HOURS_SRC}"),
        ("Reserve Bank weekday closings 2026", "; ".join(d.strftime("%b %d") for d in HOLIDAYS_2026) +
         " (Jul 4 is a Saturday: open Friday, no weekday closing)", f"reported figure, {HOLIDAYS_SRC}"),
        ("Reserve Bank weekday closings 2027", "; ".join(d.strftime("%b %d") for d in sorted(HOLIDAYS_2027)) +
         " (Jun 19 and Dec 25 are Saturdays: open Friday; Jul 4 is a Sunday: closed Monday Jul 5)",
         f"reported figure, {HOLIDAYS_SRC}"),
        ("Announced 22x6 schedule", "Sunday to Friday including weekday holidays, Saturday closed (26 hours from Friday "
         "19:00 to Saturday 21:00), implementation 2028 or 2029, not yet in effect", f"reported figure, {SIX_DAY_SRC}"),
        ("Fedwire Securities: opening; secondary-market transfer cutoff", "8:30 a.m. ET; 3:15 p.m. ET (3:30 p.m. is "
         "for reversals and repo adjustments); not covered by the 2025 schedule expansion, which is Fedwire Funds and NSS "
         "only", "reported figure, Federal Reserve Financial Services, Fedwire Securities Service schedule"),
        ("Closed-window convention; elapsed-hours check", f"nominal Eastern schedule hours; check with {TZ_NY} offsets "
         "(zoneinfo)", "author convention"),
        ("Stay on termination, liquidation and netting rights", f"no termination solely because of the receiver's appointment until {QFC_STAY_END_HOUR}:00 ET on the "
         "business day after it; business day excludes Saturday, Sunday and days the NYSE or the New York Reserve Bank is "
         "closed", "reported figure, 12 U.S.C. 1821(e)(10)(B)(i) and (e)(10)(D)"),
        ("Outflow over a window of h hours", "median scales with h / 50 (linear); square root of h / 50 as a sensitivity; same sigma",
         "author assumption (illustrative)"),
        ("Liquid-asset buffer b held anyway", ", ".join(f"{b:.0%}" for b in BUFFER_SET) + " of the tokenized balance",
         "author assumption (illustrative)"),
        ("Custody-and-positioning spread on bills drawn from the buffer", rng_b(*CUSTODY), "author assumption (illustrative)"),
        ("Sponsor margin; sponsor's extra access cost", f"{rng_b(*SPONSOR_MARGIN)} per non-member tier dollar; "
         f"{rng_b(*SPONSOR_ACCESS)} on the non-member's whole balance", "author assumption (illustrative)"),
        ("Overnight secured rate; bridging spread", f"{SECURED_RATE:.1%}; {rng_b(*BRIDGE_SPREAD)}", "author assumption (illustrative)"),
        ("Monday cash gap hours: legal stay interval", f"{GAP_H_NORMAL}, from the scheduled Fedwire opening at which "
         "settlement would have happened to the end of the stay (Sunday 21:00 to Monday 17:00; after a Monday holiday, "
         "Monday 21:00 to Tuesday 17:00)", "author convention on the reported hours"),
        ("Monday cash gap hours: operational collateral-to-cash interval", f"{GAP_H_OPER:g}: the stay ends after the "
         "securities cutoff, so collateral is delivered against cash at the next securities opening (Sunday 21:00 to "
         "Tuesday 8:30; after a Monday holiday, Monday 21:00 to Wednesday 8:30)", "author convention on the reported hours"),
        ("Daylight overdraft fee at the Sunday opening", f"{b1(DOD_FEE)} bps a year, collateralized (constant DOD_FEE); "
         f"{b1(DOD_FEE_SET[-1])} uncollateralized as a sensitivity, quoted on a 24-hour day and a {PSR_YEAR_DAYS}-day "
         f"year, daily rate truncated to {psr_daily_rate(DOD_FEE_SET[-1]):.7f}", "reported figure, Federal Reserve Policy "
         "on Payment System Risk, Section II.C and footnote 58"),
        ("Daylight overdraft repaid", f"Monday {DOD_REPAY_HOUR}:00 ET: a solvent debtor repays from a "
         "delivery-versus-payment sale or bilateral repo of its bills settling Monday morning after the 8:30 securities "
         f"opening ({DOD_H:g} hours from the Sunday opening)", "author assumption (illustrative)"),
        ("Closure timing; spread of the closed member's debit", "every closure on the last business day before a weekend; "
         f"debit spread equally over the other {M_BASE - 1} members", "author assumption (illustrative)"),
    ]
    w(table(["Parameter", "Value", "Label"], rows))
    w("")
    # ---------------------------------------------------------------- 2
    w("## 2. Parity with the routes engine and method checks")
    w("")
    w("Each imported value is read from the routes engine in memory and compared, at the precision it is recorded, with "
      "the value in `model/results_routes.md`; the row passes only when the two strings match and the recorded string is "
      "present in that file.")
    w("")
    w(table(["Imported quantity", "Imported value", "Recorded value", "Result"],
            [(l, v, r, "PASS" if ok else "FAIL") for l, v, r, ok in PARITY_ROWS]))
    w("")
    w(f"Parity result: {'all rows PASS' if PARITY_OK else 'at least one row FAILS'}.")
    w("")
    w(table(["Method check", "This engine", "Reference", "Result"],
            [(l, f"{a:.10f}", f"{b:.10f}", "PASS" if ok else "FAIL") for l, a, b, ok in METHOD_ROWS]))
    w("")
    w(f"Method checks: {'all PASS' if METHOD_OK else 'at least one FAILS'}. The Monte Carlo check of the factor model is in "
      f"Section 3 (largest absolute z-score {MC_MAXZ:.2f}).")
    w("")
    # ---------------------------------------------------------------- 3 A
    w("## 3. Same-weekend factor model (analysis A)")
    w("")
    w(f"Member i's weekend peak net debit (the largest net debit it runs during the closed window, to all "
      f"counterparties) as a share of its always-on tier is X_i = {R7_OUT_MED:.2f} exp(sigma Z_i), the "
      "routes engine's marginal. The M members form an open debtor cohort: each is drawn as a net debtor and its "
      "receivers sit outside the modelled set. Dependence enters through a one-factor copula: Z_i = sqrt(rho) F + sqrt(1 - rho) e_i "
      f"(Gaussian), or the same latent divided by sqrt(W / {NU}), W chi-square({NU}), and mapped back to a standard normal "
      "through the t cdf (Student-t), so each member keeps the lognormal marginal. The cap binds at a member when X_i "
      "exceeds 1. Counts come from quadrature over the factor (and W for the t copula); the queued amount, the peak debit "
      "above the cap summed over the cohort as a share of the cohort's always-on tier, comes from the Monte Carlo. Weekends "
      f"are independent of each other, so the 99th percentile over a year is the weekly quantile at 0.99^(1/{R7_WEEKENDS}).")
    w("")
    rows = []
    for cop in COPULAS:
        for rho in RHO_SET:
            k = (cop, rho, M_BASE, R7_OUT_SIG)
            pm, m = PMF[k], MC[k]
            rows.append((COP_NAME[cop], f"{rho:.2f}", psig(p_atleast(pm, 1)), psig(p_atleast(pm, 3)),
                         psig(p_atleast(pm, quarter(M_BASE))), f"{float((np.arange(M_BASE + 1) * pm).sum()):.3f}",
                         pct(m["q_mean"], 3), pct(m["q99"], 2), pct(m["q99y"], 2)))
    w(f"Table A1. Open debtor cohort of M {M_BASE}, sigma {R7_OUT_SIG}: bind counts per weekend and the queued amount "
      "(share of the cohort's always-on tier). Not a closed-membership result.")
    w("")
    w(table(["Copula", "rho", "P(at least 1 binds)", "P(at least 3)", f"P(at least {quarter(M_BASE)}, a quarter)",
             "Expected number binding", "Queued, mean", "Queued, 99th pct weekend", "Queued, 99th pct over a year"], rows))
    w("")
    g0, g3 = PMF[("gauss", 0.0, M_BASE, R7_OUT_SIG)], PMF[("gauss", RHO_REF, M_BASE, R7_OUT_SIG)]
    t3, t5 = PMF[("t", RHO_REF, M_BASE, R7_OUT_SIG)], PMF[("t", 0.50, M_BASE, R7_OUT_SIG)]
    mg3, mt3 = MC[("gauss", RHO_REF, M_BASE, R7_OUT_SIG)], MC[("t", RHO_REF, M_BASE, R7_OUT_SIG)]
    w(f"Each member's cap binds in {pct(ps, 3)} of weekends whatever the copula, so the expected number binding is "
      f"{M_BASE * ps:.3f} in every row; dependence changes how the binds arrive. With independent members the cap binds "
      f"somewhere in the open cohort in {psig(p_atleast(g0, 1))} of weekends and at a quarter of members in "
      f"{psig(p_atleast(g0, quarter(M_BASE)))}. At rho 0.30 the Gaussian factor lowers the chance that any member binds to "
      f"{psig(p_atleast(g3, 1))} but raises the chance that a quarter bind together to {psig(p_atleast(g3, quarter(M_BASE)))}, "
      f"and the Student-t(5) factor raises it to {psig(p_atleast(t3, quarter(M_BASE)))} ({psig(p_atleast(t5, quarter(M_BASE)))} at "
      f"rho 0.50). The queued amount on the 99th-percentile weekend of a year is {pct(mg3['q99y'], 2)} of the cohort's "
      f"always-on tier under the Gaussian factor at rho 0.30 and {pct(mt3['q99y'], 2)} under the t factor. The t(5) "
      "copula at rho 0 is uncorrelated but not independent: the common W still makes binds arrive together.")
    w("")
    w(f"Table A2. Sensitivity, open debtor cohort: P(at least 1 binds), P(at least a quarter bind) and the queued amount "
      f"on the 99th-percentile weekend of a year, by cohort size (sigma {R7_OUT_SIG}) and by sigma (M {M_BASE}).")
    w("")
    rows = []
    for M, sg in [(m, R7_OUT_SIG) for m in M_SET if m != M_BASE] + [(M_BASE, s) for s in SIG_SET if s != R7_OUT_SIG]:
        for cop in COPULAS:
            for rho in RHO_SET:
                k = (cop, rho, M, sg)
                rows.append((M, sg, COP_NAME[cop], f"{rho:.2f}", pct(P_MEMBER[sg], 3), psig(p_atleast(PMF[k], 1)),
                             f"{quarter(M)}", psig(p_atleast(PMF[k], quarter(M))), pct(MC[k]["q99y"], 2)))
    w(table(["M", "sigma", "Copula", "rho", "Per-member P(bind)", "P(at least 1)", "A quarter is", "P(at least a quarter)",
             "Queued, 99th pct over a year"], rows))
    w("")
    k10 = ("gauss", RHO_REF, 10, R7_OUT_SIG)
    k40 = ("gauss", RHO_REF, 40, R7_OUT_SIG)
    w(f"A larger open cohort makes some bind on most weekends but makes a quarter binding together rarer: under the Gaussian "
      f"factor at rho 0.30, P(at least a quarter) is {psig(p_atleast(PMF[k10], quarter(10)))} with 10 members and "
      f"{psig(p_atleast(PMF[k40], quarter(40)))} with 40. Sigma moves everything: at sigma 0.5 the per-member rate is "
      f"{pct(P_MEMBER[0.5], 3)} and at 1.2 it is {pct(P_MEMBER[1.2], 3)}.")
    w("")
    w(f"Table A3. Monte Carlo check of the quadrature, M {M_BASE}, sigma {R7_OUT_SIG} ({MC_N:,} weekends, seed {MC_SEED}); "
      "z is (Monte Carlo minus quadrature) / standard error; the per-member standard error is that of the weekly share "
      "of members binding, so it allows for dependence within a weekend. The rows share one set of draws, so their errors "
      "move together.")
    w("")
    rows = [(c, f"{r:.2f}", f"{pm * 100:.3f}% ({zpm:+.2f})", f"{psig(a1)} / {psig(m1)} ({z1:+.2f})",
             f"{psig(a3)} / {psig(m3)} ({z3:+.2f})", f"{psig(aq)} / {psig(mq)} ({zq:+.2f})")
            for c, r, pm, zpm, a1, m1, z1, a3, m3, z3, aq, mq, zq in MC_CHECK]
    w(table(["Copula", "rho", "Per-member rate, Monte Carlo (z)", "P(at least 1), quadrature / Monte Carlo (z)",
             "P(at least 3) (z)", f"P(at least {quarter(M_BASE)}) (z)"], rows))
    w("")
    w(f"At rho 0 the Gaussian quadrature reproduces the independent binomial exactly (Section 2) and the Monte Carlo "
      f"per-member rate is {pct(_pm0, 3)} against {pct(ps, 3)}. The largest absolute z-score in the table is {MC_MAXZ:.2f}.")
    w("")
    # cap ladder
    w("### Cap ladder")
    w("")
    w(f"The backing a member must hold (its always-on share, with the cap equal to the share) so that a bind frequency "
      f"meets a target, with the weekend peak debit itself unchanged: median {R7_OUT_MED:.0%} of a 20% tier, that is "
      f"{pct(R7_OUT_MED * R7_SHARE, 1)} of the tokenized balance, sigma {R7_OUT_SIG}. The cap multiple is the cap over the "
      "median peak debit (4.0 in the routes engine). The per-member criterion does not depend on the copula or rho, "
      "because each member keeps its marginal; the joint criteria do, and describe the open debtor cohort, not a closed "
      "membership. Prices use the routes engine's r7_price at the new share; "
      "lendable share is 1 minus the share, as in the routes engine.")
    w("")
    rows = [(r["target"], r["crit"], r["cop"], "any" if r["rho"] is None else f"{r['rho']:.2f}", psig(r["pd"]),
             f"{r['mult']:.2f}", pct(r["back"], 1), rng_b(r["lo"], r["hi"]), f"{r['lend']:.3f}", s2_txt(r["lend"]))
            for r in LADDER]
    w(table(["Target", "Criterion", "Copula", "rho", "Per-member P(bind) needed", "Cap multiple", "Backing (always-on share)",
             "Price, whole balance", "Lendable share", "S2"], rows))
    w("")
    pm1 = LADDER[0]
    pm10 = [r for r in LADDER if r["crit"] == "per member"][1]
    w(f"Rows that pass S2: {len(LADDER_PASS)} of {len(LADDER)}"
      + (": " + "; ".join(f"{r['target']}, {r['crit']}, {r['cop']}, rho {r['rho']}" for r in LADDER_PASS) if LADDER_PASS else
         ", none.")
      + f" Holding a member's own cap to binding in 1% of weekends needs a cap multiple of {pm1['mult']:.2f} and a backing "
      f"of {pct(pm1['back'], 1)} of the balance, priced {rng_b(pm1['lo'], pm1['hi'])} with a lendable share of "
      f"{pm1['lend']:.2f}; once in ten years needs {pct(pm10['back'], 1)}, priced {rng_b(pm10['lo'], pm10['hi'])}. "
      f"S2 allows a backing of at most {pct(CAP_S2, 0)} (a cap multiple of {CAP_S2 / _MED_ASSUMED:.1f} at this outflow), at "
      "which a member's cap binds in "
      f"{psig(S2_MED_P[R7_OUT_SIG])} of weekends.")
    w("")
    w("Table A4. The largest median weekend peak debit, as a share of the tokenized balance, at which a member can meet the "
      f"per-member target with a backing that passes S2 (backing at most {pct(CAP_S2, 0)}); the routes engine assumes "
      f"{pct(_MED_ASSUMED, 1)}.")
    w("")
    rows = [(sg, tn, pct(m, 2), psig(S2_MED_P[sg])) for sg, tn, m in S2_MED]
    w(table(["sigma", "Per-member target", "Largest median peak debit compatible with S2",
             f"Per-member P(bind) at a {pct(CAP_S2, 0)} backing, median {pct(_MED_ASSUMED, 0)}"], rows))
    w("")
    m1 = [m for sg, tn, m in S2_MED if sg == R7_OUT_SIG][0]
    w(f"At sigma {R7_OUT_SIG} the facility meets S2 and a 1% per-member bind rate together only if the median weekend peak "
      f"debit is at most {pct(m1, 2)} of the tokenized balance, under a third of the routes engine's 5%. The lendable screen "
      "and a rare cap cannot both hold at the routes engine's outflow assumption.")
    w("")
    w(f"Table A5. Median sensitivity, per member: bind probability per weekend at a cap of {pct(CAP_S2, 0)} of the balance "
      "(the largest backing S2 allows), and the cap a 1%-of-weekends bind needs, with the S2 verdict on that cap.")
    w("")
    w(table(["sigma", "Median peak debit, share of the balance", f"P(bind) at a {pct(CAP_S2, 0)} cap",
             "Cap for a 1% per-member bind", "Lendable share at that cap", "S2"],
            [(r["sig"], pct(r["med"], 1), psig(r["p10"]), pct(r["cap1"], 2), f"{1 - r['cap1']:.3f}", s2_txt(1 - r["cap1"]))
             for r in MED_SENS]))
    w("")
    _ms = {(r["sig"], r["med"]): r for r in MED_SENS}
    w(f"At sigma {R7_OUT_SIG} the verdict turns between medians of 1.5% and 2%: a 1% bind needs a cap of "
      f"{pct(_ms[(R7_OUT_SIG, 0.015)]['cap1'], 2)} at 1.5% (pass) and {pct(_ms[(R7_OUT_SIG, 0.02)]['cap1'], 2)} at 2% (fail). "
      "No public source reports participant-level peak debits on tokenized balances, so the median is the input to "
      "observe in a pilot.")
    w("")
    w("### S2 bar sensitivity of the cap-ladder boundary")
    w("")
    w(f"Table A6. At each S2 bar of the routes engine's sensitivity (results_routes.md, Section 9b), the largest cap S2 "
      f"allows, c = 1 minus the bar, and the largest median weekend peak debit, as a share of the tokenized balance, that "
      f"keeps a member's cap binding in at most {pct(S2_MED_BAR_TARGET, 0)} of weekends: c / exp(sigma x "
      f"{-_ND.inv_cdf(S2_MED_BAR_TARGET):.4f}). The second boundary counts the grossed-up bills as non-lendable, so the "
      f"cap is c x {1 - R7_HAIRCUT:.2f} (Section 9). The cap test passes when the boundary is at least the assumed "
      f"median of {pct(_MED_ASSUMED, 1)}. The rule of record is the {rt.S2_MIN_DEFAULT:g} bar.")
    w("")
    w(table(["S2 bar", "Largest cap c", "sigma", "Largest median for a 1% bind, cap c",
             f"Cap test at the {pct(_MED_ASSUMED, 1)} median, cap c",
             f"Largest median, cap c x {1 - R7_HAIRCUT:.2f} (grossed-up bills)",
             f"Cap test at the {pct(_MED_ASSUMED, 1)} median, grossed-up bills",
             f"Per-member P(bind) at cap c, median {pct(_MED_ASSUMED, 1)}"],
            [(f"{r['bar']:.2f}", pct(r["c"], 0), r["sig"], pct(r["med"], 2),
              "pass" if r["med"] >= _MED_ASSUMED - 1e-12 else "fail", pct(r["med_g"], 2),
              "pass" if r["med_g"] >= _MED_ASSUMED - 1e-12 else "fail", psig(r["p"])) for r in S2_MED_BAR]))
    w("")
    _pass = [r for r in S2_MED_BAR if r["med"] >= _MED_ASSUMED - 1e-12]
    _r08 = {r["bar"]: r for r in S2_MED_BAR if r["sig"] == R7_OUT_SIG}
    w(f"At sigma {R7_OUT_SIG} the boundary is " + ", ".join(f"{pct(_r08[b]['med'], 2)} at {b:.2f}" for b in rt.S2_BARS)
      + f" ({', '.join(pct(_r08[b]['med_g'], 2) for b in rt.S2_BARS)} counting the grossed-up bills): the cap test "
      + ("fails" if all(_r08[b]["med"] < _MED_ASSUMED - 1e-12 for b in rt.S2_BARS) else "does not fail")
      + f" at the assumed {pct(_MED_ASSUMED, 1)} median at every bar. "
      + ("It passes only at " + "; ".join(f"sigma {r['sig']}, bar {r['bar']:.2f}" for r in _pass) + "."
         if _pass else "It fails at every bar and sigma in the grid."))
    w("")
    # ---------------------------------------------------------------- 4 B
    w("## 4. Closed-window calendar (analysis B)")
    w("")
    w(f"Fedwire Funds opens at {FEDWIRE_OPEN_HOUR_PREV_DAY}:00 ET on the calendar day before each business day "
      f"and closes at {FEDWIRE_CLOSE_HOUR}:00 ET ({HOURS_SRC}), so a closed window between business days a and b lasts "
      f"24 x (days from a to b) - 22 hours. Holidays are the Reserve Banks' weekday closings ({HOLIDAYS_SRC}). Each business "
      "day is preceded by one window, and a window belongs to the year of the business day that ends it. Window lengths "
      "are nominal schedule hours (the convention); the elapsed-hours check at the end of this section adds the "
      "daylight-saving offsets. The constants sit at the top of the script.")
    w("")
    rows = []
    for y in YEARS:
        for h, n in CAL[y]["rows"]:
            rows.append((y, wtype(h), h, n, n * h))
        rows.append((y, "All windows", "", sum(n for _, n in CAL[y]["rows"]), CAL[y]["total"]))
    w("Table B1. Closed windows by type.")
    w("")
    w(table(["Year", "Window type", "Hours", "Count", "Total closed hours"], rows))
    w("")
    c26 = dict(CAL[2026]["rows"])
    w(f"2026 has {CAL[2026]['n_ops']} business days and {CAL[2026]['total']:,} closed hours; its {CAL[2026]['weekends']} "
      f"weekends split into {c26.get(50, 0)} normal weekends of 50 hours and {c26.get(74, 0)} three-day weekends of 74 hours, "
      f"and {c26.get(26, 0)} midweek holidays add 26-hour windows. 2027 has {CAL[2027]['n_ops']} business days and "
      f"{CAL[2027]['total']:,} closed hours. No window longer than 74 hours occurs in either year.")
    w("")
    rows = []
    for h in (2, 26, 50, 74):
        rows.append((wtype(h), h, psig(p_win(h, scaling="linear")), psig(p_win(h, scaling="sqrt")),
                     f"{p_win(h, scaling='linear') / p_win(H_REF):.2f}", f"{p_win(h, scaling='sqrt') / p_win(H_REF):.2f}"))
    w(f"Table B2. Policy P1 (cap sized for the normal weekend, backing {R7_SHARE:.0%}, all year): bind probability per window.")
    w("")
    w(table(["Window type", "Hours", "P(bind), linear scaling", "P(bind), square-root scaling", "Relative to a normal weekend, linear",
             "Relative, square root"], rows))
    w("")
    w(f"Under P1 a three-day weekend binds {HOL_RATIO['linear'][74]:.2f} times as often as a normal weekend with linear "
      f"scaling ({psig(p_win(74))} against {pct(ps, 3)}) and {HOL_RATIO['sqrt'][74]:.2f} times as often with square-root "
      f"scaling; a midweek holiday binds {HOL_RATIO['linear'][26]:.2f} times as often (linear). The weekday evening gap "
      "is negligible under either scaling.")
    w("")
    rows = [("Routes engine (52 independent weekends)", "", f"{ROUTES_BINDS:.2f}", pct(ROUTES_YEAR, 1))]
    for y in YEARS:
        for sc in SCALINGS:
            n, p1y = P1[(y, sc)]
            rows.append((f"Calendar {y}, P1", sc, f"{n:.2f}", pct(p1y, 1)))
    w("Table B3. Expected binds a year for one member under P1, calendar against the routes engine.")
    w("")
    w(table(["Basis", "Scaling", "Expected binds a year", "P(at least one bind in the year)"], rows))
    w("")
    w(f"The calendar adds {P1[(2026, 'linear')][0] - ROUTES_BINDS:.2f} expected binds a year to the routes engine's "
      f"{ROUTES_BINDS:.2f} in 2026 under linear scaling ({P1[(2026, 'linear')][0]:.2f} in all), almost all of it from the "
      f"{c26.get(74, 0)} three-day weekends.")
    w("")
    rows = []
    for y in YEARS:
        for sc in SCALINGS:
            d = P2[(y, sc)]
            rows.append((y, sc, "P1", pct(R7_SHARE, 1), rng_b(R7_LO, R7_HI), f"{R7_LEND:.3f}", s2_txt(R7_LEND),
                         f"{P1[(y, sc)][0]:.2f}"))
            rows.append((y, sc, f"P2 (longest window {CAL[y]['hmax']} h)", pct(d["back"], 1), rng_b(d["lo"], d["hi"]),
                         f"{d['lend']:.3f}", s2_txt(d["lend"]), f"{d['binds'][0]:.2f}"))
    w("Table B4. Policies: P1 sizes the cap for the normal weekend all year; P2 sizes the backing so the longest window binds "
      "no more often than a normal weekend does under P1, and holds it all year.")
    w("")
    w(table(["Year", "Scaling", "Policy", "Backing", "Price, whole balance", "Lendable share", "S2", "Expected binds a year"], rows))
    w("")
    p2 = P2[(2026, "linear")]
    w(f"P2 needs a backing of {pct(p2['back'], 1)} under linear scaling ({pct(P2[(2026, 'sqrt')]['back'], 1)} under square "
      f"root), priced {rng_b(p2['lo'], p2['hi'])} against P1's {rng_b(R7_LO, R7_HI)}, with a lendable share of "
      f"{p2['lend']:.2f}: it fails S2 by more than P1 does, and cuts expected binds to {p2['binds'][0]:.2f} a year.")
    w("")
    rows = []
    for r in SCEN:
        hc = "; ".join(f"{n} of {h} h" for h, n in sorted(r["hcount"].items()))
        for tag, lab in (("max", f"longest window ({r['h_max']} h) at {pct(ps, 3)}"),
                         ("year", f"{ROUTES_BINDS:.2f} expected binds a year")):
            d, ds = r[(tag, "linear")], r[(tag, "sqrt")]
            rows.append((r["name"], hc if tag == "max" else "", lab, pct(d["back"], 1), pct(ds["back"], 1),
                         rng_b(d["lo"], d["hi"]), f"{d['lend']:.3f}", s2_txt(d["lend"]), f"{d['binds']:.2f}",
                         f"{r['binds_p1']:.2f}" if tag == "max" else ""))
    w("Table B5. Schedule scenarios (2026 calendar). Two sizing criteria: the longest window binds no more often than a "
      f"normal weekend does under P1 ({pct(ps, 3)}), or the member's expected binds a year equal the routes engine's "
      f"{ROUTES_BINDS:.2f} (52 weekends at {pct(ps, 3)}). Price and lendable share at the linear backing.")
    w("")
    w(table(["Schedule", "Closed windows", "Sized to", "Backing, linear", "Backing, square root", "Price, linear",
             "Lendable, linear", "S2", "Expected binds a year at that backing (linear)",
             "Expected binds a year at a 20% backing (linear)"], rows))
    w("")
    cur, sf, sv = SCEN[0], SCEN[1], SCEN[2]
    sfl, sfq = sf[("max", "linear")], sf[("max", "sqrt")]
    w(f"Under the announced 22x6 schedule, which opens weekday holidays as well as Sundays, the longest window is the "
      f"{sf['h_max']}-hour Saturday closure, so the backing that holds P1's normal-weekend bind rate on every window falls "
      f"from {pct(cur[('max', 'linear')]['back'], 1)} today to {pct(sfl['back'], 1)} under linear scaling "
      f"({pct(sfq['back'], 1)} under square root), priced {rng_b(sfl['lo'], sfl['hi'])} against today's "
      f"{rng_b(cur[('max', 'linear')]['lo'], cur[('max', 'linear')]['hi'])}. The standing-capacity term falls by "
      f"{1 - sfl['back'] / R7_SHARE:.0%} against P1's 20% on the hours alone, but the lendable share is {sfl['lend']:.3f}, "
      f"which still misses S2 by {S2_MIN - sfl['lend']:.3f}; under square-root scaling it misses by {S2_MIN - sfq['lend']:.3f}. "
      f"Held to the routes engine's {ROUTES_BINDS:.2f} binds a year instead, today's calendar needs "
      f"{pct(cur[('year', 'linear')]['back'], 1)} and the 22x6 schedule {pct(sf[('year', 'linear')]['back'], 1)}. "
      f"Seven-day operation, a hypothetical, leaves 365 two-hour gaps: sized so each binds no more often than a normal "
      f"weekend today, the backing is {pct(sv[('max', 'linear')]['back'], 1)} (linear) or "
      f"{pct(sv[('max', 'sqrt')]['back'], 1)} (square root) but the member then binds {sv[('max', 'linear')]['binds']:.1f} "
      f"times a year; held to {ROUTES_BINDS:.2f} binds a year it is {pct(sv[('year', 'linear')]['back'], 1)} (linear) or "
      f"{pct(sv[('year', 'sqrt')]['back'], 1)} (square root), priced "
      f"{rng_b(sv[('year', 'linear')]['lo'], sv[('year', 'linear')]['hi'])}, of which access and frictions are nearly all.")
    w("")
    w("The seven-day pass is conditional. With seven-day Fedwire Funds but Fedwire Securities and the repo market still on "
      "weekdays, each weekend net debit settles in reserves before any bill can be repoed or sold, so the pass needs "
      "either weekend Reserve Bank credit against collateral or reserves held against the weekend outflow (analysis F). "
      "Reserves held count as not lendable under the absolute convention.")
    w("")
    w("Table B6. Seven-day schedule (hypothetical), sized to the routes engine's binds a year: lendable share with weekend "
      "Reserve Bank credit, and with reserves held against the weekend peak debit at the routes engine's bind rate.")
    w("")
    rows = []
    for sc in SCALINGS:
        rows.append((sc, "weekend Reserve Bank credit (no reserves held)", pct(_sv[("year", sc)]["back"], 1), "0",
                     f"{SEVEN_CREDIT[sc]:.3f}", s2_txt(SEVEN_CREDIT[sc])))
    for r_ in SEVEN_RES:
        rows.append((r_["sc"], f"reserves held, sized over the {r_['lab']}", pct(r_["bills"], 1), pct(r_["res"], 1),
                     f"{r_['lend']:.3f}", s2_txt(r_["lend"])))
    w(table(["Scaling", "Weekend cash source", "Bills backing the facility", "Reserves held", "Lendable share (absolute)",
             "S2"], rows))
    w("")
    w("Seven-day operation passes S2 only with weekend Reserve Bank credit; with reserves held against the weekend outflow "
      "it fails under every row, because the reserves cost the lendable share the facility's bills had saved.")
    w("")
    w("### Elapsed hours: the daylight-saving check")
    w("")
    w(f"The convention is nominal Eastern schedule hours. Computed with {TZ_NY} offsets and differenced in UTC, the "
      "windows that span a daylight-saving change are:")
    w("")
    w(table(["Year", "Closed window", "Nominal hours", "Elapsed hours"],
            [(y, f"{wd['prev'].strftime('%a %d %b')} {FEDWIRE_CLOSE_HOUR}:00 to {(wd['next'] - dt.timedelta(days=1)).strftime('%a %d %b')} "
                 f"{FEDWIRE_OPEN_HOUR_PREV_DAY}:00", wd["hours"], f"{wd['elapsed']:g}") for y, wd in DST_ROWS]))
    w("")
    w(f"Annual closed hours are unchanged ({', '.join(f'{y}: {EL_TOTAL[y]:,.0f}' for y in YEARS)} elapsed). "
      f"The announced 22x6 and seven-day schedules close on Saturday evening or every evening, so no window spans the "
      f"2:00 a.m. Sunday change: {SCEN[1]['dst_n']} and {SCEN[2]['dst_n']} windows differ. Each printed figure of this "
      "section recomputed on elapsed hours, compared at its printed precision:")
    w("")
    w(table(["Figure", "Nominal hours (printed)", "Elapsed hours", "Same at printed precision"],
            [(lab, a_, b_, "yes" if a_ == b_ else "NO") for lab, a_, b_ in DST_CMP]))
    w("")
    w(("No printed figure changes." if not DST_CHANGED else
       f"{len(DST_CHANGED)} printed figure(s) change: " + "; ".join(f"{l} {a_} to {b_}" for l, a_, b_ in DST_CHANGED) + ".")
      + " The square-root 22x6 case, which misses S2 by "
      f"{S2_MIN - SCEN[1][('max', 'sqrt')]['lend']:.3f} on nominal hours, misses by "
      f"{S2_MIN - SCEN[1][('max', 'sqrt', 'el')]['lend']:.3f} on elapsed hours.")
    w("")
    # ---------------------------------------------------------------- 5 C
    w("## 5. Liquidity-buffer test (analysis C, a sensitivity, never the base case)")
    w("")
    w("The bank holds a liquid-asset buffer b of the tokenized balance anyway, and the facility's backing is drawn from "
      "it up to b. S2 stays on the absolute convention: bills or reserves held for the always-on tier are not lendable "
      "whether or not they are a pre-existing buffer, so the lendable share is 1 minus the share at every buffer and a "
      "buffer cannot lift S2 above that. Reported separately, and not the S2 metric, is the incremental lending "
      "displacement relative to a bank that already holds the buffer, max(0, share - b); 1 minus it is the figure an "
      "earlier version of this engine reported as the lendable share. The standing-capacity term on the covered part "
      f"uses a custody-and-positioning spread of {rng_b(*CUSTODY)} in place of the {rng_b(*R7_ENC)} encumbrance spread "
      "[author assumption (illustrative)]. At b 0 the price equals the routes engine's.")
    w("")
    hdr = (["Always-on share", "Lendable share, absolute (every b)", "S2"]
           + [f"b {b:.0%}: 1 - incremental displacement" for b in BUFFER_SET] + ["Smallest b with displacement at most 0.1"])
    rows = []
    for s_ in R7_SHARE_SET:
        lab_ = BUF[(s_, BUFFER_SET[0])][0]["lend"]
        rows.append([f"{s_:.0%}", f"{lab_:.3f}", s2_txt(lab_)] + [f"{BUF[(s_, b)][0]['incr']:.3f}" for b in BUFFER_SET]
                    + [pct(BUF_MIN[s_], 2)])
    w("Table C1. Lendable share and S2 on the absolute convention, and, separately, 1 minus the incremental lending "
      "displacement relative to a bank that already holds the buffer (not the S2 metric), by always-on share and buffer.")
    w("")
    w(table(hdr, rows))
    w("")
    rows = []
    for s_ in R7_SHARE_SET:
        rows.append([f"{s_:.0%}"] + [rng_b(BUF[(s_, b)][0]["price"], BUF[(s_, b)][1]["price"]) for b in BUFFER_SET])
    w("Table C2. Price range, bps a year on the whole balance, by always-on share and buffer.")
    w("")
    w(table(["Always-on share"] + [f"b {b:.0%}" for b in BUFFER_SET], rows))
    w("")
    w(f"At a 20% always-on share the lendable share is {BUF[(0.20, 0.10)][0]['lend']:.3f} at every buffer: S2 "
      f"{'passes' if passes_s2(BUF[(0.20, 0.10)][0]['lend']) else 'fails'}. "
      f"Relative to a bank that already holds the buffer, the facility displaces {pct(BUF[(0.20, 0.10)][0]['disp'], 0)} of "
      f"the balance from lending with a 10% buffer and {pct(BUF[(0.20, 0.20)][0]['disp'], 0)} with a 20% buffer (1 minus "
      f"displacement {BUF[(0.20, 0.10)][0]['incr']:.3f} and {BUF[(0.20, 0.20)][0]['incr']:.3f}); that is the lending the "
      f"facility costs on top of the buffer, not the share of the balance that funds loans. Prices: "
      f"{rng_b(BUF[(0.20, 0.10)][0]['price'], BUF[(0.20, 0.10)][1]['price'])} with a 10% buffer and "
      f"{rng_b(BUF[(0.20, 0.20)][0]['price'], BUF[(0.20, 0.20)][1]['price'])} with a 20% buffer.")
    w("")
    rows = [(pct(b, 0), pct(lft, 1), pct(lc, 1)) for b, lft, lc in DOUBLE]
    w(f"Table C3. The double call: share of the buffer left for Monday outflows after the weekend's net debit is settled "
      f"in central bank money at Sunday's opening, at a 20% always-on share. The 99th-percentile weekend of the open "
      f"debtor cohort (A, Gaussian, rho 0.30, M {M_BASE}) has a cohort-average secured debit of {pct(MC_X['sec99'], 1)} "
      f"of the tier, {pct(D99_BAL, 2)} of the balance; a member at its cap has settled the full tier, 20% of its balance.")
    w("")
    w(table(["Buffer b", "Left for Monday, cohort-average member on the 99th-percentile weekend", "Left for Monday, member at its cap"], rows))
    w("")
    b20 = [x for x in DOUBLE if abs(x[0] - 0.20) < 1e-12][0]
    w(f"Counting the buffer for both the facility and the bank's own Monday outflows double-counts it: with a 20% buffer the "
      f"cohort-average member has {pct(b20[1], 1)} of the buffer left after the 99th-percentile weekend, and a member whose "
      f"cap bound has {pct(b20[2], 1)}.")
    w("")
    # ---------------------------------------------------------------- 6 D
    w("## 6. Non-members through a sponsoring member (analysis D)")
    w("")
    w("A non-member reaches the facility through a member that carries the non-member's net debit on its own cap, backed by "
      "bills the non-member pledges to the sponsor in a back-to-back repo. The non-member pays the R7 terms, a sponsor "
      f"margin of {rng_b(*SPONSOR_MARGIN)} per always-on tier dollar and the sponsor's extra access cost of "
      f"{rng_b(*SPONSOR_ACCESS)} on its whole balance [author assumption (illustrative)].")
    w("")
    rows = [(pct(r["s"], 0), rng_b(r["mlo"], r["mhi"]), rng_b(r["lo"], r["hi"]),
             f"{r['lo'] / r['s'] / BP:.1f} to {r['hi'] / r['s'] / BP:.1f}", rng_b(r["lo"] - r["mlo"], r["hi"] - r["mhi"]))
            for r in SPON]
    w("Table D1. Price for a sponsored non-member.")
    w("")
    w(table(["Always-on share", "Member price, whole balance", "Non-member price, whole balance", "Non-member, per tier dollar",
             "Sponsorship adds, whole balance"], rows))
    w("")
    s20 = [r for r in SPON if abs(r["s"] - 0.20) < 1e-12][0]
    s5 = [r for r in SPON if abs(r["s"] - 0.05) < 1e-12][0]
    w(f"Sponsorship adds {rng_b(s20['lo'] - s20['mlo'], s20['hi'] - s20['mhi'])} on the whole balance at a 20% share, taking "
      f"the non-member to {rng_b(s20['lo'], s20['hi'])}; at 5% it adds {rng_b(s5['lo'] - s5['mlo'], s5['hi'] - s5['mhi'])}, "
      f"to {rng_b(s5['lo'], s5['hi'])}, or {s5['lo'] / 0.05 / BP:.0f} to {s5['hi'] / 0.05 / BP:.0f} per tier dollar, because "
      "the extra access cost is fixed and the tier is small.")
    w("")
    w("What the sponsor bears [author's reading]: cap room, not credit, when the back-to-back repo is full. The non-member's "
      "net debit counts against the sponsor's cap, so every dollar of it is a dollar the sponsor's own depositors cannot "
      "use that weekend; the sponsor's credit exposure to the non-member is the haircut-breach risk on the pledged bills and "
      "the timing gap if the non-member is closed (analysis E), the same as a net creditor's. If the sponsor adds the "
      "non-member's bills to its own cap, the pooled cap binds less often than two separate caps would, but the sponsor's "
      "depositors then queue behind the non-member's: for two equal tiers drawn as net debtors (an open pair, receivers "
      "outside it) under the Gaussian factor at rho 0.30, the pooled "
      f"cap binds in {psig(MC_X['pair_pool'])} of weekends against {psig(MC_X['pair_sep'])} for either separate cap binding "
      "(Monte Carlo), so a sponsor would want a sub-limit for the non-member.")
    w("")
    # ---------------------------------------------------------------- 7 E
    w("## 7. Monday cash for net creditors when a member is closed (analysis E)")
    w("")
    w(f"If a member is closed on the last business day before a weekend, its net creditors hold its pledged bills. Two "
      f"provisions apply [12 U.S.C. 1821(e)(8)(G)(ii) and (e)(10)(B); author's reading, Chapter 6]: (e)(10)(B) stays "
      f"termination, liquidation and netting rights until {QFC_STAY_END_HOUR}:00 ET on the next business day (business "
      f"day as in (e)(10)(D)); (e)(8)(G)(ii) suspends payment and delivery under the contract itself during that period. "
      f"Neither suspends payments in general. Two intervals follow. The legal stay interval runs from the scheduled "
      f"Fedwire opening at which settlement would have happened to the end of the stay: {GAP_H_NORMAL} hours on a normal "
      f"weekend (Sunday 21:00 to Monday 17:00). The operational collateral-to-cash interval runs to the first time the "
      f"collateral can be delivered against cash: the stay ends after the Fedwire Securities secondary-market cutoff "
      f"(3:15 p.m. ET), so delivery waits for the next securities opening, Tuesday 8:30 a.m., "
      f"{GAP_H_OPER:g} hours after Sunday 21:00. The creditor bridges the gap by borrowing against its own bills at "
      f"{SECURED_RATE:.1%} plus {rng_b(*BRIDGE_SPREAD)}. A member is closed in a year with probability lambda_P = "
      f"{pct(LAMBDA_P)} (the routes engine's LAMBDA_P). The closed member's net debit is spread equally over the other "
      f"{M_BASE - 1} members; per creditor the gap lies between that and the whole debit, if one creditor received it all.")
    w("")
    w("Table E0. The two intervals, normal weekend and Monday holiday (nominal Eastern clock).")
    w("")
    w(table(["Case", "Settlement would have happened", "Stay ends", "Collateral delivered against cash", "Legal stay interval, hours",
             "Operational interval, hours"],
            [(lab, g["open"].strftime("%a %d %b %H:%M"), g["stay"].strftime("%a %d %b %H:%M"),
              g["oper"].strftime("%a %d %b %H:%M"), f"{g['legal']:g}", f"{g['op']:g}") for lab, g in GAP_CASES]))
    w("")
    w("A Monday holiday lengthens neither interval, because the opening moves with the holiday.")
    w("")
    rows = [(r["lab"], pct(r["d"], 2), pct(r["per"], 3),
             f"{r[('exp', 0)] / BP:.5f} to {r[('exp', 1)] / BP:.5f}", f"{r[('exp_op', 0)] / BP:.5f} to {r[('exp_op', 1)] / BP:.5f}",
             f"{r[('exp_spread', 0)] / BP:.5f} to {r[('exp_spread', 1)] / BP:.5f}",
             f"{r[('exp_spread_op', 0)] / BP:.5f} to {r[('exp_spread_op', 1)] / BP:.5f}",
             f"{r[('event', 0)] / BP:.4f} to {r[('event', 1)] / BP:.4f}", f"{r[('event_op', 0)] / BP:.4f} to {r[('event_op', 1)] / BP:.4f}")
            for r in MON]
    w("Table E1. The Monday cash gap and its cost, on the legal stay interval and on the operational interval.")
    w("")
    w(table(["Closed member's net debit", "Debit, share of its balance", "Gap per creditor, share of its balance",
             f"Expected cost, bps a year on the whole balance, {GAP_H_NORMAL} h (rate + spread)",
             f"Same, {GAP_H_OPER:g} h", f"Memo: spread only, {GAP_H_NORMAL} h", f"Memo: spread only, {GAP_H_OPER:g} h",
             f"Cost per event to one creditor, bps of its balance, {GAP_H_NORMAL} h", f"Same, {GAP_H_OPER:g} h"], rows))
    w("")
    m0 = MON[0]
    w(f"At most, with the closed member at its cap, the expected bridging cost is {m0[('exp', 0)] / BP:.5f} to "
      f"{m0[('exp', 1)] / BP:.5f} bps a year on the whole balance over the legal interval and {m0[('exp_op', 0)] / BP:.5f} "
      f"to {m0[('exp_op', 1)] / BP:.5f} over the operational one: the Monday gap is not a price term. It is a size: "
      f"{pct(m0['d'], 0)} of the closed member's balance, {pct(m0['per'], 2)} of each creditor's if spread evenly, all of it at "
      f"one creditor that received the whole debit, held for up to {GAP_H_OPER:g} hours. On the 99th-percentile weekend of "
      f"the open debtor cohort of analysis A the cohort-average net debit is {pct(D99_BAL, 2)} of the balance, "
      f"{pct(D99_BAL / (M_BASE - 1), 3)} per creditor. The arithmetic does not establish that a bridge is available; the "
      "creditor's claim accrues the usage charge at the overnight secured rate while it waits, so the spread-only memo "
      "is the closer reading of the net cost.")
    w("")
    # ---------------------------------------------------------------- 8 F
    w("## 8. The Sunday settlement cash source (analysis F)")
    w("")
    w(f"Every net debtor, not only a failed one, settles at the Sunday {FEDWIRE_OPEN_HOUR_PREV_DAY}:00 Fedwire Funds "
      "opening in reserves. Its pledged bills are not reserves and Fedwire Securities is closed until Monday "
      "8:30 a.m., so the debtor pays from its own reserve balance or a collateralized Reserve Bank "
      "daylight overdraft, repaid on Monday after the bills are repoed or sold. The requirement: at the Sunday opening "
      f"the debtor holds reserves or collateralized intraday credit capacity of at least its cap, {pct(R7_SHARE, 0)} of "
      "the balance, with the collateral pledged at the Reserve Bank separate from the bills pledged to the facility. "
      "The facility's price (Section 1 terms) does not include this capacity; the daylight overdraft fee sits in one "
      f"constant, DOD_FEE, {b1(DOD_FEE)} bps a year for collateralized overdrafts [reported figure, Federal Reserve Policy "
      f"on Payment System Risk], with {b1(DOD_FEE_SET[-1])} bps for uncollateralized overdrafts as a sensitivity. The "
      f"fee follows the policy's convention (Section II.C and footnote 58): the annual rate is quoted on a 24-hour day "
      f"and a {PSR_YEAR_DAYS}-day year, the effective daily rate is the annual rate over {PSR_YEAR_DAYS}, truncated "
      f"({psr_daily_rate(DOD_FEE_SET[-1]):.7f} at {b1(DOD_FEE_SET[-1])} bps), and it is charged on the average overdraft "
      "over the minutes of the 24-hour day, before the $150 fee waiver per reserve-maintenance period. The overdraft is "
      f"repaid by Monday {DOD_REPAY_HOUR}:00 ET: a solvent debtor repays from a delivery-versus-payment sale or bilateral "
      "repo of its bills settling Monday morning after the 8:30 a.m. securities opening [author "
      "assumption (illustrative)].")
    w("")
    w(table(["Daylight overdraft fee, bps a year", "Expected secured debit settled each Sunday, share of the balance",
             "Overdraft hours", "Expected fee, bps a year on the whole balance"],
            [(b1(f_), pct(SUN_DEBIT, 3), f"{DOD_H:g}", f"{DOD_COST[f_] / BP:.4f}") for f_ in DOD_FEE_SET]))
    w("")
    w(f"Repaid only at Monday {QFC_STAY_END_HOUR}:00 ({DOD_H_1700:g} hours), the uncollateralized fee would be "
      f"{DOD_COST_1700[DOD_FEE_SET[-1]] / BP:.4f} bps a year; the collateralized fee stays "
      f"{DOD_COST_1700[DOD_FEE] / BP:.4f}.")
    w("")
    w(table(["Sunday cash source", "Requirement", "Lendable share (absolute)", "S2"],
            [(lab, req, f"{ln:.2f}", s2_txt(ln)) for lab, req, ln in SUN_ROWS]))
    w("")
    w("The fee is negligible either way; the requirement is not. A collateralized overdraft keeps the lendable share at "
      f"{1 - R7_SHARE:.2f} only if the Reserve Bank collateral is loans the bank already holds; reserves held, or securities "
      f"bought to pledge, take it to {1 - 2 * R7_SHARE:.2f}. For the seven-day schedule, see Table B6.")
    w("")
    # ---------------------------------------------------------------- 8
    w("## 9. Conventions and limits")
    w("")
    w("- Each member's figure is its peak net debit during the closed window to all counterparties, members and "
      "non-members, not its terminal net position; payment paths and the release of queued payments are not modelled. "
      "Members are equal in size and form an open debtor cohort whose receivers sit outside the modelled set, so every "
      "multi-member statistic describes that cohort, not a closed membership in which signed net positions sum to zero.")
    w("- Weekends are independent of each other; the factor is redrawn every weekend. Serial dependence across weekends "
      "would change annual incidence, annual maxima and run lengths in ways the engine does not model; at fixed weekly "
      "marginals it leaves the expected count of binds unchanged.")
    w("- The linear and square-root scalings of the outflow with window hours are illustrative; neither is estimated.")
    w(f"- The calendar constants (Fedwire hours, 2026 and 2027 weekday closings) are reported figures ({HOURS_SRC}; "
      f"{HOLIDAYS_SRC}) and sit at the top of the script. The 22x6 scenario is announced ({SIX_DAY_SRC}), voluntary for "
      "participants and not yet in effect. The QFC business-day definition (12 U.S.C. 1821(e)(10)(D)) also excludes days "
      "the New York Stock Exchange is closed, Good Friday among them; the Monday-cash hours here use the Reserve Bank "
      "calendar only.")
    w("- The cap ladder holds the weekend peak debit in balance terms fixed and moves the backing. Lendable share is 1 "
      "minus the always-on share throughout, the routes engine's absolute convention, including analysis C, where the "
      "buffer's effect is reported only as incremental lending displacement.")
    w("- Window lengths are nominal Eastern schedule hours; the elapsed-hours check in Section 4 shows the daylight-saving "
      "effect on every printed calendar figure.")
    _g = SCEN[1][("max", "linear")]["back"]
    w(f"- Counting the grossed-up bills (share / {1 - R7_HAIRCUT:.2f}) as non-lendable instead, the S2 boundary is a "
      f"{(1 - S2_MIN) * (1 - R7_HAIRCUT) * 100:.1f} percent always-on share, not {(1 - S2_MIN) * 100:.0f}. The 22x6 lendable "
      f"share is {1 - _g:.3f} under the routes engine's convention and {1 - _g / (1 - R7_HAIRCUT):.3f} counting the bills, "
      f"a 0.2-point move; the buffer at which a 20% share's incremental displacement falls to 0.1 is {pct(BUF_MIN[0.20], 2)} "
      f"under the first and {pct(BUF_MIN_GROSS[0.20], 2)} under the second, a 0.41-point move (the gross-up on a 20% share).")
    w("- Everything is illustrative and calibrated to no bank, facility or member.")
    w("")
    RESULTS_MD.write_text("\n".join(L), encoding="utf-8")


# =============================================================================
# 10. FIGURES
# =============================================================================
def make_figures():
    import logging
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.patches import Patch
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)

    # palette and frame of the routes engine's figures
    NAVY, STEEL, SLATE, MIST, INK, GRID, ACCENT = "#1F3A5F", "#4F74A8", "#8A9AAE", "#C9D3DF", "#2B2B2B", "#E3E7EC", "#D2851F"
    MUTED, DARKACC, BRICK, SAGE = "#4A5361", "#9A5A0A", "#A4473A", "#6E8F7A"
    fam = "Inter" if any(f.name == "Inter" for f in font_manager.fontManager.ttflist) else "DejaVu Sans"
    plt.rcParams.update({
        "font.family": fam, "font.size": 10, "axes.edgecolor": "#8C96A3", "axes.linewidth": 0.8,
        "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
        "axes.spines.right": False, "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "text.color": INK, "hatch.color": "#FFFFFF", "hatch.linewidth": 1.0, "svg.hashsalt": "settlement",
    })
    SRC = "Source: author's calculations."
    ILL = "Illustrative parameters, calibrated to no bank."

    def frame(fig, title, subtitle, source):
        fig.text(0.06, 0.955, title, fontsize=14, fontweight="semibold", ha="left", va="top", color=INK)
        fig.text(0.06, 0.905, subtitle, fontsize=10, ha="left", va="top", color="#5A6472")
        fig.text(0.06, 0.03, source, fontsize=7.5, ha="left", va="bottom", color="#6B7480")

    def save(fig, n):
        fig.savefig(FIG(n), dpi=200, metadata={"Software": None})
        plt.close(fig)

    RCOL = {0.0: MIST, 0.15: SLATE, 0.30: STEEL, 0.50: NAVY}

    # ---- S01: same-weekend binds ----------------------------------------------------------------------------
    ks = np.arange(1, 13)
    fig, axs = plt.subplots(1, 2, figsize=(11, 5.6), sharey=True)
    fig.subplots_adjust(left=0.08, right=0.97, top=0.78, bottom=0.2, wspace=0.08)
    for ax, cop in zip(axs, COPULAS):
        for rho in RHO_SET:
            pm = PMF[(cop, rho, M_BASE, R7_OUT_SIG)]
            ys = np.array([max(p_atleast(pm, int(k)), 1e-12) for k in ks])
            ax.plot(ks, ys, color=RCOL[rho], lw=2.0, marker="o", ms=3.5, label=f"rho {rho:.2f}")
        ax.set_yscale("log")
        ax.set_ylim(1e-6, 1.0)
        ax.set_xticks(ks)
        ax.axhline(0.01, color=ACCENT, lw=1.0, ls=(0, (4, 2)))
        ax.set_title(f"{COP_NAME[cop]} factor", fontsize=10, loc="left")
        ax.set_xlabel(f"k: number of the {M_BASE} members whose cap binds on the same weekend", fontsize=9, color=MUTED)
        ax.yaxis.grid(True, color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axs[0].set_ylabel("P(at least k members bind), per weekend (log)", fontsize=9.5, color=MUTED)
    axs[0].text(12, 0.012, "1% of weekends", ha="right", va="bottom", fontsize=8, color=DARKACC)
    axs[1].legend(frameon=False, fontsize=8.5, loc="upper right")
    frame(fig, "When one cap binds, do others bind with it?",
          f"Each member's cap binds in {pct(P_MEMBER[R7_OUT_SIG], 2)} of weekends under every curve (lognormal peak debit, "
          f"median 25% of the tier, sigma {R7_OUT_SIG});\nthe factor decides whether binds arrive alone or together. An open "
          f"cohort of {M_BASE} equal net debtors, receivers outside the modelled set.",
          f"{SRC} Quadrature over the common factor (and the chi-square mixing variable for t). {ILL}")
    save(fig, 1)

    # ---- S02: calendar ----------------------------------------------------------------------------------------
    fig = plt.figure(figsize=(11, 6.4))
    ax1 = fig.add_axes([0.2, 0.52, 0.76, 0.27])
    ax2 = fig.add_axes([0.2, 0.13, 0.76, 0.27])
    y0 = dt.datetime(2026, 1, 1)
    rowy = {2: 0, 26: 1, 50: 2, 74: 3}
    tcol = {2: SLATE, 26: SAGE, 50: NAVY, 74: ACCENT}
    for wdw in CAL[2026]["ws"]:
        x = (wdw["start"] - y0).total_seconds() / 86400
        h = wdw["hours"]
        if h == 2:
            ax1.vlines(max(x, 0), rowy[h] - 0.3, rowy[h] + 0.3, color=tcol[h], lw=0.5)
        else:
            ax1.broken_barh([(max(x, 0), h / 24 - (max(x, 0) - x))], (rowy[h] - 0.32, 0.64), facecolors=tcol[h])
    c26 = dict(CAL[2026]["rows"])
    ax1.set_yticks(list(rowy.values()))
    ax1.set_yticklabels([f"{wtype(h)} ({h} h): {c26.get(h, 0)}" for h in rowy], fontsize=8.5)
    mstart = [(dt.datetime(2026, m, 1) - y0).days for m in range(1, 13)]
    ax1.set_xticks(mstart)
    ax1.set_xticklabels([dt.date(2026, m, 1).strftime("%b") for m in range(1, 13)], fontsize=8.5)
    ax1.set_xlim(0, 365)
    ax1.set_ylim(-0.6, 3.6)
    ax1.set_title("Closed windows of 2026, by the business day that ends them", fontsize=9.5, loc="left")
    xs = np.arange(4)
    hs = [2, 26, 50, 74]
    pl = [p_win(h, scaling="linear") * 100 for h in hs]
    pq = [p_win(h, scaling="sqrt") * 100 for h in hs]
    ax2.bar(xs - 0.18, pl, width=0.34, color=[tcol[h] for h in hs], label="Outflow scales with hours / 50")
    ax2.bar(xs + 0.18, pq, width=0.34, color=[tcol[h] for h in hs], alpha=0.45, hatch="////",
            label="Square root of hours / 50")
    for x, a, b in zip(xs, pl, pq):
        ax2.text(x - 0.18, a + 0.25, f"{a:.2f}%" if a >= 0.01 else "<0.01%", ha="center", fontsize=8, color=INK)
        ax2.text(x + 0.18, b + 0.25, f"{b:.2f}%" if b >= 0.01 else "<0.01%", ha="center", fontsize=8, color=MUTED)
    ax2.axhline(P_MEMBER[R7_OUT_SIG] * 100, color=INK, lw=0.9, ls=(0, (4, 2)))
    ax2.text(0.6, P_MEMBER[R7_OUT_SIG] * 100 + 0.25, "normal weekend under P1", ha="left", fontsize=8, color=INK)
    ax2.set_xticks(xs)
    ax2.set_xticklabels([f"{wtype(h)} ({h} h)" for h in hs], fontsize=8.5)
    ax2.set_ylabel("P(cap binds) per window, %", fontsize=9, color=MUTED)
    ax2.set_ylim(0, max(pl) * 1.25)
    ax2.yaxis.grid(True, color=GRID, lw=0.8)
    ax2.set_axisbelow(True)
    ax2.set_title(f"Bind probability per window with the cap sized for the normal weekend ({R7_SHARE:.0%} backing all year)",
                  fontsize=9.5, loc="left")
    ax2.legend(handles=[Patch(facecolor=SLATE, edgecolor="none", label="Outflow scales with hours / 50"),
                        Patch(facecolor=SLATE, alpha=0.45, hatch="////", edgecolor="none",
                              label="Square root of hours / 50")],
               frameon=False, fontsize=8, loc="upper left")
    frame(fig, "The closed-window calendar",
          f"{CAL[2026]['n_ops']} business days, {CAL[2026]['total']:,} closed hours in 2026. Three-day weekends bind "
          f"{HOL_RATIO['linear'][74]:.1f} times as often as a normal weekend\nwhen outflow scales with the hours; the "
          "weekday evening gap is negligible.",
          f"{SRC} Fedwire hours and holidays: Federal Reserve Financial Services, accessed 3 November 2026. {ILL}")
    save(fig, 2)

    # ---- S03: lendable share vs always-on share: absolute (S2) and incremental displacement (not S2) ------------------
    fig, ax = plt.subplots(figsize=(11, 5.8))
    fig.subplots_adjust(left=0.08, right=0.74, top=0.8, bottom=0.17)
    sgrid = np.linspace(0.0, 0.5, 501)
    bcol = {0.05: MIST, 0.10: SLATE, 0.20: STEEL, 0.40: NAVY}
    ax.plot(sgrid * 100, [buffer_cell(float(x), 0.0, 0)["lend"] for x in sgrid], color=INK, lw=2.4,
            label="Lendable share, absolute convention,\nat every buffer (the S2 metric)")
    ax.plot([x * 100 for x in R7_SHARE_SET], [BUF[(x, 0.0)][0]["lend"] for x in R7_SHARE_SET], "o", ms=4, color=INK)
    for b in BUFFER_SET:
        if b == 0:
            continue
        ax.plot(sgrid * 100, [buffer_cell(float(x), b, 0)["incr"] for x in sgrid], color=bcol[b], lw=1.4, ls=(0, (3, 1.5)),
                label=f"buffer {b:.0%}: 1 - incremental displacement\n(not the S2 metric)")
    ax.axhline(S2_MIN, color=ACCENT, lw=1.2, label=f"S2 floor, {S2_MIN:g}")
    ax.axvline(R7_SHARE * 100, color=GRID, lw=1.0)
    ax.text(R7_SHARE * 100 + 0.4, 0.5, "routes engine's\n20% share", fontsize=8, color=MUTED, va="bottom")
    ax.set_xlim(0, 50)
    ax.set_ylim(0.45, 1.01)
    ax.set_xlabel("Always-on share of the tokenized balance, %", fontsize=9.5, color=MUTED)
    ax.set_ylabel("Share of the balance", fontsize=9.5, color=MUTED)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.text(0.755, 0.30, "Dashed lines measure the lending\nthe facility costs on top of a buffer\nthe bank holds "
             f"anyway. After a\n99th-percentile weekend a 20%\nbuffer has {pct(DOUBLE[2][1], 0)} left for the "
             "cohort-\naverage member, 0% for one at\nits cap.", fontsize=7.8, color=MUTED, va="top")
    frame(fig, "A liquidity buffer does not lift the lendable share",
          "Bills held for the always-on tier are not lendable whether or not they are a buffer, so the lendable share is "
          "1 minus\nthe share at every buffer and a 20% share fails S2. Dashed: incremental displacement, a different "
          "quantity.",
          f"{SRC} {ILL}")
    save(fig, 3)


# =============================================================================
# 11. RUN
# =============================================================================
if __name__ == "__main__":
    FIGURES.mkdir(parents=True, exist_ok=True)
    make_figures()
    write_results()
    print(f"Parity with the routes engine: {'PASS' if PARITY_OK else 'FAIL'}; method checks "
          f"{'PASS' if METHOD_OK else 'FAIL'}; Monte Carlo largest |z| {MC_MAXZ:.2f}")
    print(f"S2 bar {S2_MIN:g}" + (" (rule of record)" if rt.S2_DEFAULT_RUN else " (sensitivity run, not the rule of record)"))
    print(f"Wrote {RESULTS_MD.relative_to(ROOT)}")
    for n in range(1, N_FIGS + 1):
        print(f"Wrote {FIG(n).relative_to(ROOT)}")
    print(f"Run time {time.perf_counter() - _T_START:.1f} s")
