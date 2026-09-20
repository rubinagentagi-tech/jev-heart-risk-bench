#!/usr/bin/env python3
"""
run_jev_v4.py - was this the wrong use case, or the wrong shape of question?

Hypothesis from the rigour review: Jev failed here because the task asked it to ESTIMATE a
calibrated probability of a rare event, which is an estimation task. Every previous Jev
success in this repo's history has been a SELECTION task - pick one option out of a defined
list. If that diagnosis is right, then giving Jev the number (from a trained model) and
asking it instead to ROUTE and EXPLAIN should play to its strengths, and should be
measurable against the same recorded outcome.

Contract v4:
  state  = the 21 survey answers PLUS the trained model's probability as a stated fact
  Q1 explain_factor : choice, which recorded factor drives that score
  Q2 action_tier     : choice, no_action / lifestyle / clinician_review / urgent
  Q3 modifiable      : noul
  Q4 data_consistent : noul

Scored against the recorded outcome: the tiers must separate risk, in order, for the
routing to be worth anything.

    python run_jev_v4.py
"""
import json, os, sys, threading, time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
import jev_client as jc  # noqa: E402
import score as sc       # noqa: E402
from pack_builder import questions  # noqa: E402

TIERS = ["no_action", "lifestyle", "clinician_review", "urgent"]
REGISTRY, LOCK = [], threading.Lock()


def build_questions(driver_criteria):
    return {
        "explain_factor": {
            "type": "choice",
            "instructions": (
                "A statistical model has already scored this respondent's probability of having "
                "been told they had a heart attack or coronary heart disease. Which single recorded "
                "factor best explains THAT SCORE? Choose only a factor recorded as present."),
            "criteria": driver_criteria,
        },
        "action_tier": {
            "type": "choice",
            "instructions": (
                "Given the recorded answers and the model's score, which single follow-up tier is "
                "right for this respondent? Choose the action the recorded evidence supports, not "
                "the most cautious one."),
            "criteria": {
                "no_action": "Nothing in the record calls for follow-up. No modifiable factor is "
                             "present and the score is unremarkable.",
                "lifestyle": "A modifiable factor is present but the score is not high and there is "
                             "no diagnosed cardiovascular disease. Lifestyle change is the right "
                             "next step, not a referral.",
                "clinician_review": "The record shows enough to warrant a clinician reviewing the "
                                    "risk: a diagnosed condition such as diabetes, or several "
                                    "modifiable factors together, or a high score.",
                "urgent": "The record shows a diagnosed cardiovascular event or condition that "
                          "should already be under clinical care, or the combination of findings "
                          "is severe.",
            },
        },
        "modifiable_risk_present": {
            "type": "noul",
            "instructions": (
                "Is at least one modifiable risk factor present that a lifestyle or treatment "
                "change could address? Count high blood pressure, high cholesterol, diabetes, "
                "smoking history, obesity (body mass index 30 or more), physical inactivity and "
                "heavy alcohol use."),
        },
    }


def worker(cases, out, key, model, qs):
    local = threading.local()
    for c in cases:
        if not hasattr(local, "client"):
            local.client = jc.JevClient(key, model=model)
            with LOCK:
                REGISTRY.append(local.client)
        r = local.client.ask(c["state_block"], qs)
        if not r.get("ok"):
            out.append({"id": c["id"], "error": r.get("error")})
            continue
        a = r["answers"]
        out.append({
            "id": c["id"], "truth": c["truth"], "lr_p": c["lr_p"],
            "driver": (a.get("explain_factor") or {}).get("choice"),
            "driver_conf": (a.get("explain_factor") or {}).get("confidence"),
            "tier": (a.get("action_tier") or {}).get("choice"),
            "tier_conf": (a.get("action_tier") or {}).get("confidence"),
            "modifiable": (a.get("modifiable_risk_present") or {}).get("noul"),
            "driver_truth": c["driver_truth"],
            "risk_factor_count": c["risk_factor_count"],
            "latency_s": r["latency_s"], "input_tokens": r["input_tokens"],
        })


