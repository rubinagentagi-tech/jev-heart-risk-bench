#!/usr/bin/env python3
"""
make_app.py - builds the interactive app: cardio-app.html

One self-contained file, no server, no CDN, no API key. Every profile a visitor can build
was genuinely scored by Jev up front (the 29,952-cell lattice), and every profile is shown
next to what actually happened to the real CDC respondents who matched it.

Three things to do in the app:
  1. build a respondent and ask Jev
  2. guess for yourself and be scored against Jev on real people
  3. look at all 5,000 scored respondents as a bead field
"""
import json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as sc  # noqa: E402
from make_repo import de_dash  # noqa: E402

OUT = os.path.join(HERE, "cardio-app.html")

BAND_ORDER = ["low", "moderate", "elevated", "high"]
DRIVER_ORDER = ["high_blood_pressure", "high_cholesterol", "smoking_history", "diabetes",
                "obesity", "physical_inactivity", "age", "poor_self_rated_health",
                "prior_stroke", "none_clear"]
DRIVER_LABEL = {
    "high_blood_pressure": "high blood pressure", "high_cholesterol": "high cholesterol",
    "smoking_history": "smoking history", "diabetes": "diabetes", "obesity": "obesity (BMI 30+)",
    "physical_inactivity": "no physical activity", "age": "age 65+",
    "poor_self_rated_health": "fair or poor self-rated health", "prior_stroke": "prior stroke",
    "none_clear": "nothing stood out",
}
DIMS = [
    ["18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64",
     "65-69", "70-74", "75-79", "80+"],
    ["male", "female"],
    ["under 25", "25 to 30", "30 or more"],
    [0, 1], [0, 1], [0, 1], [0, 1], [0, 1],
    ["excellent", "good", "fair"],
    [0, 1], [0, 1],
]


