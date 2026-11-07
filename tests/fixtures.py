"""
Parity fixtures for the interactive dashboard (docs/index.html).

What it does
    Imports the Python workpaper (model/clearing_cost.py) and evaluates its own functions -- components(),
    pool(), pool_price(), cond_short(), cond_unpaid(), cond_loss(), uncond_short(), breakeven(),
    bisect_lp() -- for the base case of Chapter 3 and a set of varied parameter sets. Writes the inputs and
    outputs to tests/fixtures.json, which tests/parity.mjs compares against the dashboard's JavaScript.

Run (from this folder or anywhere):
    python3 -I tests/fixtures.py [path/to/clearing_cost.py]

    Without an argument the workpaper is ../model/clearing_cost.py relative to this folder
    (model/ at the repository root). Importing the workpaper computes its result tables
    (about a minute) but writes no files; only fixtures.json is written here.

Conventions
    All rates are decimals per year on the covered balance (1 bp = 1e-4). Probabilities are real-world
    (P) quantities computed with the per-bank default probability lambda_P; prices are computed on the
    pricing measure with mu x lambda_P, exactly as in the workpaper.
"""

import importlib.util
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True    # importing the workpaper leaves no __pycache__ in model/

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WP_DEFAULT = HERE / ".." / "model" / "clearing_cost.py"


def find_workpaper():
    wp = Path(sys.argv[1]) if len(sys.argv) > 1 else WP_DEFAULT
    wp = wp.resolve()
    if not wp.exists():
        raise SystemExit(f"Workpaper {wp} not found; pass its path as the first argument.")
    return wp


WP = find_workpaper()
spec = importlib.util.spec_from_file_location("clearing_cost", WP)
M = importlib.util.module_from_spec(spec)
t0 = time.perf_counter()
spec.loader.exec_module(M)          # module-level result tables run here; nothing is written to disk
print(f"Imported {WP.name} in {time.perf_counter() - t0:.0f} s")

BP = 1e-4
BASE = dict(pd=0.0025, mu=3.0, lgd=0.25, a=0.50, D=2.0, r=0.043, s_b=0.010, f=15 * BP, k=10 * BP,
            N=50, rho=0.30, copula="gauss", nu=5, theta=0.20, F=0.0, fee=20 * BP, s_lock=10 * BP,
            s_draw=200 * BP, lag=7, lgd_mode="fixed", delta=50 * BP)