def main():
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        p = os.path.expanduser("~/.typesafe_key")
        key = open(p).read().strip() if os.path.exists(p) else None
    if not key:
        sys.exit("set TYPESAFE_API_KEY")
    cases_in = [json.loads(l) for l in open(os.path.join(HERE, "cases.jsonl")) if l.strip()]
    sample = pd.read_parquet(os.path.join(HERE, "sample.parquet")).set_index("record_id")
    asm = sample.loc[[c["id"] for c in cases_in]]

    # ---- refit the trained model to get a probability per respondent
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    NUM = ["bmi", "poor_physical_health_days", "poor_mental_health_days"]
    BIN = ["high_blood_pressure", "high_cholesterol", "cholesterol_checked", "diabetes",
           "ever_stroke", "smoked_100_cigarettes", "any_physical_activity", "fruit_daily",
           "vegetables_daily", "heavy_alcohol", "has_health_coverage",
           "no_doctor_due_to_cost", "difficulty_walking"]
    CAT = ["age_band", "sex", "general_health", "education", "income"]
    full = pd.read_parquet(os.path.join(HERE, "cohort_clean.parquet"))
    tr = full[~full.record_id.isin(set(asm.index))].reset_index(drop=True)
    pre = ColumnTransformer([("n", StandardScaler(), NUM), ("b", "passthrough", BIN),
                             ("c", OneHotEncoder(handle_unknown="ignore"), CAT)])
    clf = Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=2000))])
    clf.fit(tr[NUM + BIN + CAT], tr.heart_disease)
    probs = clf.predict_proba(asm[NUM + BIN + CAT])[:, 1]
    print(f"refit trained model on {len(tr):,} labelled rows; "
          f"mean score on the 5,000 = {probs.mean():.4f} vs actual {asm.heart_disease.mean():.4f}")

    # ---- build v4 cases: the trained score is handed to Jev as a stated fact
    qs = build_questions(questions()["top_driver"]["criteria"])
    cases = []
    for c, p in zip(cases_in, probs):
        cases.append({
            "id": c["id"], "truth": c["expected"]["heart_disease"], "lr_p": round(float(p), 4),
            "driver_truth": c["expected"]["driver_truth"],
            "risk_factor_count": c["expected"]["risk_factor_count"],
            "state_block": c["state_block"].rstrip() +
                f"\n\nA statistical model trained on 250,000 labelled survey respondents scores "
                f"this person at {p*100:.1f} percent probability of having been told they had a "
                f"heart attack or coronary heart disease.\n",
        })
    outdir = os.path.join(HERE, "results", "v4-router")
    os.makedirs(outdir, exist_ok=True)

    workers = 10
    chunks = [cases[i::workers] for i in range(workers)]
    rows, t0 = [], time.time()
    ts = [threading.Thread(target=worker, args=(ch, rows, key, jc.DEFAULT_MODEL, qs))
          for ch in chunks if ch]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    wall = time.time() - t0
    good = [r for r in rows if "error" not in r]
    tin = sum(c.tokens_in for c in REGISTRY)
    cost = round(tin / 1e6 * 0.042, 5)
    print(f"{len(good):,} answered, {len(rows)-len(good)} errors, {wall:.0f}s, ${cost:.4f}")

    # ---- score: do the tiers separate risk, in order?
    y = np.array([r["truth"] for r in good], dtype=float)
    base = y.mean()
    print()
    print("=" * 72)
    print("Does Jev's ROUTING separate risk? (the test that matters)")
    print("=" * 72)
    print(f"  base rate {base:.4f}")
    tier_idx = {t: i for i, t in enumerate(TIERS)}
    print(f"  {'tier':>17} {'n':>6} {'share':>7} {'actually positive':>18} {'vs base':>8}")
    tiers_used = []
    for t in TIERS:
        m = np.array([r["tier"] == t for r in good])
        if m.sum():
            tiers_used.append((t, m))
            print(f"  {t:>17} {m.sum():>6,} {m.mean():>7.1%} {y[m].mean():>18.1%} "
                  f"{y[m].mean()/base:>7.2f}x")
    rank = np.array([tier_idx.get(r["tier"], -1) for r in good], dtype=float)
    ok = rank >= 0
    print(f"  AUC of the tier as an ordinal score: {sc.auc(y[ok].tolist(), rank[ok].tolist()):.4f}")
    print(f"  (Jev's own band earlier scored {json.load(open(os.path.join(HERE,'results','jev','results.json')))['scorecard']['auc']:.4f},")
    print(f"   the trained model it was handed scored {sc.auc(y.tolist(), [r['lr_p'] for r in good]):.4f})")

    print()
    print("=" * 72)
    print("Did the explanation stay honest?")
    print("=" * 72)
    named = [r for r in good if r["driver"] and r["driver"] != "none_clear"]
    valid = [r for r in named if (r["driver_truth"] or {}).get(r["driver"]) is True]
    print(f"  named a factor: {len(named):,} of {len(good):,} ({len(named)/len(good):.1%})")
    print(f"  the named factor is actually present: {len(valid)/max(1,len(named)):.1%}")
    from collections import Counter
    print("  tier distribution:", dict(Counter(r["tier"] for r in good).most_common()))
    print(f"  mean tier confidence: {np.mean([r['tier_conf'] or 0 for r in good]):.3f}")
    print(f"  latency {np.mean([r['latency_s'] for r in good]):.3f}s   cost ${cost:.4f} "
          f"(${cost/len(good)*1000:.4f} per 1,000)")

    json.dump({"rows": good, "cost_usd": cost, "wall_s": round(wall, 1), "tiers": TIERS},
              open(os.path.join(outdir, "results.json"), "w"), indent=1)
    print(f"\nwrote results/v4-router/results.json")


if __name__ == "__main__":
    main()
