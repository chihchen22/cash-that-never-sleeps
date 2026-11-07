// Parity test: the settlement clock dashboard's JavaScript model against the settlement and routes engines.
//
// Run from the release root:   node tests/parity_settlement.mjs
// Needs tests/fixtures_settlement.json, written by:   python -I -B tests/fixtures_settlement.py
//
// Loads the <script id="model"> block from docs/settlement.html, evaluates it, and compares every output in
// fixtures_settlement.json. Tolerances: prices within 0.05 bps; probabilities, shares and counts within 2% relative
// or 1e-6 absolute. Also checks that the fixtures' base case reproduces the engines' published values, reproduces the
// manual's headline settlement numbers, and times one dashboard update per case.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "..", "docs", "settlement.html"), "utf8");
const m = html.match(/<script id="model">([\s\S]*?)<\/script>/);
if (!m) throw new Error("model script block not found in docs/settlement.html");
const M = new Function(m[1] + "\nreturn SCModel;")();
const fx = JSON.parse(readFileSync(join(here, "fixtures_settlement.json"), "utf8"));

const BP = 1e-4, PRICE_TOL = 0.05 * BP, REL_TOL = 0.02, ABS_TOL = 1e-6;
let pass = 0, fail = 0;
const worst = { price: 0, probRel: 0, probAbs: 0 };
const failures = [];

function checkPrice(label, js, py) {
  const d = Math.abs(js - py);
  if (!(d === d)) { fail++; failures.push(`${label}: js ${js} vs py ${py}`); return; }
  worst.price = Math.max(worst.price, d / BP);
  if (d <= PRICE_TOL) pass++; else { fail++; failures.push(`${label}: js ${js / BP} vs py ${py / BP} bps`); }
}
function checkProb(label, js, py) {
  if (py === null || js === null) {
    if (py === js) pass++; else { fail++; failures.push(`${label}: js ${js} vs py ${py}`); }
    return;
  }
  const d = Math.abs(js - py), rel = py !== 0 ? d / Math.abs(py) : (d === 0 ? 0 : Infinity);
  if (d <= ABS_TOL || rel <= REL_TOL) {
    pass++;
    if (Math.abs(py) > ABS_TOL) worst.probRel = Math.max(worst.probRel, rel);
    else worst.probAbs = Math.max(worst.probAbs, d);
  } else { fail++; failures.push(`${label}: js ${js} vs py ${py} (rel ${rel.toExponential(2)})`); }
}
function checkEq(label, js, py) {
  if (JSON.stringify(js) === JSON.stringify(py)) pass++; else { fail++; failures.push(`${label}: js ${JSON.stringify(js)} vs py ${JSON.stringify(py)}`); }
}
const TERMS = ["credit", "access", "capacity", "frictions"];

function toPar(p) { return { ...M.BASE, ...JSON.parse(JSON.stringify(p)) }; }

