"""
Parity fixtures for the settlement clock dashboard (docs/settlement.html).

What it does
    Imports the settlement engine (model/settlement.py), which loads the routes engine (model/routes.py) and, through
    it, the clearing-cost and mutual-tail engines. For the base case and a set of varied parameter sets it sets the
    engines' parameters in memory, re-runs the engines' own code for the blocks that depend on them, and records the
    outputs the dashboard shows. Writes tests/fixtures_settlement.json, which tests/parity_settlement.mjs compares
    against the dashboard's JavaScript.

    Re-run blocks (the engines' own source, executed again in the engine's namespace after the parameters are set):
      routes.py      the R7, R8 and R9 block and the Sunday settlement cash memo (section 3, from "R7: always-on
                     netting facility" to "R2 and R3 economics"), and section 5 (routes, variants, screens, the rule,
                     and the by-deposit-type table of Section 10b) up to the S2 bar sensitivity.
      settlement.py  the imports from routes.py, the median boundary and Table A6 block, the closed-window calendar
                     (analysis B) and the Sunday settlement cash source (analysis F).
    The per-member and joint cap ladders and the same-weekend count distribution are computed by calling the
    engine's functions (backing_for, solve_pd, count_pmf, p_atleast) directly. Nothing is written to model/.

Run (from this folder or anywhere):
    /path/to/python -I -B tests/fixtures_settlement.py [path/to/settlement.py]

    Without an argument the engine is ../model/settlement.py relative to this folder. Importing it computes the routes
    engine's tables and the settlement engine's Monte Carlo (several minutes) but writes no files; only
    fixtures_settlement.json is written here.

Conventions
    Rates are decimals per year on the whole tokenized balance (1 bp = 1e-4). Shares are of the tokenized balance.
    The dashboard's median weekend peak debit is a share of the balance (medBal); the engines carry it as a share of
    the always-on tier (R7_OUT_MED = medBal / share), so the two agree at the base (5% = 25% of 20%).
"""

import importlib.util
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True    # importing the engines leaves no __pycache__ in model/

HERE = Path(__file__).resolve().parent
ST_DEFAULT = HERE / ".." / "model" / "settlement.py"
BP = 1e-4


def find_engine():
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else ST_DEFAULT
    p = p.resolve()
    if not p.exists():
        raise SystemExit(f"Engine {p} not found; pass the path of settlement.py as the first argument.")
    return p


ST_PATH = find_engine()
RT_PATH = ST_PATH.parent / "routes.py"
sys.argv = sys.argv[:1]           # the engines parse --s2-min from the command line; run at the rule of record
spec = importlib.util.spec_from_file_location("settlement", ST_PATH)
st = importlib.util.module_from_spec(spec)
sys.modules["settlement"] = st
t0 = time.perf_counter()
spec.loader.exec_module(st)       # loads routes.py (and its engines) and runs both engines' module-level tables
rt, cc, mt = st.rt, st.cc, st.rt.mt
print(f"Imported {ST_PATH.name} (and routes.py) in {time.perf_counter() - t0:.0f} s")

RT_SRC = RT_PATH.read_text(encoding="utf-8")
ST_SRC = ST_PATH.read_text(encoding="utf-8")


def segment(src, start, end, name):
    i = src.index(start)
    j = src.index(end, i)
    return compile(src[i:j], f"<{name}: {start[:40]}>", "exec")


# blocks of the engines' own source re-run after the parameters are set
RT_SEG_R7 = segment(RT_SRC, "# --- R7: always-on netting facility", "# --- R2 and R3 economics", "routes.py")
RT_SEG_5 = segment(RT_SRC, "# 5. ROUTES, VARIANTS AND SCREENS", "# --- S2 bar sensitivity: every route", "routes.py")
ST_SEG_IMP = segment(ST_SRC, "R7_SHARE, R7_HAIRCUT = rt.R7_SHARE", "# --- A. same-weekend factor model", "settlement.py")
ST_SEG_LAD = segment(ST_SRC, "# --- cap ladder", "LADDER = []", "settlement.py")
ST_SEG_MED = segment(ST_SRC, "# the largest median weekend outflow", "# 4. B. CLOSED-WINDOW CALENDAR", "settlement.py")
ST_SEG_CAL = segment(ST_SRC, "def operating_days(", "# 5. C. LIQUIDITY-BUFFER", "settlement.py")
ST_SEG_SUN = segment(ST_SRC, "def lognorm_min_mean(", "# 8. PARITY AND METHOD CHECKS", "settlement.py")