CASES = [
    ("Base case: all-funded reference (theta 20%, F 0), Gaussian, rho 0.30", {}),
    ("10/10 hybrid at a 20 bps fee", dict(theta=0.10, F=0.10)),
    ("Student-t(5) copula, reference design", dict(copula="t")),
    ("rho 0.10, 5/15 split, Gaussian", dict(rho=0.10, theta=0.05, F=0.15)),
    ("PD 0.50%, rho 0.30, Student-t(5), 10/10", dict(pd=0.005, copula="t", theta=0.10, F=0.10)),
    ("N 25 (each 4%), reference design", dict(N=25)),
    ("N 100, rho 0.20, Student-t(5), 15/5", dict(N=100, rho=0.20, copula="t", theta=0.15, F=0.05)),
    ("State-dependent LGD, rho 0.30, Gaussian, 10/10", dict(lgd_mode="corr", theta=0.10, F=0.10)),
    ("State-dependent LGD, PD 0.50%, Student-t(5)", dict(lgd_mode="corr", pd=0.005, copula="t")),
    ("Single-name inputs varied, Student-t(8), 30/10 at 40 bps",
     dict(mu=4.0, lgd=0.40, a=0.30, D=3.0, r=0.039, s_b=0.015, f=10 * BP, k=5 * BP, copula="t", nu=8,
          theta=0.30, F=0.10, fee=40 * BP, s_lock=15 * BP, s_draw=300 * BP, lag=14, delta=100 * BP)),
    ("No advance dividend, 10/10, Gaussian", dict(a=0.0, theta=0.10, F=0.10, delta=75 * BP)),
    ("N 10, rho 0.30, Student-t(5), capacity 30%", dict(N=10, copula="t", theta=0.30)),
    ("PD 1.00%, rho 0.20, Gaussian, 5/15 at 5 bps", dict(pd=0.01, rho=0.20, theta=0.05, F=0.15, fee=5 * BP,
                                                          delta=150 * BP)),
]
CURVE_CAPS = [0.06, 0.10, 0.12, 0.16, 0.20, 0.24, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
SPLIT_SHARES = [0.25, 0.50, 0.75]   # facility share of capacity for the buffer-versus-facility readout


def set_case(p):
    """Workpaper globals that pool_price() reads at call time: S_B (funding spread) and the t-copula nu."""
    M.S_B = p["s_b"]
    M._t_nodes.__defaults__ = (p["nu"], 401, 240)
    M._POOL_CACHE.clear()


def mode_args(p):
    """Fixed LGD: mode = the LGD value and a = the advance dividend. State-dependent: mode 'corr', a None."""
    return ("corr", None) if p["lgd_mode"] == "corr" else (float(p["lgd"]), p["a"])


def price(p, cop, pd=None, theta=None, F=None):
    mode, a = mode_args(p)
    return M.pool_price(pd=p["pd"] if pd is None else pd, rho=p["rho"], mode=mode,
                        theta=p["theta"] if theta is None else theta, F=p["F"] if F is None else F,
                        fee=p["fee"], f=p["f"], s_lock=p["s_lock"], s_draw=p["s_draw"], a=a, mu=p["mu"],
                        d=p["D"], lag=p["lag"], copula=cop, n_names=p["N"], r=p["r"])


def reliability(p, cop):
    mode, a = mode_args(p)
    P = M.pool(p["pd"], p["rho"], mode, a, cop, p["N"])
    cap = p["theta"] + p["F"]
    sf = M.cond_short(P, cap)
    unpaid = M.cond_unpaid(P, cap)
    return dict(uncond=M.uncond_short(P, cap), p_fail=M.p_fail(P, p["theta"], p["F"]), cond=sf,
                unpaid=unpaid, severity=(unpaid / sf if sf > 0 else 0.0), loss=M.cond_loss(P, cap),
                curve=[M.cond_short(P, c) for c in CURVE_CAPS])


def single(p, lp=None):
    return M.components(lambda_p=p["pd"] if lp is None else lp, mu=p["mu"], lgd=p["lgd"], a=p["a"], d=p["D"],
                        r=p["r"], s_b=p["s_b"], k=p["k"], f=p["f"])


def run_case(label, over):
    p = {**BASE, **over}
    set_case(p)
    t = time.perf_counter()
    cop = p["copula"]
    out = {"single": single(p)}
    pp = price(p, cop)
    out["pool"] = {k: pp[k] for k in ("credit", "access", "lock", "commit", "drawn", "k", "f", "c_star")}
    out["rel"] = {}
    with M._trim_cache():
        for c in ("gauss", "t"):
            out["rel"][c] = reliability(p, c)
    cap = p["theta"] + p["F"]
    allf = price(p, cop, theta=cap, F=0.0)["c_star"]
    out["rule"] = {"all_funded": allf,
                   "splits": [dict(share=s, theta=cap * (1 - s), F=cap * s,
                                   c_star=price(p, cop, theta=cap * (1 - s), F=cap * s)["c_star"])
                              for s in SPLIT_SHARES]}
    d = p["delta"]
    out["be_single"] = M.breakeven(lambda lp: single(p, lp)["c_star"], d)
    with M._trim_cache():
        out["be_pool"] = M.bisect_lp(lambda lp: price(p, cop, pd=lp)["c_star"], d)
    M._POOL_CACHE.clear()
    print(f"  {label}: {time.perf_counter() - t:.1f} s; single {out['single']['c_star'] / BP:.2f}, "
          f"pool {pp['c_star'] / BP:.2f} bps; cond G {out['rel']['gauss']['cond']:.5f} t {out['rel']['t']['cond']:.4f}")
    return dict(label=label, inputs=p, out=out)


def numerics():
    """Spot values of the normal CDF and its inverse, for the JS special functions."""
    xs = [-38.0, -30.0, -12.0, -8.0, -5.0, -3.0, -1.5, -0.3, 0.0, 0.7, 2.0, 4.5, 9.0]
    ps = [1e-12, 1e-6, 0.0025, 0.0075, 0.02, 0.3, 0.5, 0.9, 0.999]
    return dict(ncdf=[[x, float(M.ncdf([x])[0])] for x in xs],
                inv=[[q, M._ND.inv_cdf(q)] for q in ps])


fixtures = dict(source=WP.name, base=BASE, curve_caps=CURVE_CAPS, numerics=numerics(),
                cases=[run_case(lbl, ov) for lbl, ov in CASES])
(HERE / "fixtures.json").write_text(json.dumps(fixtures, indent=1), encoding="utf-8")
print(f"Wrote {HERE / 'fixtures.json'} ({len(fixtures['cases'])} cases)")