function compareCase(L, r, o, par) {
  const R = r.routes, B = r.bind, C = r.cohort, K = r.cal, D = r.dt;
  for (const k of ["lo", "hi", "base"]) {
    checkPrice(`${L} r7.${k}`, R.r7[k], o.r7[k]);
    checkPrice(`${L} r9.${k}`, R.r9[k], o.r9[k]);
    checkPrice(`${L} r9alt.${k}`, R.r9alt[k], o.r9alt[k]);
    checkPrice(`${L} r8.${k}`, R.r8[k], o.r8[k]);
  }
  for (const e of [0, 1]) for (const t of TERMS) {
    checkPrice(`${L} r7.terms[${e}].${t}`, R.r7.terms[e][t], o.r7.terms[e][t]);
    checkPrice(`${L} r9.terms[${e}].${t}`, R.r9.terms[e][t], o.r9.terms[e][t]);
  }
  checkProb(`${L} r7.lend`, R.r7.lend, o.r7.lend);
  checkProb(`${L} r7.bills`, R.r7.bills, o.r7.bills);
  checkProb(`${L} r9.lend`, R.r9.lend, o.r9.lend);
  checkProb(`${L} r8.lend`, R.r8.lend, o.r8.lend);
  checkProb(`${L} cross`, R.cross, o.cross);
  for (const c of ["a", "b1", "b2"]) {
    for (const k of ["lo", "hi", "base", "ex_base"]) checkPrice(`${L} sun.${c}.${k}`, R.sun[c][k], o.sun[c][k]);
    checkProb(`${L} sun.${c}.lend`, R.sun[c].lend, o.sun[c].lend);
    checkProb(`${L} sun.${c}.cross`, R.sun[c].cross, o.sun[c].cross);
  }
  checkProb(`${L} tie.b1`, R.tie.b1, o.tie.b1);
  checkProb(`${L} tie.b2`, R.tie.b2, o.tie.b2);
  // mixed Sunday source: at m = 1 it is the full case; at m = the tie, R7's base equals R9's (the engine's tie definition)
  for (const c of ["b1", "b2"]) {
    const full = M.routes({ ...par, sunCase: c, sunMix: 1 }).chosen;
    checkPrice(`${L} mixed ${c} at m=1`, full.base, o.sun[c].base);
    checkProb(`${L} mixed ${c} lend at m=1`, full.lend, o.sun[c].lend);
    const tie = o.tie[c];
    if (tie > 0 && tie < 1) checkPrice(`${L} mixed ${c} at the tie equals R9`, M.routes({ ...par, sunCase: c, sunMix: tie }).chosen.base, o.r9.base);
  }
  // binding, ladder, median boundary, R9 rejection, overdraft fee
  checkProb(`${L} bind.p`, B.p, o.bind.p);
  checkProb(`${L} bind.year`, B.year, o.bind.year);
  checkProb(`${L} bind.n`, B.n, o.bind.n);
  checkProb(`${L} rej.p`, B.rej.p, o.rej.p);
  checkProb(`${L} rej.e`, B.rej.e, o.rej.e);
  o.ladder.forEach((x, i) => {
    const j = B.ladder[i];
    checkEq(`${L} ladder[${i}].target`, j.key, x.target);
    for (const k of ["mult", "back", "lend"]) checkProb(`${L} ladder.${x.target}.${k}`, j[k], x[k]);
    checkPrice(`${L} ladder.${x.target}.lo`, j.lo, x.lo);
    checkPrice(`${L} ladder.${x.target}.hi`, j.hi, x.hi);
  });
  checkProb(`${L} s2med.1pct`, B.med[0].med, o.s2med["1pct"]);
  checkProb(`${L} s2med.1in520`, B.med[1].med, o.s2med["1in520"]);
  if (o.a6) {
    checkProb(`${L} a6.med`, B.med[0].med, o.a6.med);
    checkProb(`${L} a6.med_g`, B.med[0].medGross, o.a6.med_g);
    checkProb(`${L} a6.p`, B.pAtS2cap, o.a6.p);
  }
  checkProb(`${L} pAtS2cap`, B.pAtS2cap, o.pAtS2cap);
  checkProb(`${L} dod.sun_debit`, B.dod.sun_debit, o.dod.sun_debit);
  checkEq(`${L} dod.hours`, B.dod.hours, o.dod.hours);
  for (const k of ["fee0", "fee50", "fee50_1700"]) checkPrice(`${L} dod.${k}`, B.dod[k], o.dod[k]);
  // same-weekend cohort and joint cap ladder (quadrature on coarser grids than the engine's)
  for (const k of ["p1", "p3", "pq", "mean"]) checkProb(`${L} cohort.${k}`, C[k], o.cohort[k]);
  checkEq(`${L} cohort.quarter`, C.quarter, o.cohort.quarter);
  o.joint.forEach((x, i) => {
    const j = C.joint[i];
    checkEq(`${L} joint[${i}]`, [j.target, j.crit, j.k], [x.target, x.crit, x.k]);
    checkProb(`${L} joint.${x.target}.${x.crit}.pd`, j.pd, x.pd);
    checkProb(`${L} joint.${x.target}.${x.crit}.back`, j.back, x.back);
    checkProb(`${L} joint.${x.target}.${x.crit}.lend`, j.lend, x.lend);
  });
  // closed-window calendar
  checkProb(`${L} cal.routes_binds`, K.routes_binds, o.cal.routes_binds);
  checkProb(`${L} cal.routes_year`, K.routes_year, o.cal.routes_year);
  for (const key of Object.keys(o.cal.p1)) {
    checkProb(`${L} cal.p1.${key}.binds`, K.p1[key][0], o.cal.p1[key][0]);
    checkProb(`${L} cal.p1.${key}.atleast1`, K.p1[key][1], o.cal.p1[key][1]);
    const a = K.p2[key], b = o.cal.p2[key];
    for (const k of ["back", "lend", "binds"]) checkProb(`${L} cal.p2.${key}.${k}`, a[k], b[k]);
    checkPrice(`${L} cal.p2.${key}.lo`, a.lo, b.lo);
    checkPrice(`${L} cal.p2.${key}.hi`, a.hi, b.hi);
  }
  for (const key of Object.keys(o.cal.pwin)) checkProb(`${L} cal.pwin.${key}`, K.pwin[key], o.cal.pwin[key]);
  o.cal.scen.forEach((x, i) => {
    const j = K.scen[i], hc = {};
    Object.keys(j.hcount).forEach((h) => { hc[h] = j.hcount[h]; });
    checkEq(`${L} scen[${i}].hcount`, hc, x.hcount);
    checkProb(`${L} scen[${i}].binds_p1`, j.binds_p1, x.binds_p1);
    for (const tag of ["max", "year"]) for (const sc of ["linear", "sqrt"]) {
      const a = j[`${tag}_${sc}`], b = x[`${tag}_${sc}`];
      for (const k of ["back", "lend", "binds"]) checkProb(`${L} scen[${i}].${tag}_${sc}.${k}`, a[k], b[k]);
      checkPrice(`${L} scen[${i}].${tag}_${sc}.lo`, a.lo, b.lo);
      checkPrice(`${L} scen[${i}].${tag}_${sc}.hi`, a.hi, b.hi);
    }
  });
  o.cal.seven.forEach((x, i) => {
    const j = K.seven[i];
    checkEq(`${L} seven[${i}].sc`, j.sc, x.sc);
    for (const k of ["bills", "res", "lend"]) checkProb(`${L} seven[${i}].${k}`, j[k], x[k]);
  });
  // by deposit type (Section 10b)
  o.dt.forEach((x, i) => {
    const j = D.rows[i];
    checkEq(`${L} dt[${i}].labels`, [j.deposit, j.clocks, j.hedge], [x.deposit, x.clocks, x.hedge]);
    for (const k of ["base", "lo", "hi"]) checkPrice(`${L} dt[${i}].${k}`, j[k], x[k]);
    checkProb(`${L} dt[${i}].lend`, j.lend, x.lend);
  });
  for (const c of ["a", "b1", "b2"]) {
    checkEq(`${L} dtBoth.${c}`, D.both[c].hedge, o.dtBoth[c]);
    checkPrice(`${L} dtExtra.${c}.price`, D.extra[c][0], o.dtExtra[c][0]);
    checkProb(`${L} dtExtra.${c}.lend`, D.extra[c][1], o.dtExtra[c][1]);
  }
}