# ---- the published (unpatched) engine values, recorded before any parameter is changed --------------------------
PUBLISHED = dict(
    r7=dict(lo=rt.R7_LO, hi=rt.R7_HI, base=rt.R7_BASE, lend=rt.R7_LEND),
    r9=dict(lo=rt.R9_LO, hi=rt.R9_HI, base=rt.R9_BASE, lend=rt.R9_LEND),
    cross=rt.R9_BE_SHARE,
    sun={c: dict(lo=v["lo"], hi=v["hi"], base=v["base"], lend=v["lend"], cross=v["cross"], ex_base=v["ex_base"])
         for c, v in rt.R7_SUN.items()},
    tie=dict(rt.R7_SUN_TIE),
    rej=list(rt.r9_reject(rt.R9_SHARE)),
    s2med=[[sg, tn, m] for sg, tn, m in st.S2_MED],
    dt=[dict(deposit=r["deposit"], hedge=r["hedge"], base=r["base"], lo=r["lo"], hi=r["hi"], lend=r["lend"])
        for r in rt.DT_ROWS],
    r8=dict(lo=rt.R8_LO, hi=rt.R8_HI, base=rt.R8_BASE),
)
# fixed inputs from the mutual-tail and clearing-cost engines (not recomputed by the dashboard)
FIXED = dict(r6_price=rt.R6["ref"]["pi"], r6_access=rt.R6_ACCESS, theta_m=mt.THETA_M,
             r5_sized=rt.VBY["R5 sized"]["base"], r5_sized_lend=rt.VBY["R5 sized"]["lendable"],
             r8_acc_share=rt.R8_ACC_SHARE, r8_fric_save=rt.R8_FRIC_SAVE, weekends=rt.R7_WEEKENDS)

# ---- parameter sets ---------------------------------------------------------------------------------------------
BASE = dict(share=0.20, haircut=0.02, medBal=0.05, sig=0.8,
            r7credit=[0.0, 1 * BP], r7access=[2 * BP, 5 * BP], r7enc=[25 * BP, 100 * BP], r7fric=[3 * BP, 8 * BP],
            r9credit=[0.0, 0.5 * BP], r9access=[2 * BP, 6 * BP], r9loan=[25 * BP, 100 * BP], r9fric=[2 * BP, 6 * BP],
            iorb=0.0390, bill=0.0413, interest=True, s2=0.90, M=20, rho=0.30, cop="gauss")

CASES = [
    ("Base case (the engines' published parameters)", {}),
    ("Share 10%, sigma 0.5, Student-t(5), rho 0.15", dict(share=0.10, sig=0.5, cop="t", rho=0.15)),
    ("Share 35%, median 3%, sigma 1.2, 10 members, rho 0.50", dict(share=0.35, medBal=0.03, sig=1.2, M=10, rho=0.50)),
    ("Joint-account balance earns nothing; bill 4.50%, IORB 4.25%, loan spread 50 to 150",
     dict(interest=False, bill=0.045, iorb=0.0425, r9loan=[50 * BP, 150 * BP])),
    ("S2 bar 0.80, haircut 5%, median 2%, Student-t(5), rho 0.30, 40 members",
     dict(s2=0.80, haircut=0.05, medBal=0.02, cop="t", rho=0.30, M=40)),
    ("R7 terms varied: credit 0.5 to 2, access 1 to 4, encumbrance 30 to 90, frictions 2 to 10",
     dict(r7credit=[0.5 * BP, 2 * BP], r7access=[1 * BP, 4 * BP], r7enc=[30 * BP, 90 * BP], r7fric=[2 * BP, 10 * BP])),
    ("Share 7%, median 1%, Gaussian rho 0 (independent members)", dict(share=0.07, medBal=0.01, rho=0.0)),
    ("Share 50%, sigma 1.0, median 8%, Student-t(5) rho 0, S2 bar 0.75",
     dict(share=0.50, sig=1.0, medBal=0.08, cop="t", rho=0.0, s2=0.75)),
    ("R9 terms varied, IORB 3.00%, bill 3.50%, share 15%",
     dict(r9credit=[0.0, 1 * BP], r9access=[3 * BP, 8 * BP], r9fric=[3 * BP, 8 * BP], iorb=0.030, bill=0.035,
          share=0.15)),
    ("Share 25%, median 4%, sigma 0.65, 30 members, Gaussian rho 0.20",
     dict(share=0.25, medBal=0.04, sig=0.65, M=30, rho=0.20)),
]
TARGETS = [("1pct", 0.01), ("1in520", 1.0 / 520)]


