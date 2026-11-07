// Parity test: the dashboard's JavaScript model against the Python workpaper.
//
// Run from the release root:   node tests/parity.mjs
// Needs tests/fixtures.json, written by:   python3 -I tests/fixtures.py
//
// Loads the <script id="model"> block from docs/index.html, evaluates it, and compares every output
// in fixtures.json. Tolerances: prices within 0.05 bps; probabilities within 2% relative or 1e-6 absolute.
// Also reproduces the headline numbers of Chapter 3 and times one dashboard update per case.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(here, "..", "docs", "index.html"), "utf8");
const m = html.match(/<script id="model">([\s\S]*?)<\/script>/);
if (!m) throw new Error("model script block not found in docs/index.html");
const M = new Function(m[1] + "\nreturn UDModel;")();
const fx = JSON.parse(readFileSync(join(here, "fixtures.json"), "utf8"));

const BP = 1e-4, PRICE_TOL = 0.05 * BP, REL_TOL = 0.02, ABS_TOL = 1e-6;
let pass = 0, fail = 0;
const worst = { price: 0, probRel: 0, probAbs: 0, numeric: 0 };
const failures = [];

function checkPrice(label, js, py) {
  const d = Math.abs(js - py);
  worst.price = Math.max(worst.price, d / BP);
  if (d <= PRICE_TOL) pass++; else { fail++; failures.push(`${label}: js ${js / BP} vs py ${py / BP} bps`); }
}
function checkProb(label, js, py) {
  const d = Math.abs(js - py), rel = py !== 0 ? d / Math.abs(py) : (d === 0 ? 0 : Infinity);
  if (d <= ABS_TOL || rel <= REL_TOL) {
    pass++;
    if (Math.abs(py) > ABS_TOL) worst.probRel = Math.max(worst.probRel, rel);
    else worst.probAbs = Math.max(worst.probAbs, d);
  } else { fail++; failures.push(`${label}: js ${js} vs py ${py} (rel ${rel.toExponential(2)})`); }
}
function checkBE(label, js, py) {
  // Python bisection returns ~0.20 when the price never reaches delta below 20%, and None when it exceeds delta at 0.
  if (py === null) { if (js.none) pass++; else { fail++; failures.push(`${label}: expected none, got ${JSON.stringify(js)}`); } return; }
  if (py > 0.1999) { if (js.above) pass++; else { fail++; failures.push(`${label}: expected above 20%, got ${JSON.stringify(js)}`); } return; }
  if (js.none || js.above) { fail++; failures.push(`${label}: expected ${py}, got ${JSON.stringify(js)}`); return; }
  checkProb(label, js.pd, py);
}

// special functions
for (const [x, v] of fx.numerics.ncdf) {
  const js = M.ncdf(x), rel = v === 0 ? Math.abs(js) : Math.abs(js - v) / v;
  worst.numeric = Math.max(worst.numeric, rel);
  if (rel < 1e-9 || Math.abs(js - v) < 1e-300) pass++; else { fail++; failures.push(`ncdf(${x}): ${js} vs ${v}`); }
}
for (const [p, v] of fx.numerics.inv) {
  const js = M.invNcdf(p), d = Math.abs(js - v);
  worst.numeric = Math.max(worst.numeric, d);
  if (d < 1e-9) pass++; else { fail++; failures.push(`invNcdf(${p}): ${js} vs ${v}`); }
}

function toPar(p) {
  return { pd: p.pd, mu: p.mu, lgd: p.lgd, a: p.a, D: p.D, r: p.r, s_b: p.s_b, f: p.f, k: p.k, N: p.N, rho: p.rho,
           copula: p.copula, nu: p.nu, theta: p.theta, F: p.F, fee: p.fee, s_lock: p.s_lock, s_draw: p.s_draw,
           lag: p.lag, lgdMode: p.lgd_mode, delta: p.delta };
}

const timings = [];
for (const c of fx.cases) {
  const par = toPar(c.inputs), o = c.out, L = c.label;
  M.compute(par);                                   // builds the fixed grids once, as on first page load
  M.clearCache();                                   // but not the per-input nodes: time a cold update
  const t0 = performance.now();
  const r = M.compute(par);
  timings.push([L, performance.now() - t0, par.N, par.copula]);
  for (const k of ["credit", "access", "c_star"]) checkPrice(`${L} single.${k}`, r.single[k], o.single[k]);
  for (const k of ["credit", "access", "lock", "commit", "drawn", "k", "c_star"]) checkPrice(`${L} pool.${k}`, r.pool[k], o.pool[k]);
  for (const cop of ["gauss", "t"]) {
    const js = r.rel[cop], py = o.rel[cop];
    for (const k of ["uncond", "cond", "unpaid", "severity", "loss"]) checkProb(`${L} ${cop}.${k}`, js[k], py[k]);
    checkProb(`${L} ${cop}.p_fail`, js.uncond, py.p_fail);
    fx.curve_caps.forEach((cap, i) => checkProb(`${L} ${cop}.curve@${cap}`, M.relAt(r.dist[cop], cap).cond, py.curve[i]));
  }
  checkPrice(`${L} rule.all_funded`, r.rule.allFunded, o.rule.all_funded);
  o.rule.splits.forEach((s, i) => checkPrice(`${L} rule.split${s.share}`, r.rule.splits[i].c_star, s.c_star));
  checkBE(`${L} be_single`, r.be.single, o.be_single);
  checkBE(`${L} be_pool`, r.be.pool, o.be_pool);
}

// Chapter 3 headline numbers (base case)
const B = M.compute({ ...M.BASE });
const hyb = M.compute({ ...M.BASE, theta: 0.10, F: 0.10 });
const Bt = B.rel.t;
const headline = [
  ["single-name c* 45.7 bps", (B.single.c_star / BP).toFixed(1), "45.7"],
  ["all-funded 20% pool c* 37.7 bps", (B.pool.c_star / BP).toFixed(1), "37.7"],
  ["hybrid 10/10 at 20 bps c* 38.7 bps", (hyb.pool.c_star / BP).toFixed(1), "38.7"],
  ["unconditional failure 0.0097%", (B.rel.gauss.uncond * 100).toFixed(4) + "%", "0.0097%"],
  ["conditional shortfall Gaussian 1.008%", (B.rel.gauss.cond * 100).toFixed(3) + "%", "1.008%"],
  ["conditional shortfall t(5) 27.7%", (Bt.cond * 100).toFixed(1) + "%", "27.7%"],
];
for (const [lbl, got, want] of headline) {
  if (got === want) pass++; else { fail++; failures.push(`headline ${lbl}: got ${got}`); }
}

console.log("Chapter 3 headline numbers (base case):");
for (const [lbl, got] of headline) console.log(`  ${lbl.padEnd(42)} -> ${got}`);
console.log("\nTime per dashboard update (model only, warm grids):");
for (const [l, ms, N, cop] of timings) console.log(`  ${ms.toFixed(0).padStart(5)} ms  N=${String(N).padEnd(3)} ${cop.padEnd(5)} ${l}`);
console.log(`\nWorst deviations: price ${worst.price.toExponential(2)} bps; probability ${(worst.probRel * 100).toExponential(2)}% relative` +
            ` (values > 1e-6), ${worst.probAbs.toExponential(2)} absolute (values <= 1e-6); special functions ${worst.numeric.toExponential(2)}`);
console.log(`\n${pass} checks passed, ${fail} failed (${fx.cases.length} parameter sets from ${fx.source})`);
if (fail) { console.log(failures.slice(0, 40).join("\n")); process.exit(1); }