// the fixtures' base case (the engines' blocks re-run at the published parameters) must reproduce the published values
const P = fx.published, B0 = fx.cases[0].out;
for (const k of ["lo", "hi", "base"]) {
  checkPrice(`published r7.${k}`, B0.r7[k], P.r7[k]); checkPrice(`published r9.${k}`, B0.r9[k], P.r9[k]);
  checkPrice(`published r8.${k}`, B0.r8[k], P.r8[k]);
}
checkProb("published cross", B0.cross, P.cross);
for (const c of ["a", "b1", "b2"]) checkPrice(`published sun.${c}.base`, B0.sun[c].base, P.sun[c].base);
checkProb("published tie.b1", B0.tie.b1, P.tie.b1); checkProb("published tie.b2", B0.tie.b2, P.tie.b2);
checkProb("published rej.p", B0.rej.p, P.rej[0]);
P.dt.forEach((x, i) => checkPrice(`published dt[${i}].base`, B0.dt[i].base, x.base));
// the page's fixed inputs must equal the engines'
checkPrice("fixed r6 price", M.FIXED.r6Price, fx.fixed.r6_price);
checkPrice("fixed r6 access", M.FIXED.r6Access, fx.fixed.r6_access);
checkProb("fixed theta_m", M.FIXED.thetaM, fx.fixed.theta_m);
checkPrice("fixed r5 sized", M.FIXED.r5Sized, fx.fixed.r5_sized);
checkProb("fixed r5 sized lendable", M.FIXED.r5SizedLend, fx.fixed.r5_sized_lend);
checkProb("fixed r8 access share", M.FIXED.r8AccShare, fx.fixed.r8_acc_share);
checkPrice("fixed r8 frictions saved", M.FIXED.r8FricSave, fx.fixed.r8_fric_save);
// the page's defaults must equal the fixtures' base case
for (const k of Object.keys(fx.base)) checkEq(`default ${k}`, M.BASE[k], fx.base[k]);