def set_params(p):
    """Set the routes engine's parameters, re-run its R7/R8/R9 and section 5 blocks, then the settlement engine's."""
    rt.R7_SHARE = p["share"]
    rt.R9_SHARE = p["share"]                         # the engine compares R9 with R7 at the same share
    rt.R7_HAIRCUT = p["haircut"]
    rt.R7_CREDIT, rt.R7_ACCESS = tuple(p["r7credit"]), tuple(p["r7access"])
    rt.R7_ENC, rt.R7_FRIC = tuple(p["r7enc"]), tuple(p["r7fric"])
    rt.R7_OUT_MED = p["medBal"] / p["share"]         # median peak debit as a share of the tier
    rt.R7_OUT_SIG = p["sig"]
    rt.R7_OUT_SIG_SET = sorted({0.5, 0.8, 1.2, p["sig"]})
    rt.R9_CREDIT, rt.R9_ACCESS = tuple(p["r9credit"]), tuple(p["r9access"])
    rt.R9_LOAN_SPREAD, rt.R9_FRIC = tuple(p["r9loan"]), tuple(p["r9fric"])
    rt.R9_IORB, rt.R9_BILL, rt.R9_JA_INTEREST = p["iorb"], p["bill"], p["interest"]
    rt.S2_MIN = p["s2"]
    rt.S2_DEFAULT_RUN = False                        # recorded S2 verdicts are for the published parameters only
    exec(RT_SEG_R7, rt.__dict__)
    exec(RT_SEG_5, rt.__dict__)
    exec(ST_SEG_IMP, st.__dict__)
    exec(ST_SEG_LAD, st.__dict__)
    exec(ST_SEG_MED, st.__dict__)
    exec(ST_SEG_CAL, st.__dict__)
    exec(ST_SEG_SUN, st.__dict__)


def sched_out(rec):
    out = dict(hcount={str(k): v for k, v in sorted(rec["hcount"].items())}, binds_p1=rec["binds_p1"])
    for tag in ("max", "year"):
        for sc in ("linear", "sqrt"):
            r = rec[(tag, sc)]
            out[f"{tag}_{sc}"] = dict(back=r["back"], lo=r["lo"], hi=r["hi"], lend=r["lend"], binds=r["binds"])
    return out


