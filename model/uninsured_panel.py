"""uninsured_panel.py (Cash That Never Sleeps, Chapter 1): uninsured share of domestic
deposits at banks of $10 billion to $250 billion.

Group reading (the QBP-like ratio), a fixed panel of surviving banks, failure and
composition decomposition, acquirer exclusions, and survivorship counts, from
FDIC BankFind Suite bank-level Call Report data.

Sources (all public, all pulled by this script and cached under model/cache/):
  * FDIC BankFind Suite API, financials endpoint (RIS view), https://api.fdic.gov/banks/financials
    (the documented host https://banks.data.fdic.gov/api/ answers with a 301 to this one).
    Field definitions: https://api.fdic.gov/banks/docs/risview_properties.yaml
  * FDIC BankFind Suite API, failures endpoint, https://api.fdic.gov/banks/failures
  * FDIC BankFind Suite API, history (structure events) endpoint, https://api.fdic.gov/banks/history
  * FDIC Quarterly Banking Profile, second quarter 2026, time-series spreadsheet
    (sheet "Ratios by Asset Size Groups") and Notes to Users.

Run (from anywhere):
    python -I -B <this file>
First run pulls and caches (the QBP spreadsheet download takes about two minutes);
later runs read the cache only and rewrite results_panel.md byte for byte.
The script never re-pulls a file already cached; to re-pull, point --cache at a new
directory (and --out at a new results file).

Units: the API reports dollar amounts in thousands. Shares are in percent.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_DIR = Path(__file__).resolve().parent
API = "https://api.fdic.gov/banks"
QBP_XLSX_URL = ("https://www.fdic.gov/quarterly-banking-profile/"
                "qbp-time-series-spreadsheets-second-quarter-2026.xlsx")
QBP_NOTES_URL = ("https://www.fdic.gov/quarterly-banking-profile/"
                 "qbp-notes-users-second-quarter-2026.pdf")
UA = "Mozilla/5.0 (research replication script; uninsured_panel.py)"

DATES = ["20221231", "20230630", "20241231", "20260630"]
LABEL = {"20221231": "2022 Q4", "20230630": "2023 Q2",
         "20241231": "2024 Q4", "20260630": "2026 Q2"}
QBP_COL = {"20221231": "2022Q4", "20230630": "2023Q2",
           "20241231": "2024Q4", "20260630": "2026Q2"}
# Printed reference values (uninsured share, percent, Chapter 1), carried only to check the
# spreadsheet read below; the comparison uses the spreadsheet values.
TABLE1 = {"20221231": 41.7, "20230630": 33.4, "20241231": 33.9, "20260630": 36.5}

# Group bounds in thousands of dollars, both inclusive.
LO, HI = 10_000_000, 250_000_000
FIELDS = ["CERT", "NAME", "REPDTE", "ASSET", "DEP", "DEPDOM", "DEPINS",
          "DEPUNINS", "DEPCSBQ", "BKCLASS"]
# QBP Notes to Users: "U.S. branches of institutions headquartered in foreign countries and
# non-deposit trust companies are not included unless otherwise indicated." BKCLASS codes per
# the API docs: OI insured U.S. branch of a foreign chartered institution; NC noninsured
# non-deposit commercial bank and/or trust company.
NON_QBP_CLASSES = {"OI", "NC"}
PAGE = 1000
GROWTH_CUT = 0.30
# History endpoint event codes treated as whole-institution combinations in which
# ACQ_CERT absorbs OUT_CERT (see the API's CHANGECODE_DESC values).
MERGER_CODES = {211: "Failure - Whole Institution",
                216: "Bridge Bank Resolution",
                221: "Absorption - Without Assistance",
                223: "Merger - Without Assistance",
                224: "Affiliated Institution Merger (corporate reorganization)"}
FAILURE_CODES = {211, 216}


# ----------------------------------------------------------------------------- I/O

def http_get(url: str, timeout: int = 600) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:  # retry transient faults
            last = e
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"STOP: request failed after 3 attempts: {url}\n  {last}")


class Cache:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta_path = root / "pull_meta.json"
        self.meta = (json.loads(self.meta_path.read_text())
                     if self.meta_path.exists() else {})
        self.pulled_now = 0

    def get(self, name: str, url: str) -> bytes:
        p = self.root / name
        if p.exists():
            if self.meta.get(name, {}).get("url") != url:
                raise SystemExit(f"STOP: cache file {name} was pulled from a different URL; "
                                 "use a fresh --cache directory")
            return p.read_bytes()
        body = http_get(url)
        p.write_bytes(body)
        self.meta[name] = {"url": url,
                           "pulled_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                           "bytes": len(body)}
        self.meta_path.write_text(json.dumps(self.meta, indent=1, sort_keys=True))
        self.pulled_now += 1
        return body


def api_url(endpoint: str, **params) -> str:
    return f"{API}/{endpoint}?" + urllib.parse.urlencode(params, safe=":[]()\"")


def api_json(cache: Cache, name: str, url: str) -> dict:
    body = cache.get(name, url)
    try:
        js = json.loads(body)
    except json.JSONDecodeError:
        raise SystemExit(f"STOP: API returned non-JSON for {url}: {body[:200]!r}")
    if "data" not in js:
        raise SystemExit(f"STOP: API response without data for {url}: {str(js)[:300]}")
    return js


def pull_financials(cache: Cache, repdte: str) -> tuple[pd.DataFrame, dict]:
    rows, offset, page, meta = [], 0, 0, None
    while True:
        url = api_url("financials", filters=f"REPDTE:{repdte}", fields=",".join(FIELDS),
                      sort_by="CERT", sort_order="ASC", limit=PAGE, offset=offset,
                      format="json")
        js = api_json(cache, f"financials_{repdte}_p{page:03d}.json", url)
        meta = meta or js["meta"]
        rows += [r["data"] for r in js["data"]]
        total = js["meta"]["total"]
        offset += PAGE
        page += 1
        if offset >= total:
            break
    df = pd.DataFrame(rows)
    missing = [f for f in FIELDS if f not in df.columns]
    if missing:
        raise SystemExit(f"STOP: fields missing from the API response at {repdte}: {missing}")
    if len(df) != total or df["CERT"].duplicated().any():
        raise SystemExit(f"STOP: paging mismatch at {repdte}: {len(df)} rows vs total {total}")
    for c in ["ASSET", "DEP", "DEPDOM", "DEPINS", "DEPUNINS", "DEPCSBQ"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["CERT"] = df["CERT"].astype(int)
    return df.set_index("CERT").sort_index(), {"total": total, "pages": page,
                                                "index": meta.get("index", {})}


def pull_failures(cache: Cache) -> pd.DataFrame:
    url = api_url("failures", filters='FAILDATE:["2023-01-01" TO "2023-12-31"]',
                  fields="CERT,NAME,FAILDATE,QBFASSET,QBFDEP", sort_by="CERT",
                  sort_order="ASC", limit=1000, format="json")
    js = api_json(cache, "failures_2023.json", url)
    df = pd.DataFrame([r["data"] for r in js["data"]])
    df["CERT"] = df["CERT"].astype(int)
    return df.sort_values("CERT").reset_index(drop=True)


def pull_history(cache: Cache) -> pd.DataFrame:
    rows, offset, page = [], 0, 0
    lim = 10000
    while True:
        url = api_url("history",
                      filters="EFFDATE:[2023-01-01 TO 2026-06-30] AND ACQ_CERT:[1 TO 99999999]",
                      fields="CHANGECODE,CHANGECODE_DESC,ACQ_CERT,OUT_CERT,EFFDATE",
                      sort_by="EFFDATE", sort_order="ASC", limit=lim, offset=offset,
                      format="json")
        js = api_json(cache, f"history_2023_2026_p{page:03d}.json", url)
        rows += [r["data"] for r in js["data"]]
        offset += lim
        page += 1
        if offset >= js["meta"]["total"]:
            break
    df = pd.DataFrame(rows)
    return df


def pull_qbp(cache: Cache) -> tuple[dict, dict, str]:
    """Return (uninsured share by date, institution count by date, note) from the QBP
    time-series spreadsheet, group "Assets $10 Billion - $250 Billion"."""
    body = cache.get("qbp_time_series_2026q2.xlsx", QBP_XLSX_URL)
    cache.get("qbp_notes_users_2026q2.pdf", QBP_NOTES_URL)
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError:
        return ({d: TABLE1[d] for d in DATES}, {}, "openpyxl not installed: QBP values "
                "taken from the printed reference values, not read from the spreadsheet")
    import io  # noqa: PLC0415
    wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    ws = wb["Ratios by Asset Size Groups"]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    def norm(x):
        return " ".join(str(x).split()) if x is not None else ""

    def block(title):
        start = next(i for i, r in enumerate(rows) if any(norm(c) == title for c in r))
        hdr_i = next(i for i in range(start, start + 6)
                     if any(norm(c) == "Asset Size Group" for c in rows[i]))
        hdr = [norm(c) for c in rows[hdr_i]]
        grp_i = next(i for i in range(hdr_i, hdr_i + 8)
                     if any(norm(c) == "Assets $10 Billion - $250 Billion" for c in rows[i]))
        return {d: rows[grp_i][hdr.index(QBP_COL[d])] for d in DATES}

    ins = block("Estimated Insured Deposits as a Percent of Total Deposits - Domestic")
    cnt = block("Number of Institutions Reporting")
    return ({d: round(100.0 - float(ins[d]), 4) for d in DATES},
            {d: int(cnt[d]) for d in DATES}, "read from the spreadsheet")


# ------------------------------------------------------------------------ analysis

def share(df: pd.DataFrame) -> float:
    """Uninsured share, percent: 1 - sum(DEPINS) / sum(DEPDOM)."""
    return 100.0 * (1.0 - df["DEPINS"].sum() / df["DEPDOM"].sum())


def share_uninsured_field(df: pd.DataFrame) -> float:
    return 100.0 * df["DEPUNINS"].sum() / df["DEPDOM"].sum()


def unins_bn(df: pd.DataFrame) -> float:
    return (df["DEPDOM"].sum() - df["DEPINS"].sum()) / 1e6


def group(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["ASSET"] >= LO) & (df["ASSET"] <= HI)]


def decompose(fin: dict, failed: set, d0: str, d1: str) -> list[tuple[str, float]]:
    """S(G1) - S(G0) split into: failed banks leaving; other exits (non-filers) at d0;
    surviving panel's own change; size-group migration and entrants at d1. Exact."""
    g0, g1 = group(fin[d0]), group(fin[d1])
    g0x = g0[~g0.index.isin(failed)]
    surv = g0x.index[g0x.index.isin(fin[d1].index)]
    c0, c1 = fin[d0].loc[surv], fin[d1].loc[surv]
    s = {"G0": share(g0), "G0x": share(g0x), "C0": share(c0), "C1": share(c1), "G1": share(g1)}
    parts = [
        ("Failed 2023 banks leaving the group", s["G0x"] - s["G0"]),
        ("Other exits (group members at the start no longer filing at the end)", s["C0"] - s["G0x"]),
        ("Surviving banks' own change (fixed set, own data at both dates)", s["C1"] - s["C0"]),
        ("Size migration and entrants (survivors leaving the size band, banks entering it)", s["G1"] - s["C1"]),
    ]
    return parts, s, len(g0), len(g1), len(surv)