const timings = [];
for (const c of fx.cases) {
  const par = toPar(c.inputs);
  M.compute(par);                                   // warm the grids and the joint-ladder cache, as on first page load
  const t0 = performance.now();
  const r = M.compute(par);
  timings.push([c.label, performance.now() - t0]);
  compareCase(c.label, r, c.out, par);
}

// headline settlement numbers of the manual (base case)
const H = M.compute({ ...M.BASE });
const pct = (x, d) => (x * 100).toFixed(d) + "%";
const headline = [
  ["R7 facility, base price 22.00 bps", (H.routes.r7.base / BP).toFixed(2), "22.00"],
  ["R9 joint account, base price 25.35 bps", (H.routes.r9.base / BP).toFixed(2), "25.35"],
  ["R7 lendable share 0.80", H.routes.r7.lend.toFixed(2), "0.80"],
  ["R7 vs R9 crossover share 5.4%", pct(H.routes.cross, 1), "5.4%"],
  ["Sunday cash (b1) 34.50 bps", (H.routes.sun.b1.base / BP).toFixed(2), "34.50"],
  ["Sunday cash (b2) 39.10 bps", (H.routes.sun.b2.base / BP).toFixed(2), "39.10"],
  ["tie, new reserves (b2) 19.6%", pct(H.routes.tie.b2, 1), "19.6%"],
  ["tie, bought securities (b1) 26.8%", pct(H.routes.tie.b1, 1), "26.8%"],
  ["median boundary at sigma 0.8, 1% bind: 1.56%", pct(H.bind.med[0].med, 2), "1.56%"],
  ["R9 rejected in 4.156% of weekends", pct(H.bind.rej.p, 3), "4.156%"],
  ["R8 one ledger 41.84 bps", (H.dt.rows[7].base / BP).toFixed(2), "41.84"],
  ["R6 + R9 46.38 bps", (H.dt.rows[8].base / BP).toFixed(2), "46.38"],
  ["cap binds per weekend 4.156%", pct(H.bind.p, 3), "4.156%"],
  ["backing for a 1% per-member bind 32.2%", pct(H.bind.ladder[0].back, 1), "32.2%"],
  ["22x6 longest-window backing 10.4%, lendable 0.896", pct(H.cal.scen[1].max_linear.back, 1) + ", " + H.cal.scen[1].max_linear.lend.toFixed(3), "10.4%, 0.896"],
  ["P2 backing today 29.6%", pct(H.cal.p2["2026_linear"].back, 1), "29.6%"],
  ["calendar 2026 P1 expected binds 2.64", H.cal.p1["2026_linear"][0].toFixed(2), "2.64"],
  ["at least a quarter of 20, Gaussian rho 0.30: 3.36%", pct(H.cohort.pq, 2), "3.36%"],
];
for (const [lbl, got, want] of headline) {
  if (got === want) pass++; else { fail++; failures.push(`headline ${lbl}: got ${got}`); }
}

console.log("Chapter 6 headline settlement numbers (base case):");
for (const [lbl, got] of headline) console.log(`  ${lbl.padEnd(52)} -> ${got}`);
console.log("\nTime per dashboard update (model only, warm grids):");
for (const [l, ms] of timings) console.log(`  ${ms.toFixed(0).padStart(5)} ms  ${l}`);
console.log(`\nWorst deviations: price ${worst.price.toExponential(2)} bps; probability ${(worst.probRel * 100).toExponential(2)}% relative` +
            ` (values > 1e-6), ${worst.probAbs.toExponential(2)} absolute (values <= 1e-6)`);
console.log(`\n${pass} checks passed, ${fail} failed (${fx.cases.length} parameter sets from ${fx.source.join(" and ")})`);
if (fail) { console.log(failures.slice(0, 60).join("\n")); process.exit(1); }