def main():
    import time
    t0 = time.time()
    print("loading inputs...", flush=True)
    grid = json.load(open(os.path.join(HERE, "results", "grid", "grid.json")))
    truth = json.load(open(os.path.join(HERE, "grid-truth.json")))
    jev = json.load(open(os.path.join(HERE, "results", "jev", "results.json")))
    base = json.load(open(os.path.join(HERE, "results", "baselines", "baselines.json")))
    llm = json.load(open(os.path.join(HERE, "results", "llm", "results.json")))
    ab = {k: json.load(open(os.path.join(HERE, "results", f"ab-{k}", "results.json")))["scorecard"]
          for k in ("v1", "v2", "v3")}
    sample = pd.read_parquet(os.path.join(HERE, "sample.parquet")).set_index("record_id")
    print(f"  loaded in {time.time()-t0:.1f}s", flush=True)

    # ---- lattice: flat array in itertools.product order, tiny tuples
    cells = sorted(grid["cells"], key=lambda r: r["id"])
    assert len(cells) == 29952, f"expected 29,952 lattice cells, got {len(cells)}"
    flat = [[BAND_ORDER.index(c["band"]) if c.get("band") in BAND_ORDER else -1,
             round(float(c.get("conf") or 0), 2), round(float(c.get("p") or 0), 2),
             int(c.get("driver") if c.get("driver") is not None else 9),
             1 if (c.get("modif") or 0) >= 0.5 else 0,
             1 if (c.get("flag") or 0) >= 0.5 else 0] for c in cells]
    print(f"lattice cells embedded: {len(flat):,}")

    # ---- real respondents for the guessing game, with Jev's call and the truth
    rows = {r["id"]: r for r in jev["rows"]}
    rng = np.random.default_rng(7)
    ids = [r for r in sample.index if r in rows]
    pick = [ids[i] for i in rng.choice(len(ids), size=min(500, len(ids)), replace=False)]
    quiz = []
    for rid in pick:
        s, j = sample.loc[rid], rows[rid]
        quiz.append([s.age_band, s.sex, round(float(s.bmi), 1),
                     "excellent" if s.general_health in ("excellent", "very good") else
                     ("good" if s.general_health == "good" else "fair"),
                     int(s.high_blood_pressure), int(s.high_cholesterol), int(s.diabetes),
                     int(s.smoked_100_cigarettes), int(s.any_physical_activity),
                     int(s.ever_stroke), int(s.difficulty_walking),
                     BAND_ORDER.index(j["band"]), round(float(j["band_confidence"] or 0), 2),
                     int(j["truth"]), DRIVER_ORDER.index(j["top_driver"])
                     if j["top_driver"] in DRIVER_ORDER else 9])
    print(f"quiz respondents: {len(quiz):,}")

    # ---- bead field (the 5,000 scored respondents)
    AGE_START = {"80+": 80}

    def age_start(band):
        if band in AGE_START:
            return AGE_START[band]
        return int(str(band).split("-")[0])

    beads = []
    for rid in sample.index:
        j = rows.get(rid)
        if not j or j.get("band") not in BAND_ORDER:
            continue
        s = sample.loc[rid]
        beads.append([round(float(j["p_positive"] or 0), 3), BAND_ORDER.index(j["band"]),
                      int(j["truth"]), int(j.get("risk_factor_count") or 0),
                      age_start(s.age_band), j["band"],
                      DRIVER_LABEL.get(j.get("top_driver"), "nothing stood out")])
    # position beads by age x a risk-factor composite so the view is readable without PCA
    print(f"beads: {len(beads):,}")

    print(f"configuring... ({time.time()-t0:.1f}s)", flush=True)
    jc_, lc = jev["scorecard"], llm["scorecard"]
    html = TEMPLATE
    repl = {
        "@@DIMS@@": json.dumps(DIMS, separators=(",", ":")),
        "@@GRID@@": json.dumps(flat, separators=(",", ":")),
        "@@TRUTH_EXACT@@": json.dumps(truth["exact"], separators=(",", ":")),
        "@@TRUTH_WIDE@@": json.dumps(truth["wide"], separators=(",", ":")),
        "@@QUIZ@@": json.dumps(quiz, separators=(",", ":")),
        "@@BEADS@@": json.dumps(beads, separators=(",", ":")),
        "@@DRIVER_LABEL@@": json.dumps(DRIVER_LABEL),
        "@@DRIVER_LABELS@@": json.dumps([DRIVER_LABEL[d] for d in DRIVER_ORDER]),
        "@@N_CELLS@@": f"{len(flat):,}",
        "@@N_SCORED@@": f"{jc_['cases']:,}",
        "@@BASE_RATE@@": f"{jc_['base_rate']*100:.1f}",
        "@@COHORT@@": f"{truth['cohort_n']:,}",
        "@@COHORT_RATE@@": f"{truth['cohort_rate']*100:.1f}",
        "@@ACC@@": f"{jc_['accuracy']*100:.1f}",
        "@@AUC@@": f"{jc_['auc']}",
        "@@PREC@@": f"{jc_['precision']*100:.1f}",
        "@@REC@@": f"{jc_['recall']*100:.1f}",
        "@@LIFT@@": f"{jc_['lift']}",
        "@@MAJORITY@@": f"{base['majority']['accuracy']*100:.1f}",
        "@@LR_AUC@@": f"{base['logistic']['auc']}",
        "@@LR_LIFT@@": f"{base['logistic']['lift']}",
        "@@LLM_ACC@@": f"{lc['accuracy']*100:.1f}",
        "@@LLM_AUC@@": f"{lc['auc']}",
        "@@LLM_COST@@": f"{lc['cost_usd']:.2f}",
        "@@JEV_COST@@": f"{jc_['cost_usd']:.2f}",
        "@@JEV_LAT@@": f"{jc_['latency_mean_s']:.2f}",
        "@@LLM_LAT@@": f"{lc['latency_mean_s']:.2f}",
        "@@JEV_P95@@": f"{jc_['prob_p95']}",
        "@@LLM_P95@@": f"{lc['prob_p95']}",
        "@@DRIVER_ACC@@": f"{jc_['driver']['driver_present_accuracy']*100:.1f}",
        "@@AB_V1@@": f"{ab['v1']['accuracy']*100:.1f}",
        "@@AB_V2@@": f"{ab['v2']['accuracy']*100:.1f}",
        "@@AB_V3@@": f"{ab['v3']['accuracy']*100:.1f}",
        "@@AB_V3_AUC@@": f"{ab['v3']['auc']}",
        "@@GRID_COST@@": f"{grid['cost_usd']:.2f}",
        "@@GRID_TOKENS@@": f"{grid['input_tokens']:,}",
        "@@GENERATED@@": pd.Timestamp.now(tz="America/Toronto").strftime("%d %B %Y"),
    }
    for k, v in repl.items():
        html = html.replace(k, v)
    html = de_dash(html)
    open(OUT, "w").write(html)
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ask Jev about a heart-risk profile</title>
<style>
:root{--bg:#070c19;--panel:#0d1428;--panel2:#111a30;--line:#1c2947;--ink:#e8eefc;--mut:#8b9ab8;
--green:#34d399;--amber:#fbbf24;--orange:#fb923c;--red:#f43f5e;--blue:#38bdf8;--violet:#a78bfa}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:32px 22px 70px}
.brand{display:flex;align-items:center;gap:10px;font:600 12px/1 ui-monospace,monospace;
letter-spacing:.16em;color:var(--blue);text-transform:uppercase}
.brand i{width:9px;height:9px;border-radius:50%;background:var(--green);display:inline-block;
box-shadow:0 0 12px var(--green)}
h1{font-size:36px;line-height:1.15;margin:16px 0 10px;letter-spacing:-.02em}
.sub{color:#a9b6d2;font-size:16px;max-width:880px;margin:0 0 8px}
h2{font-size:23px;margin:46px 0 6px}
h2 .n{color:var(--blue);font:600 14px/1 ui-monospace,monospace;margin-right:9px}
p.note{color:#a9b6d2;margin:6px 0 16px;max-width:900px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:14px 0}
.two{display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:18px;align-items:start}
@media(max-width:900px){.two{grid-template-columns:1fr}}
label.row{display:block;margin:0 0 13px}
label.row .lab{display:flex;justify-content:space-between;font-size:12.5px;color:var(--mut);
text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px}
label.row .val{color:#dbe6ff;font-family:ui-monospace,monospace;text-transform:none;letter-spacing:0}
select,input[type=range]{width:100%}
select{background:#101a30;color:var(--ink);border:1px solid var(--line);border-radius:9px;
padding:8px 10px;font:14px inherit}
input[type=range]{accent-color:var(--blue);height:22px}
.btns{display:flex;gap:7px;flex-wrap:wrap}
button,.chip{background:#131c34;color:#cbd5e1;border:1px solid var(--line);border-radius:9px;
padding:8px 13px;font:500 13px/1 inherit;cursor:pointer;transition:.12s}
button:hover,.chip:hover{border-color:#3b5490;color:#fff}
.chip.on{background:#1d2c52;color:#fff;border-color:#4a68a8}
button.primary{background:linear-gradient(180deg,#1f6b4f,#175c43);border-color:#2f9e74;color:#eafff7;
font-weight:600}
button.primary:hover{background:linear-gradient(180deg,#248059,#1a6b4e)}
.toggles{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:12px}
.verdict{border-radius:14px;padding:20px 22px;border:1px solid var(--line);background:var(--panel2)}
.vband{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:var(--mut)}
.vbig{font-size:42px;font-weight:700;letter-spacing:-.02em;line-height:1.1;margin:2px 0 6px}
.vmeta{font-size:13.5px;color:#b6c2da}
.bars{margin:16px 0 6px}
.bar{margin:10px 0}
.bar .t{display:flex;justify-content:space-between;font-size:13px;margin-bottom:5px;color:#cbd5e1}
.bar .track{height:15px;background:#0a1225;border-radius:8px;overflow:hidden;border:1px solid #16203a}
.bar .fill{height:100%;border-radius:8px;transition:width .35s ease}
.gap{border-left:3px solid var(--amber);padding:10px 0 10px 14px;margin:16px 0 4px;
background:#161f38;border-radius:0 10px 10px 0;font-size:14px}
.gap b{color:#fff}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #16203a}
th{color:var(--mut);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.06em}
td.num,th.num{text-align:right;font-family:ui-monospace,monospace}
td.good{color:var(--green);font-weight:600}td.mid{color:var(--amber);font-weight:600}
td.bad{color:var(--red);font-weight:600}
.score{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 0}
.score div{background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:10px 14px;
font-size:13px;color:var(--mut)}
.score div b{display:block;font:700 21px/1.2 ui-monospace,monospace;color:#fff}
.qcard{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.qgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:4px 14px;
font:13px/1.7 ui-monospace,monospace;color:#cbd5e1;margin:10px 0 14px}
.qgrid span b{color:#fff}
.verdictpill{border-radius:10px;padding:12px 16px;margin-top:12px;font-size:15px}
.legend{display:flex;gap:15px;flex-wrap:wrap;margin:12px 2px 0;font-size:13px;color:#b6c2da}
.legend i{width:11px;height:11px;border-radius:50%;display:inline-block;margin-right:6px;vertical-align:-1px}
canvas{display:block;width:100%;height:auto;background:#070c19;border:1px solid var(--line);
border-radius:14px}
.credits{margin-top:48px;padding-top:20px;border-top:1px solid var(--line);color:#93a2c0;font-size:14px}
.credits b{color:#dce6ff;font-size:19px;display:block;margin-bottom:6px}
.credits .fine{font-size:13px;color:#7d8bab;line-height:1.75}
.muted{color:var(--mut)}.warn{color:var(--amber)}
</style></head><body><div class="wrap">

<div class="brand"><i></i>HEART-RISK DECISION BENCH</div>
<h1>Build a person. Ask Jev.</h1>
<p class="sub">Jev is a decision model, not a chatbot: it returns a typed answer with a
probability, a reason code and a confidence, and it cannot write a sentence. Below, assemble a
respondent from real CDC survey answers and Jev will judge them.
Every one of the @@N_CELLS@@ profiles you can reach was genuinely scored by Jev before this page
was built, and each profile is shown next to what actually happened to the real people in the
@@COHORT@@-respondent survey who matched it.</p>
<p class="note">Base rate: <b>@@COHORT_RATE@@%</b> of those respondents had ever been told they
had a heart attack or coronary heart disease. Jev was never trained on any of them.</p>

<h2><span class="n">01</span>Build a respondent</h2>
<div class="two">
  <div class="panel">
    <label class="row"><span class="lab">Age band <span class="val" id="v_age"></span></span>
      <input type="range" id="age" min="0" max="12" value="7" oninput="render()"></label>
    <label class="row"><span class="lab">Sex</span>
      <span class="btns"><button class="chip" id="sex0" onclick="setDim(1,0)">male</button>
      <button class="chip" id="sex1" onclick="setDim(1,1)">female</button></span></label>
    <label class="row"><span class="lab">Body mass index <span class="val" id="v_bmi"></span></span>
      <input type="range" id="bmi" min="0" max="2" value="1" oninput="render()"></label>
    <label class="row"><span class="lab">General health</span>
      <span class="btns"><button class="chip" id="h0" onclick="setDim(8,0)">excellent / very good</button>
      <button class="chip" id="h1" onclick="setDim(8,1)">good</button>
      <button class="chip" id="h2" onclick="setDim(8,2)">fair / poor</button></span></label>
    <div class="toggles" id="toggles"></div>
    <div class="btns">
      <button class="primary" onclick="randomProfile()">Random realistic profile</button>
      <button onclick="resetProfile()">Reset</button>
    </div>
    <p class="muted" style="font-size:12.5px;margin:12px 0 0">Held fixed and shown to Jev:
    cholesterol checked in the last 5 years, eats fruit and vegetables daily, no heavy alcohol,
    has health coverage, no cost barrier to care, high school graduate, income $35-50k.</p>
  </div>

  <div>
    <div class="verdict" id="verdict"></div>
    <div class="score" id="score"></div>
  </div>
</div>

<h2><span class="n">02</span>Guess for yourself, then be scored against Jev</h2>
<p class="note">A random real respondent from the survey. You see exactly what Jev saw. Say
whether they had heart disease, then find out, and whether Jev got it right.</p>
<div class="panel">
  <div class="qcard">
    <div class="muted" style="font-size:12.5px;text-transform:uppercase;letter-spacing:.08em">
      Respondent <span id="qn"></span></div>
    <div class="qgrid" id="qgrid"></div>
    <div class="btns">
      <button class="primary" onclick="guess(true)">I say: had heart disease</button>
      <button class="primary" onclick="guess(false)">I say: did not</button>
      <button onclick="nextQ()">Skip</button>
    </div>
    <div id="qresult"></div>
  </div>
  <div class="score" id="qscore"></div>
</div>

<h2><span class="n">03</span>All @@N_SCORED@@ people at once</h2>
<p class="note">Each bead is one real respondent. Fill is Jev's band; a white centre means they
really did have heart disease. Switch to the truth view and the white centres are where Jev put
its red and orange beads.</p>
<div class="btns" style="margin-bottom:12px">
  <button id="b0" class="chip on" onclick="setView(0)">Jev's band</button>
  <button id="b1" class="chip" onclick="setView(1)">What was true</button>
  <button id="b2" class="chip" onclick="setView(2)">Jev was wrong</button>
</div>
<div id="stage"><canvas id="c" width="2200" height="1150"></canvas><div id="tip"></div></div>
<div class="legend" id="legend"></div>

<h2><span class="n">04</span>What this run measured</h2>
<div class="panel">
  <table>
    <tr><th>arm</th><th>trained on</th><th class="num">accuracy</th><th class="num">AUC</th>
        <th class="num">lift</th><th class="num">cost / 5,000</th><th class="num">per answer</th></tr>
    <tr><td>Always say no</td><td>n/a</td><td class="num mid">@@MAJORITY@@%</td><td class="num">0.500</td>
        <td class="num">n/a</td><td class="num">n/a</td><td class="num">n/a</td></tr>
    <tr><td>Logistic regression</td><td>248,680 labelled respondents</td><td class="num">79.1%</td>
        <td class="num">@@LR_AUC@@</td><td class="num">@@LR_LIFT@@x</td><td class="num">n/a</td>
        <td class="num">n/a</td></tr>
    <tr><td>Chat LLM (deepseek-flash)</td><td>nothing, written question</td>
        <td class="num">@@LLM_ACC@@%</td><td class="num">@@LLM_AUC@@</td><td class="num">1.87x</td>
        <td class="num">$@@LLM_COST@@</td><td class="num">@@LLM_LAT@@s</td></tr>
    <tr><td><b>Jev (jev-1.13.0)</b></td><td><b>nothing, written question</b></td>
        <td class="num good">@@ACC@@%</td><td class="num good">@@AUC@@</td>
        <td class="num good">@@LIFT@@x</td><td class="num good">$@@JEV_COST@@</td>
        <td class="num good">@@JEV_LAT@@s</td></tr>
  </table>
  <p class="muted" style="font-size:13px">Read this table at each model's own threshold and it
  looks like a Jev win. Compare them at <b>matched coverage</b> instead and they are tied: at 5%,
  10%, 15%, 20%, 30%, 40% and 50% of people flagged, their precisions differ by 0.2 to 2 points.
  Inside narrow age bands they score the same AUC to two decimals. The real differences are that
  the chat LLM's numbers are better calibrated (1.36x over-stated against Jev's 3.05x), that the
  extra people it flags are <b>9.0% positive, exactly the base rate</b>, and that Jev is cheaper,
  faster and fully typed. Age band alone scores AUC 0.7215, so both arms are mostly recovering age.
  Full working in <span style="font-family:ui-monospace,monospace">results/arm-comparison.md</span>.</p>
</div>

<div class="panel">
  <h3 style="margin:0 0 6px;font-size:16px">The decision contract matters as much as the model</h3>
  <p class="muted" style="font-size:13px">Same model, same 1,000 respondents, three ways of asking.
  v1 describes four risk bands. v2 rewrites those bands around the observed base rate. v3 throws
  the bands away and asks for the probability directly.</p>
  <table>
    <tr><th>contract</th><th>what it asks for</th><th class="num">accuracy</th><th class="num">AUC</th>
        <th>what actually happens</th></tr>
    <tr><td>v1</td><td>one of four described bands</td><td class="num">@@AB_V1@@%</td>
        <td class="num">0.786</td><td>over-assigns "elevated": flags 30% of people against a 9% rate</td></tr>
    <tr><td>v2</td><td>bands rewritten around the base rate</td><td class="num">@@AB_V2@@%</td>
        <td class="num">0.793</td><td>worse: it flags 40%. It follows the words, not the percentages</td></tr>
    <tr><td>v3</td><td>the probability itself, as a typed judgement</td><td class="num">@@AB_V3@@%</td>
        <td class="num good">@@AB_V3_AUC@@</td><td>ranks best, but every answer lands between 8% and 19%</td></tr>
  </table>
  <p class="muted" style="font-size:13px;margin-top:10px">The reading: the number Jev returns is a
  ranking signal, not a probability you can quote. Its cut-off belongs in your code, where it can
  be tuned and reported. Set at 0.15 on the v3 contract it flags 8.4% of respondents at 40.5%
  precision, a 4.4x lift over the base rate.</p>
</div>

<div class="credits">
  <b>Created by Rubin Varghese</b>
  Built with <b style="display:inline;font-size:14px">Jev</b> (TypeSafe System One,
  <span class="muted">jev-1.13.0</span>) and <span class="muted">deepseek-flash</span> for the
  comparison arm.<br>
  <span class="fine">
  Survey data: Centers for Disease Control and Prevention, Behavioral Risk Factor Surveillance
  System 2015 (cdc.gov/brfss), a US federal government work in the public domain under
  17 U.S.C. &#167; 105. Downloaded raw and derived to @@COHORT@@ complete responses;
  value mappings follow the official BRFSS 2015 Codebook Report.<br>
  Every profile in this page is a synthetic combination of survey answers, and each was scored by
  Jev in a real API call (@@GRID_TOKENS@@ input tokens, $@@GRID_COST@@). The population figures come from
  the real respondents who matched each profile.<br>
  Demonstration on public survey data only. Not a medical device, not clinical advice, and not to
  be used to make decisions about anyone's care. Generated @@GENERATED@@.
  </span>
</div>
</div>

<script>
const DIMS = @@DIMS@@;
const GRID = @@GRID@@;
const TRUTH_EXACT = @@TRUTH_EXACT@@;
const TRUTH_WIDE = @@TRUTH_WIDE@@;
const QUIZ = @@QUIZ@@;
const BEADS = @@BEADS@@;
const DRIVER_LABEL = @@DRIVER_LABELS@@;
const BAND_NAMES = ["low","moderate","elevated","high"];
const BAND_COLORS = {low:"#34d399",moderate:"#fbbf24",elevated:"#fb923c",high:"#f43f5e"};
const TOGGLES = [[3,"High blood pressure"],[4,"High cholesterol"],[5,"Diabetes"],
                 [6,"Smoked 100+ cigarettes"],[7,"Physically active"],
                 [9,"Prior stroke"],[10,"Difficulty walking"]];
let sel = [7,0,1,0,0,0,0,1,1,0,0];
let tally = {n:0, sumAbs:0};

// `sel` holds a LEVEL INDEX for every dimension. For the yes/no dimensions DIMS[d] is
// [0,1], so the index and the value are the same thing, which keeps both the mixed-radix
// cell lookup and the truth keys simple and consistent.
function cellIndex(s){
  let i = 0;
  for(let d=0; d<DIMS.length; d++) i = i*DIMS[d].length + s[d];
  return i;
}
function keyFor(s){ return DIMS.map((dim,d)=>String(dim[s[d]])).join("|"); }
function wideFor(s){ return [DIMS[0][s[0]], DIMS[3][s[3]], DIMS[4][s[4]], DIMS[9][s[9]]].join("|"); }
function pct(v){return (v*100).toFixed(1)+"%";}

function lookup(s){
  const c = GRID[cellIndex(s)];
  let t = TRUTH_EXACT[keyFor(s)], kind="exact";
  if(!t || t[1] < 25){ const w = TRUTH_WIDE[wideFor(s)];
    if(w && (!t || w[1] > t[1])){ t = w; kind = "wide"; } }
  return {cell:c, truth:t, kind:kind};
}

function render(){
  document.getElementById("v_age").textContent = DIMS[0][sel[0]];
  document.getElementById("v_bmi").textContent = DIMS[2][sel[2]];
  document.getElementById("sex0").className = "chip" + (sel[1]===0?" on":"");
  document.getElementById("sex1").className = "chip" + (sel[1]===1?" on":"");
  for(let i=0;i<3;i++) document.getElementById("h"+i).className = "chip" + (sel[8]===i?" on":"");
  const tg = document.getElementById("toggles");
  if(!tg.dataset.built){
    tg.innerHTML = TOGGLES.map(([d,lab])=>
      `<button class="chip" id="tg${d}" onclick="toggleDim(${d})">${lab}</button>`).join("");
    tg.dataset.built = "1";
  }
  TOGGLES.forEach(([d])=> document.getElementById("tg"+d).className =
    "chip" + (sel[d]===1?" on":""));

  const {cell, truth, kind} = lookup(sel);
  if(!cell || cell[0] < 0){ document.getElementById("verdict").innerHTML =
    "<p class='muted'>No lattice answer for this profile.</p>"; return; }
  const band = BAND_NAMES[cell[0]], col = BAND_COLORS[band];
  const p = cell[2], conf = cell[1];
  const drv = DRIVER_LABEL[cell[3]] || "nothing stood out";
  const flagged = cell[0] >= 2;

  let html = `<div class="vband">Jev's verdict</div>
    <div class="vbig" style="color:${col}">${band.toUpperCase()}</div>
    <div class="vmeta">stated probability this person has heart disease
      <b style="color:#fff">${pct(p)}</b> &middot; confidence in the band
      <b style="color:#fff">${pct(conf)}</b><br>
      reason named: <b style="color:#fff">${drv}</b><br>
      modifiable risk factor present: <b style="color:#fff">${cell[4]?"yes":"no"}</b>
      &middot; flagged for clinical follow-up: <b style="color:#fff">${cell[5]?"yes":"no"}</b></div>`;

  if(truth){
    const n = truth[1], rate = truth[0];
    const label = kind === "exact"
      ? `the ${n.toLocaleString()} real survey respondents who matched this profile exactly`
      : `the ${n.toLocaleString()} real respondents who matched on age and the three conditions
         the survey covers thinly at fine grain`;
    html += `<div class="bars">
      <div class="bar"><div class="t"><span>Jev's stated probability</span><span>${pct(p)}</span></div>
        <div class="track"><div class="fill" style="width:${Math.min(100,p*100)}%;
          background:${col}"></div></div></div>
      <div class="bar"><div class="t"><span>What actually happened to them</span>
        <span>${pct(rate)}</span></div>
        <div class="track"><div class="fill" style="width:${Math.min(100,rate*100)}%;
          background:#7dd3fc"></div></div></div></div>
      <p class="muted" style="font-size:13px;margin:2px 0 0">Outcome among ${label}. The survey
      baseline is ${pct(TRUTH_COHORT_RATE)}.</p>`;
    const gap = p - rate;
    const dir = gap > 0.02 ? "over" : (gap < -0.02 ? "under" : "close to");
    html += `<div class="gap">Jev said <b>${pct(p)}</b>, reality was <b>${pct(rate)}</b>
      &mdash; it <b>${dir === "close to" ? "landed on the real rate" : dir+"-stated the risk"}</b>.
      Jev's band here is <b>${band}</b>${flagged ? ", which counts as a positive call"
      : ", which counts as a no call"}.</div>`;
    tally.n++; tally.sumAbs += Math.abs(gap);
    document.getElementById("score").innerHTML =
      `<div>profiles explored<b>${tally.n}</b></div>
       <div>mean gap between Jev's number and reality<b>${(tally.sumAbs/tally.n*100).toFixed(1)} pts</b></div>
       <div>Jev's average direction<b>${gap>0?"over-states":"under-states"}</b></div>`;
  } else {
    html += `<p class="muted" style="font-size:13px">The survey has too few respondents in this
      exact cell to say what really happened.</p>`;
  }
  document.getElementById("verdict").innerHTML = html;
}

function setDim(d,v){ sel[d]=v; render(); }
function toggleDim(d){ sel[d] = sel[d] ? 0 : 1; render(); }
function resetProfile(){ sel = [7,0,1,0,0,0,0,1,1,0,0]; document.getElementById("age").value=7;
  document.getElementById("bmi").value=1; render(); }
function randomProfile(){
  // draw from the real marginal rates rather than uniformly, so profiles look like people
  const r=Math.random;
  sel = [Math.floor(r()*13), r()<0.48?0:1, r()<0.35?0:(r()<0.8?1:2),
         r()<0.37?1:0, r()<0.36?1:0, r()<0.11?1:0, r()<0.43?1:0, r()<0.75?1:0,
         r()<0.2?0:(r()<0.55?1:2), r()<0.04?1:0, r()<0.18?1:0];
  document.getElementById("age").value=sel[0]; document.getElementById("bmi").value=sel[2];
  render();
}

/* ---------- guessing game ---------- */
let qi = 0, mine = [0,0], jevs = [0,0];
function nextQ(){
  qi = Math.floor(Math.random()*QUIZ.length);
  const q = QUIZ[qi];
  document.getElementById("qn").textContent = "#"+(qi+1);
  const yn = v => v ? "yes" : "no";
  document.getElementById("qgrid").innerHTML =
    `<span>age <b>${q[0]}</b></span><span>sex <b>${q[1]}</b></span><span>BMI <b>${q[2]}</b></span>
     <span>general health <b>${q[3]}</b></span>
     <span>high blood pressure <b>${yn(q[4])}</b></span>
     <span>high cholesterol <b>${yn(q[5])}</b></span>
     <span>diabetes <b>${yn(q[6])}</b></span>
     <span>smoked 100+ <b>${yn(q[7])}</b></span>
     <span>physically active <b>${yn(q[8])}</b></span>
     <span>prior stroke <b>${yn(q[9])}</b></span>
     <span>difficulty walking <b>${yn(q[10])}</b></span>`;
  document.getElementById("qresult").innerHTML = "";
}
function guess(says){
  const q = QUIZ[qi];
  const truth = q[13] === 1;
  const jevSays = q[11] >= 2;
  mine[0] += (says===truth)?1:0; mine[1]++;
  jevs[0] += (jevSays===truth)?1:0; jevs[1]++;
  const good = says===truth, jgood = jevSays===truth;
  document.getElementById("qresult").innerHTML =
    `<div class="verdictpill" style="background:${good?"#10281f":"#2a1420"};
      border:1px solid ${good?"#2f9e74":"#7f2440"}">
      You said <b>${says?"had heart disease":"did not"}</b>. The record says
      <b>${truth?"had heart disease":"did not"}</b> &mdash; you were
      <b>${good?"right":"wrong"}</b>.<br>
      Jev said <b>${BAND_NAMES[q[11]].toUpperCase()}</b> at
      ${(q[12]*100).toFixed(0)}% confidence, naming <b>${DRIVER_LABEL[q[14]]}</b>
      &mdash; Jev was <b>${jgood?"right":"wrong"}</b>.
      </div>`;
  document.getElementById("qscore").innerHTML =
    `<div>your accuracy<b>${(mine[0]/mine[1]*100).toFixed(0)}%</b></div>
     <div>Jev's accuracy on your questions<b>${(jevs[0]/jevs[1]*100).toFixed(0)}%</b></div>
     <div>answered<b>${mine[1]}</b></div>`;
  setTimeout(nextQ, 4200);
}

/* ---------- bead field ---------- */
const c = document.getElementById("c"), ctx = c.getContext("2d");
const tip = document.getElementById("tip"), stage = document.getElementById("stage");
const W = c.width, H = c.height, PAD = 70;
let view = 0;
const AGE_MIN = 18, AGE_MAX = 82;
const NROWS = 7;                                  // risk-factor count 0..7
function pos(b){
  const x = PAD + (b[4]-AGE_MIN)/(AGE_MAX-AGE_MIN)*(W-2*PAD);
  const rowH = (H-2*PAD)/NROWS;
  const h = ((b[0]*9973 + b[3]*131) % 1000)/1000 - 0.5;   // stable jitter within the row
  const y = PAD + (NROWS-1-b[3])*rowH + rowH/2 + h*rowH*0.72;
  return [x,y];
}
function colorFor(b){
  if(view===0) return {f:BAND_COLORS[b[5]], a:0.9};
  if(view===1) return {f: b[2]? "#ff4d6d":"#243049", a: b[2]?0.95:0.5};
  const ok = (b[1]>=2)===(b[2]===1);
  return ok ? {f:"#1f2b45", a:0.3} : {f:"#f43f5e", a:0.95};
}
function draw(){
  ctx.clearRect(0,0,W,H); ctx.fillStyle="#070c19"; ctx.fillRect(0,0,W,H);
  const rowH = (H-2*PAD)/NROWS;
  ctx.font = "600 22px ui-monospace, monospace";
  for(let i=0;i<NROWS;i++){
    const y = PAD + i*rowH;
    ctx.strokeStyle = "#141f3a"; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(PAD,y); ctx.lineTo(W-PAD,y); ctx.stroke();
    ctx.fillStyle = "#5d6c8c";
    ctx.fillText(String(NROWS-1-i), 26, y + rowH/2 + 8);
  }
  ctx.save(); ctx.translate(30, H/2); ctx.rotate(-Math.PI/2);
  ctx.fillStyle="#5d6c8c"; ctx.textAlign="center";
  ctx.fillText("number of classic risk factors", 0, -6); ctx.restore();
  for(const x of [20,30,40,50,60,70,80]){
    const px = PAD + (x-AGE_MIN)/(AGE_MAX-AGE_MIN)*(W-2*PAD);
    ctx.strokeStyle="#141f3a"; ctx.lineWidth=2;
    ctx.beginPath(); ctx.moveTo(px,PAD); ctx.lineTo(px,H-PAD+3); ctx.stroke();
    ctx.fillStyle="#5d6c8c"; ctx.textAlign="center";
    ctx.fillText(String(x), px, H-PAD+34);
  }
  ctx.fillStyle="#5d6c8c"; ctx.textAlign="center";
  ctx.fillText("age", W/2, H-14);
  for(const b of BEADS){
    const [x,y]=pos(b), col=colorFor(b), r = 12 + b[3]*0.8;
    ctx.beginPath(); ctx.arc(x,y,r,0,6.2832);
    ctx.globalAlpha = col.a; ctx.fillStyle = col.f; ctx.fill();
    if(view===0 && b[2]===1){ ctx.globalAlpha=1; ctx.beginPath();
      ctx.arc(x,y,r*0.33,0,6.2832); ctx.fillStyle="#fff"; ctx.fill(); }
    if(view===2 && ((b[1]>=2)===(b[2]===1))===false){ ctx.globalAlpha=1; ctx.lineWidth=2.5;
      ctx.strokeStyle="#ffe4e6"; ctx.beginPath(); ctx.arc(x,y,r+4,0,6.2832); ctx.stroke(); }
  }
  ctx.globalAlpha=1;
}
function legend(){
  const L=document.getElementById("legend"); let h="";
  if(view===0){ for(const k of BAND_NAMES) h+=`<span><i style="background:${BAND_COLORS[k]}"></i>Jev said <b style="color:${BAND_COLORS[k]}">${k}</b></span>`;
    h+=`<span><i style="background:#fff"></i>white centre = really had heart disease</span>`; }
  else if(view===1) h+=`<span><i style="background:#ff4d6d"></i>really had heart disease</span><span><i style="background:#243049"></i>did not</span><span class="muted">older people are to the right, more risk factors are higher up</span>`;
  else h+=`<span><i style="background:#f43f5e"></i>Jev got it wrong (ringed)</span><span><i style="background:#1f2b45"></i>right</span>`;
  L.innerHTML=h;
}
function setView(v){ view=v; for(let i=0;i<3;i++) document.getElementById("b"+i).className="chip"+(i===v?" on":""); draw(); legend(); }

c.addEventListener("mousemove", e=>{
  const r=c.getBoundingClientRect();
  const mx=(e.clientX-r.left)*(W/r.width), my=(e.clientY-r.top)*(H/r.height);
  let best=null,bd=1e9;
  for(const b of BEADS){ const [x,y]=pos(b); const d=(x-mx)**2+(y-my)**2; if(d<bd){bd=d;best=b;} }
  if(!best || Math.sqrt(bd)>46){ tip.style.opacity=0; return; }
  const yn=v=>v?"yes":"no";
  const q=QUIZ; // tooltip uses bead fields only
  tip.innerHTML = `<b>${best[5].toUpperCase()}</b> &middot; ${(best[0]*100).toFixed(1)}% stated<br>
    age ${best[4]} &middot; risk factors ${best[3]}<br>reason: ${best[6]}<br>
    <b>reality</b>: ${best[2]?"had heart disease":"did not"}<br>
    <span style="color:${((best[1]>=2)===(best[2]===1))?"#34d399":"#f43f5e"}">
    ${((best[1]>=2)===(best[2]===1))?"agreed with the record":"disagreed with the record"}</span>`;
  tip.style.opacity=1;
  const [sx,sy]=pos(best);
  tip.style.left = Math.min(stage.clientWidth-300, (sx/W)*stage.clientWidth+14)+"px";
  tip.style.top = Math.max(8,(sy/H)*(stage.clientHeight||700)-40)+"px";
});
c.addEventListener("mouseleave", ()=>{ tip.style.opacity=0; });

const TRUTH_COHORT_RATE = @@COHORT_RATE@@/100;
render(); nextQ(); setView(0);
</script></body></html>
"""


if __name__ == "__main__":
    main()