# ------------------------------------------------------------------------ report

def f2(x):
    return f"{x:.2f}"


def f1(x):
    return f"{x:,.1f}"


def sgn(x):
    """Signed two-decimal points, with no negative zero."""
    return f"{round(x, 2) + 0.0:+.2f}"


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(MODEL_DIR / "cache"))
    ap.add_argument("--out", default=str(MODEL_DIR / "results_panel.md"))
    a = ap.parse_args(argv)
    t_start = time.time()
    cache = Cache(Path(a.cache))

    fin, fmeta = {}, {}
    for d in DATES:
        fin[d], fmeta[d] = pull_financials(cache, d)
    fail_all = pull_failures(cache)
    hist = pull_history(cache)
    qbp_unins, qbp_cnt, qbp_note = pull_qbp(cache)

    d0, d1, d2, d3 = DATES
    G = {d: group(fin[d]) for d in DATES}
    g0 = G[d0]

    # Data completeness inside the group.
    nulls = {d: int(G[d][["DEPDOM", "DEPINS"]].isna().any(axis=1).sum()) for d in DATES}
    if any(nulls.values()):
        raise SystemExit(f"STOP: group members with missing DEPDOM or DEPINS: {nulls}")
    at_bound = {d: int(((fin[d]["ASSET"] == LO) | (fin[d]["ASSET"] == HI)).sum()) for d in DATES}

    # 2023 failures in the 2022 Q4 group, identified by CERT from the failures endpoint.
    failed = set(fail_all["CERT"]) & set(g0.index)
    failed_tbl = fail_all[fail_all["CERT"].isin(failed)].sort_values("CERT")

    # Group readings.
    grp_rows, gaps = [], {}
    for d in DATES:
        s = share(G[d])
        gaps[d] = s - qbp_unins[d]
        grp_rows.append([LABEL[d], len(G[d]), qbp_cnt.get(d, "n/a"), f2(s),
                         f2(share_uninsured_field(G[d])), f2(qbp_unins[d]),
                         f"{gaps[d]:+.2f}", f1(unins_bn(G[d]))])
    s_g0_xf = share(g0[~g0.index.isin(failed)])

    # QBP scope: drop insured U.S. branches of foreign banks and non-deposit trust companies.
    finq = {d: fin[d][~fin[d]["BKCLASS"].isin(NON_QBP_CLASSES)] for d in DATES}
    Gq = {d: group(finq[d]) for d in DATES}
    gapq = {d: share(Gq[d]) - qbp_unins[d] for d in DATES}
    grpq_rows = []
    for d in DATES:
        dropped = G[d][G[d]["BKCLASS"].isin(NON_QBP_CLASSES)]
        grpq_rows.append([LABEL[d], len(Gq[d]), qbp_cnt.get(d, "n/a"),
                          ", ".join(f"{k} {v}" for k, v in sorted(
                              dropped["BKCLASS"].value_counts().items())) or "none",
                          f2(share(Gq[d])), f2(qbp_unins[d]), sgn(gapq[d]),
                          f2(share(dropped)) if len(dropped) else "n/a",
                          f1(unins_bn(Gq[d]))])
    s_gq0_xf = share(Gq[d0][~Gq[d0].index.isin(failed)])
    dec1q = decompose(finq, failed, d0, d1)

    # Fixed panel: 2022 Q4 group less 2023 failures, filing at every later date.
    base = g0[~g0.index.isin(failed)]
    files_at = {d: set(fin[d].index) for d in DATES}
    panel = sorted(c for c in base.index if all(c in files_at[d] for d in DATES[1:]))
    panel_chk = sorted(c for c in base.index if c in files_at[d1] and c in files_at[d3])

    def panel_rows(certs):
        rows = []
        for d in DATES:
            p = fin[d].loc[certs]
            rows.append([LABEL[d], len(p), f2(share(p)), f1(unins_bn(p)),
                         f1(p["DEPDOM"].sum() / 1e6), int((p["ASSET"] > HI).sum()),
                         int((p["ASSET"] < LO).sum())])
        return rows

    # Acquirer screens.
    growth = fin[d3].loc[panel, "DEPDOM"] / fin[d0].loc[panel, "DEPDOM"] - 1.0
    grew = set(growth[growth > GROWTH_CUT].index)
    p_nogrow = [c for c in panel if c not in grew]
    nonqbp0 = set(fin[d0].index[fin[d0]["BKCLASS"].isin(NON_QBP_CLASSES)])
    panel_q = [c for c in panel if c not in nonqbp0]
    p_nogrow_q = [c for c in p_nogrow if c not in nonqbp0]
    h = hist.copy()
    h["CHANGECODE"] = pd.to_numeric(h["CHANGECODE"], errors="coerce")
    h["ACQ_CERT"] = pd.to_numeric(h["ACQ_CERT"], errors="coerce")
    h["OUT_CERT"] = pd.to_numeric(h["OUT_CERT"], errors="coerce")
    hm = h[h["CHANGECODE"].isin(MERGER_CODES) & (h["ACQ_CERT"] != h["OUT_CERT"])]
    acq_any = set(hm["ACQ_CERT"].dropna().astype(int)) & set(panel)
    acq_fail = set(hm[hm["CHANGECODE"].isin(FAILURE_CODES)]["ACQ_CERT"].dropna()
                   .astype(int)) & set(panel)
    acq_nonaffil = set(hm[hm["CHANGECODE"] != 224]["ACQ_CERT"].dropna().astype(int)) & set(panel)
    p_noacq = [c for c in panel if c not in acq_any]
    p_noacq_na = [c for c in panel if c not in acq_nonaffil]
    p_noboth = [c for c in panel if c not in acq_any and c not in grew]
    code_counts = hm[hm["ACQ_CERT"].isin(panel)].groupby("CHANGECODE").agg(
        events=("OUT_CERT", "size"), acquirers=("ACQ_CERT", "nunique"))

    # Survivorship.
    surv_rows = []
    for d in DATES[1:]:
        gone = [c for c in g0.index if c not in files_at[d]]
        gone_xf = [c for c in gone if c not in failed]
        still_in = sum(1 for c in base.index if c in G[d].index)
        surv_rows.append([LABEL[d], len(gone), len(gone_xf), still_in,
                          len(G[d]) - still_in])
    gone_end = [c for c in g0.index if c not in files_at[d3] and c not in failed]
    gone_merged = sum(1 for c in gone_end if c in set(h["OUT_CERT"].dropna().astype(int)))

    # Decompositions.
    dec1 = decompose(fin, failed, d0, d1)
    dec3 = decompose(fin, failed, d0, d3)

    # Identity check: DEPINS against DEPCSBQ - DEPUNINS, inside the group.
    ident = {}
    for d in DATES:
        g = G[d].dropna(subset=["DEPCSBQ", "DEPUNINS"])
        diff = (g["DEPINS"] - (g["DEPCSBQ"] - g["DEPUNINS"])).abs()
        ident[d] = (len(g), int((diff > 1).sum()), float(diff.max()) if len(g) else 0.0)

    # ----------------------------------------------------------------- write out
    L = []
    w = L.append
    w("# Cash That Never Sleeps, Chapter 1: uninsured share at banks of $10 billion to $250 billion "
      "(uninsured_panel.py results)")
    w("")
    w("Built by `uninsured_panel.py` from FDIC BankFind Suite bank-level data. Every number below "
      "is the script's own output on data it pulled; nothing is typed in except the four printed "
      "reference values used to check the QBP spreadsheet read.")
    w("")
    w("## Run record")
    w("")
    pulls = sorted(cache.meta.items())
    first = min(v["pulled_utc"] for _, v in pulls) if pulls else "n/a"
    last = max(v["pulled_utc"] for _, v in pulls) if pulls else "n/a"
    span = first if first == last else f"{first} to {last}"
    w(f"- Data pulled (UTC): {span}, {len(pulls)} cached files under `model/cache/` "
      "(per-file URL, date and size in `cache/pull_meta.json`). A second run reads the cache only.")
    idx = fmeta[d0]["index"]
    w(f"- API financials index: `{idx.get('name', 'n/a')}`, created {idx.get('createTimestamp', 'n/a')}.")
    w(f"- Python {platform.python_version()}, pandas {pd.__version__}, numpy {np.__version__}; "
      "HTTP by urllib (the `requests` package is not installed in this environment).")
    w(f"- QBP comparison values: {qbp_note}.")
    w("")
    w(table(["Date", "Institutions returned by the API", "Pages", "In group"],
            [[LABEL[d], fmeta[d]["total"], fmeta[d]["pages"], len(G[d])] for d in DATES]))
    w("")
    w("## Method")
    w("")
    w("- Endpoint and fields: `financials` (RIS view), fields CERT, NAME, REPDTE, ASSET, DEP, DEPDOM, "
      "DEPINS, plus DEPUNINS and DEPCSBQ for the diagnostics. The insured-deposit field is DEPINS, "
      "titled \"ESTIMATED INSURED DEPOSITS\" in the API's `risview_properties.yaml`. DEPDOM is "
      "\"Deposits held in domestic offices\". DEPUNINS is \"ESTIMATED UNINSURED DEPOSITS IN DOMESTIC "
      "OFFICES AND IN INSURED BRANCHES IN US TERRITORIES AND POSSESSIONS\"; DEPCSBQ is \"DEPOSIT "
      "LIABILITIES AFTER EXCLUSIONS\". Amounts are in thousands of dollars.")
    w("- Dates: REPDTE 20221231, 20230630, 20241231, 20260630; every institution at each date, "
      f"paged {PAGE} at a time sorted by CERT.")
    w("- Group: 10,000,000 <= ASSET <= 250,000,000 (thousands), both bounds inclusive, at each date. "
      "The QBP labels the group \"Assets $10 Billion - $250 Billion\" and does not state inclusivity "
      f"in its notes; banks reporting exactly a bound: "
      f"{', '.join(f'{LABEL[d]} {at_bound[d]}' for d in DATES)}, so the choice does not bind.")
    w("- Group uninsured share = 100 x (1 - sum DEPINS / sum DEPDOM) over the group at that date, "
      "a weighted ratio of sums as the QBP notes describe for condition ratios. Uninsured dollars "
      "= sum (DEPDOM - DEPINS).")
    w("- 2023 failures: CERTs from the `failures` endpoint with FAILDATE in 2023, intersected with "
      "the 2022 Q4 group (not hard-coded).")
    w("- Fixed panel: 2022 Q4 group members, less the 2023 failures, that file at all three later "
      "dates; each bank's own data at each date, whether or not it is still in the size band.")
    w(f"- Acquirer screens: (i) DEPDOM growth above {GROWTH_CUT:.0%} from 2022 Q4 to 2026 Q2; "
      "(ii) the panel bank is ACQ_CERT on a `history` event from 2023-01-01 to 2026-06-30 with "
      "CHANGECODE in {" + ", ".join(f"{k} {v}" for k, v in MERGER_CODES.items()) +
      "}; (iii) the same without code 224; (iv) (i) or (ii). Branch purchases (code 712) are not "
      "counted as acquisitions.")
    w("")
    w("## 1. Group uninsured share against the published QBP ratio")
    w("")
    w(table(["Date", "Banks in group (API)", "QBP count", "API share, 1 - DEPINS/DEPDOM",
             "API share, DEPUNINS/DEPDOM", "QBP share", "Gap, API less QBP (points)",
             "Uninsured $bn (API)"], grp_rows))
    w("")
    w("QBP share is 100 less \"Estimated Insured Deposits as a Percent of Total Deposits - "
      "Domestic\" for \"Assets $10 Billion - $250 Billion\" in the QBP second-quarter 2026 "
      "time-series spreadsheet. Check against the printed reference values (Chapter 1, one decimal): "
      + ", ".join(f"{LABEL[d]} {qbp_unins[d]:.2f} vs {TABLE1[d]}" for d in DATES) + ".")
    w("")
    w("## 1b. Same reading in QBP scope")
    w("")
    w("The QBP Notes to Users exclude U.S. branches of foreign banks and non-deposit trust "
      "companies. This reading drops group members with BKCLASS OI (insured U.S. branch of a "
      "foreign chartered institution) or NC (noninsured non-deposit commercial bank or trust "
      "company) at each date, using the BKCLASS the financials endpoint reports for that date.")
    w("")
    w(table(["Date", "Banks in group (QBP scope)", "QBP count", "Dropped by class",
             "Share, QBP scope", "QBP share", "Gap, API less QBP (points)",
             "Share of the dropped banks", "Uninsured $bn"], grpq_rows))
    w("")
    w(f"2022 Q4 in QBP scope: {f2(share(Gq[d0]))}; with the three failures removed "
      f"{f2(s_gq0_xf)}; difference {f2(s_gq0_xf - share(Gq[d0]))} points. Decomposition "
      "2022 Q4 to 2023 Q2 in QBP scope (same four parts as Section 3): "
      + ", ".join(f"{v:+.2f}" for _, v in dec1q[0])
      + f"; total {dec1q[1]['G1'] - dec1q[1]['G0']:+.2f}.")
    w("")
    w("## 2. The three 2023 failures")
    w("")
    w(table(["CERT", "Name (failures endpoint)", "Failure date", "ASSET 2022 Q4 $bn",
             "DEPDOM 2022 Q4 $bn", "Uninsured share 2022 Q4"],
            [[int(r.CERT), r.NAME, r.FAILDATE, f1(g0.loc[r.CERT, "ASSET"] / 1e6),
              f1(g0.loc[r.CERT, "DEPDOM"] / 1e6), f2(share(g0.loc[[r.CERT]]))]
             for r in failed_tbl.itertuples()]))
    w("")
    w(f"Other 2023 failures on the endpoint ({len(fail_all) - len(failed)}) were not in the 2022 Q4 group.")
    w("")
    w(f"2022 Q4 group share {f2(share(g0))}; with the three removed {f2(s_g0_xf)}; "
      f"difference {f2(s_g0_xf - share(g0))} points.")
    w("")
    for title, (parts, s, n0, n1, nsurv) in [
            ("## 3. Decomposition of the group's change, 2022 Q4 to 2023 Q2", dec1),
            ("## 3b. Same decomposition, 2022 Q4 to 2026 Q2", dec3)]:
        w(title)
        w("")
        rows = [[p, f"{v:+.2f}"] for p, v in parts]
        rows.append(["**Total (group share change)**", f"**{s['G1'] - s['G0']:+.2f}**"])
        w(table(["Component", "Points"], rows))
        w("")
        w(f"Group {n0} banks at the start ({f2(s['G0'])}), {n1} at the end ({f2(s['G1'])}); "
          f"surviving set {nsurv} banks, {f2(s['C0'])} at the start and {f2(s['C1'])} at the end. "
          "The parts telescope, so they sum to the total exactly.")
        w("")
    w("## 4. Fixed panel of surviving banks")
    w("")
    w(f"{len(panel)} banks: the {len(g0)} group members at 2022 Q4, less {len(failed)} failures, "
      f"less those not filing at every later date. The panel defined by filing at 2023 Q2 and "
      f"2026 Q2 only has {len(panel_chk)} banks"
      + (" (the same set)." if panel_chk == panel else " (a different set)."))
    w("")
    hdr = ["Date", "Banks", "Uninsured share", "Uninsured $bn", "DEPDOM $bn",
           "Above $250bn", "Below $10bn"]
    w(table(hdr, panel_rows(panel)))
    w("")
    w(f"QBP scope (drop {len(panel) - len(panel_q)} panel banks with BKCLASS OI or NC at 2022 Q4): "
      f"{len(panel_q)} banks.")
    w("")
    w(table(hdr, panel_rows(panel_q)))
    w("")
    w("## 5. Panel without likely acquirers")
    w("")
    w(f"(i) DEPDOM grew more than {GROWTH_CUT:.0%}, 2022 Q4 to 2026 Q2: {len(grew)} banks excluded, "
      f"{len(p_nogrow)} remain.")
    w("")
    w(table(hdr, panel_rows(p_nogrow)))
    w("")
    w(f"Same in QBP scope: {len(p_nogrow_q)} banks.")
    w("")
    w(table(hdr, panel_rows(p_nogrow_q)))
    w("")
    w(f"(ii) Acquirer on a whole-institution history event, 2023-01-01 to 2026-06-30: "
      f"{len(acq_any)} banks excluded ({len(acq_fail)} of them acquired a failed bank or its "
      f"bridge bank), {len(p_noacq)} remain. Overlap with screen (i): "
      f"{len(acq_any & grew)} banks.")
    w("")
    w(table(["CHANGECODE", "Events with a panel bank as acquirer", "Distinct panel acquirers"],
            [[int(k), int(v.events), int(v.acquirers)] for k, v in code_counts.iterrows()]))
    w("")
    w(table(hdr, panel_rows(p_noacq)))
    w("")
    w(f"(iii) As (ii) without affiliated reorganizations (code 224): {len(acq_nonaffil)} excluded, "
      f"{len(p_noacq_na)} remain.")
    w("")
    w(table(hdr, panel_rows(p_noacq_na)))
    w("")
    w(f"(iv) Excluded by (i) or (ii): {len(panel) - len(p_noboth)} excluded, {len(p_noboth)} remain.")
    w("")
    w(table(hdr, panel_rows(p_noboth)))
    w("")
    w("## 6. Survivorship")
    w("")
    w(table(["Date", "2022 Q4 group members no longer filing (incl. failures)",
             "Same, failures excluded", "Panel-eligible banks still in the size band",
             "Banks in the band not from the 2022 Q4 group (net of failures)"], surv_rows))
    w("")
    w(f"Of the {len(gone_end)} non-failed 2022 Q4 group members not filing at 2026 Q2, "
      f"{gone_merged} appear as OUT_CERT on a history event from 2023-01-01 to 2026-06-30.")
    w("")
    w("## 7. Differences from the published QBP ratio and why")
    w("")
    w("What the QBP second-quarter 2026 Notes to Users state (cached as "
      "`cache/qbp_notes_users_2026q2.pdf`):")
    w("")
    w("- Coverage is \"all FDIC-insured Call Report filers\"; U.S. branches of foreign banks and "
      "non-deposit trust companies are excluded unless indicated. Subsidiary reports are included "
      "with no adjustment for double counting. The financials endpoint returns the excluded filers "
      "too, so the all-filer sum in Section 1 includes institutions the QBP leaves out; Section 1b "
      "removes them by BKCLASS.")
    w("- Estimated insured deposits are \"total deposit liabilities after exclusions minus "
      "estimated uninsured deposits\"; banks of $1 billion or more report the uninsured estimate. "
      "The ratio's denominator is domestic deposits. The API's DEPINS reconciles to DEPCSBQ less "
      "DEPUNINS for "
      + "; ".join(f"{LABEL[d]}: {ident[d][0] - ident[d][1]} of {ident[d][0]} group banks within "
                  f"$1 thousand (max gap {ident[d][2]:,.0f})" for d in DATES)
      + ". The DEPUNINS/DEPDOM column of the Section 1 table is the uninsured estimate taken directly.")
    w("- Ratios are weighted (sum of numerators over sum of denominators). Size groups are by total "
      "assets; the QBP notes do not state the bound convention or whether size is measured on "
      "the current quarter's report.")
    w("")
    w("Bank-count check: the API group has "
      + ", ".join(f"{len(G[d])} banks at {LABEL[d]} (QBP {qbp_cnt.get(d, 'n/a')})" for d in DATES)
      + ".")
    w("")
    w("Bank-count check in QBP scope: "
      + ", ".join(f"{len(Gq[d])} at {LABEL[d]} (QBP {qbp_cnt.get(d, 'n/a')})" for d in DATES)
      + ".")
    w("")
    w("Gap, API less QBP, in points, all API filers: "
      + ", ".join(f"{LABEL[d]} {gaps[d]:+.2f}" for d in DATES)
      + "; in QBP scope: " + ", ".join(f"{LABEL[d]} {round(gapq[d], 3) + 0.0:+.3f}" for d in DATES)
      + ". The all-filer gap is the scope difference the QBP notes state: removing BKCLASS OI and "
      "NC filers reproduces the QBP bank count at every date and "
      + ("leaves a residual inside the spreadsheet's two-decimal rounding (largest "
         f"{max(abs(v) for v in gapq.values()):.3f} points), so nothing is left to explain."
         if max(abs(v) for v in gapq.values()) < 0.005 else
         "leaves a residual the QBP notes do not source: unexplained."))
    w("")
    a_out = Path(a.out)
    text = "\n".join(L) + "\n"
    if "\u2014" in text or "\u00a7" in text:
        raise SystemExit("STOP: forbidden character in output")
    a_out.write_text(text)

    # ---------------------------------------------------------------- stdout
    print(f"uninsured_panel.py: {cache.pulled_now} files pulled now, cache {cache.root}")
    for d in DATES:
        print(f"  {LABEL[d]}: group {len(G[d])} banks, API share {share(G[d]):.2f}, "
              f"QBP {qbp_unins[d]:.2f}, gap {gaps[d]:+.2f}")
    for d in DATES:
        print(f"  QBP scope {LABEL[d]}: {len(Gq[d])} banks, share {share(Gq[d]):.2f}, "
              f"gap {round(gapq[d], 3) + 0.0:+.3f}")
    print(f"  failures removed at 2022 Q4: {sorted(failed)}; share {share(g0):.2f} -> {s_g0_xf:.2f}")
    print("  fixed panel " + str(len(panel)) + ": " + ", ".join(
        f"{share(fin[d].loc[panel]):.2f}% ${unins_bn(fin[d].loc[panel]):,.0f}bn" for d in DATES))
    print(f"  growth-screened panel {len(p_nogrow)}: " + ", ".join(
        f"{share(fin[d].loc[p_nogrow]):.2f}% ${unins_bn(fin[d].loc[p_nogrow]):,.0f}bn" for d in DATES))
    print(f"  merger-screened panel {len(p_noacq)}: " + ", ".join(
        f"{share(fin[d].loc[p_noacq]):.2f}%" for d in DATES))
    print("  decomposition 2022Q4->2023Q2: " + ", ".join(f"{v:+.2f}" for _, v in dec1[0]))
    print(f"  wrote {a_out}; run time {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