def run_case(label, over):
    p = {**BASE, **over}
    t = time.perf_counter()
    set_params(p)
    sig, med_tier, share = p["sig"], rt.R7_OUT_MED, p["share"]
    o = {}
    o["r7"] = dict(lo=rt.R7_LO, hi=rt.R7_HI, base=rt.R7_BASE, lend=rt.R7_LEND, bills=rt.R7_BILLS,
                   terms=[rt.r7_terms(share, e) for e in (0, 1)])
    o["r9"] = dict(lo=rt.R9_LO, hi=rt.R9_HI, base=rt.R9_BASE, lend=rt.R9_LEND,
                   terms=[rt.r9_terms(share, e) for e in (0, 1)])
    o["r9alt"] = dict(lo=rt.R9_ALT_LO, hi=rt.R9_ALT_HI, base=rt.R9_ALT_BASE)
    o["cross"] = rt.R9_BE_SHARE
    o["sun"] = {c: dict(lo=v["lo"], hi=v["hi"], base=v["base"], lend=v["lend"], cross=v["cross"], ex_base=v["ex_base"])
                for c, v in rt.R7_SUN.items()}
    o["tie"] = dict(rt.R7_SUN_TIE)
    o["r8"] = dict(lo=rt.R8_LO, hi=rt.R8_HI, base=rt.R8_BASE, lend=rt.R8_LEND)
    pb = rt.p_bind(sig, med_tier)
    o["bind"] = dict(p=pb, year=1.0 - (1.0 - pb) ** rt.R7_WEEKENDS, n=rt.R7_WEEKENDS * pb)
    o["rej"] = dict(zip(("p", "e"), rt.r9_reject(share, sig)))
    # per-member cap ladder (backing for a target bind frequency), priced with the routes engine's r7_price
    o["ladder"] = []
    for tn, tv in TARGETS:
        mult, bk = st.backing_for(tv, sig)
        o["ladder"].append(dict(target=tn, pd=tv, mult=mult, back=bk, lo=rt.r7_price(bk, 0), hi=rt.r7_price(bk, 1),
                                lend=1.0 - bk))
    # median boundary (Table A4 / A6 at this bar), at this sigma
    key_of = {name: TARGETS[i][0] for i, (name, _) in enumerate(st.TARGETS)}   # engine label -> fixture key
    o["s2med"] = {key_of[tn_full]: m for sg, tn_full, m in st.S2_MED if sg == sig}
    a6 = [r for r in st.S2_MED_BAR if r["sig"] == sig and abs(r["bar"] - p["s2"]) < 1e-12]
    if a6:
        o["a6"] = dict(med=a6[0]["med"], med_g=a6[0]["med_g"], p=a6[0]["p"])
    o["pAtS2cap"] = st.S2_MED_P[sig]
    # same-weekend count distribution of the open debtor cohort, and the joint cap ladder, at this copula and rho
    M, rho, cop = p["M"], p["rho"], p["cop"]
    pmf = st.count_pmf(pb, rho, M, cop)
    q = st.quarter(M)
    o["cohort"] = dict(p1=st.p_atleast(pmf, 1), p3=st.p_atleast(pmf, 3), pq=st.p_atleast(pmf, q), quarter=q,
                       mean=float(sum(k * pmf[k] for k in range(M + 1))))
    o["joint"] = []
    for tn, tv in TARGETS:
        for crit, k in (("one", 1), ("quarter", q)):
            pd = st.solve_pd(tv, k, M, rho, cop)
            mult, bk = st.backing_for(pd, sig)
            o["joint"].append(dict(target=tn, crit=crit, k=k, pd=pd, back=bk, lend=1.0 - bk))
    # closed-window calendar (analysis B)
    o["cal"] = dict(
        routes_binds=st.ROUTES_BINDS, routes_year=st.ROUTES_YEAR,
        p1={f"{y}_{sc}": list(st.P1[(y, sc)]) for y in st.YEARS for sc in st.SCALINGS},
        p2={f"{y}_{sc}": dict(back=v["back"], lo=v["lo"], hi=v["hi"], lend=v["lend"], binds=v["binds"][0])
            for (y, sc), v in st.P2.items()},
        pwin={f"{h}_{sc}": st.p_win(h, share, sc, sig) for h in (2, 26, 50, 74) for sc in st.SCALINGS},
        scen=[sched_out(r) for r in st.SCEN],
        seven=[dict(sc=r["sc"], bills=r["bills"], res=r["res"], lend=r["lend"]) for r in st.SEVEN_RES])
    # Sunday settlement cash: expected secured debit and the daylight overdraft fee
    o["dod"] = dict(sun_debit=st.SUN_DEBIT, hours=st.DOD_H, fee0=st.DOD_COST[0.0], fee50=st.DOD_COST[50 * BP],
                    fee50_1700=st.DOD_COST_1700[50 * BP])
    # by deposit type (results_routes.md Section 10b)
    o["dt"] = [dict(deposit=r["deposit"], clocks=r["clocks"], hedge=r["hedge"], base=r["base"], lo=r["lo"], hi=r["hi"],
                    lend=r["lend"]) for r in rt.DT_ROWS]
    o["dtExtra"] = {c: list(v) for c, v in rt.DT_EXTRA.items()}
    o["dtBoth"] = {c: r["hedge"] for c, r in rt.DT_BOTH.items()}
    print(f"  {label}: {time.perf_counter() - t:.1f} s; R7 {o['r7']['base'] / BP:.2f}, R9 {o['r9']['base'] / BP:.2f}, "
          f"cross {o['cross']:.4f}, bind {pb:.5f}, cohort p1 {o['cohort']['p1']:.4f}")
    return dict(label=label, inputs=p, out=o)


fixtures = dict(source=[ST_PATH.name, RT_PATH.name], base=BASE, fixed=FIXED, published=PUBLISHED,
                cases=[run_case(lbl, ov) for lbl, ov in CASES])
(HERE / "fixtures_settlement.json").write_text(json.dumps(fixtures, indent=1), encoding="utf-8")
print(f"Wrote {HERE / 'fixtures_settlement.json'} ({len(fixtures['cases'])} cases)")
