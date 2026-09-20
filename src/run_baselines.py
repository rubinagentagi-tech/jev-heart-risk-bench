#!/usr/bin/env python3
"""
run_baselines.py - the two things any honest benchmark needs beside the model.

  majority   : always say "no heart disease" (9% base rate makes this 91% accurate)
  rule       : the heuristic a nurse or an analyst would write down -- flag anyone
               with 2 or more of the classic risk factors
  logistic   : trained on the 248,680 CDC respondents OUTSIDE the 5,000 test rows

The fairness note that matters: logistic regression is trained on a quarter of a
million labelled examples. Jev never sees one label; it gets a written question and
the survey answers. Both are scored by the same score.py.

    python run_baselines.py --test sample.parquet --train cohort_clean.parquet
"""
import argparse, json, os, sys, time
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as sc  # noqa: E402

NUMERIC = ["bmi", "poor_physical_health_days", "poor_mental_health_days"]
BINARY = ["high_blood_pressure", "high_cholesterol", "cholesterol_checked", "diabetes",
          "ever_stroke", "smoked_100_cigarettes", "any_physical_activity", "fruit_daily",
          "vegetables_daily", "heavy_alcohol", "has_health_coverage",
          "no_doctor_due_to_cost", "difficulty_walking"]
CATEG = ["age_band", "sex", "general_health", "education", "income"]


def risk_factor_count(df):
    """The classic modifiable factors, computed in Python - never asked of a model."""
    return (
        (df.high_blood_pressure == 1).astype(int)
        + (df.high_cholesterol == 1).astype(int)
        + (df.diabetes == 1).astype(int)
        + (df.smoked_100_cigarettes == 1).astype(int)
        + (df.bmi >= 30).astype(int)
        + (df.any_physical_activity == 0).astype(int)
        + (df.heavy_alcohol == 1).astype(int)
    )


def band_from_prob(p):
    if p < 0.05: return "low"
    if p < 0.12: return "moderate"
    if p < 0.25: return "elevated"
    return "high"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default=os.path.join(HERE, "sample.parquet"))
    ap.add_argument("--train", default=os.path.join(HERE, "cohort_clean.parquet"))
    ap.add_argument("--out", default=os.path.join(HERE, "results", "baselines"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    test = pd.read_parquet(a.test)
    full = pd.read_parquet(a.train)
    train = full[~full.record_id.isin(set(test.record_id))].reset_index(drop=True)
    print(f"test {len(test):,} rows ({test.heart_disease.mean():.4f} positive) · "
          f"train {len(train):,} rows ({train.heart_disease.mean():.4f} positive)")

    arms = {}

    # ---------------- majority
    rows = [{"id": r.record_id, "truth": int(r.heart_disease), "band": "low",
             "band_confidence": None, "p_positive": 0.0 if r.heart_disease == 0 else 1.0}
            for r in test.itertuples()]
    for r in rows:
        r["p_positive"] = float(test.heart_disease.mean())
    arms["majority"] = sc.scorecard(
        rows, "Majority class (always predict 'no heart disease')",
        {"note": "predicts the base rate for every respondent"})

    # ---------------- hand-written rule
    cnt = risk_factor_count(test)
    rows = [{"id": r.record_id, "truth": int(r.heart_disease),
             "band": "elevated" if c >= 2 else "low",            # the rule as written
             "band_confidence": 0.5,
             "p_positive": min(c / 7.0, 0.95),                   # monotone score, for AUC
             "risk_factor_count": int(c)}
            for r, c in zip(test.itertuples(), cnt)]
    arms["rule"] = sc.scorecard(
        rows, "Hand-written rule (flag 2 or more classic risk factors)",
        {"note": "a human heuristic, no model, no training"})

    # ---------------- logistic regression
    t0 = time.time()
    pre = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC),
        ("bin", "passthrough", BINARY),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEG),
    ])
    clf = Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=2000, solver="lbfgs"))])
    clf.fit(train[NUMERIC + BINARY + CATEG], train.heart_disease)
    train_s = time.time() - t0
    probs = clf.predict_proba(test[NUMERIC + BINARY + CATEG])[:, 1]
    rows = [{"id": r.record_id, "truth": int(r.heart_disease),
             "band": band_from_prob(float(p)), "band_confidence": float(max(p, 1 - p)),
             "p_positive": float(p)} for r, p in zip(test.itertuples(), probs)]
    arms["logistic"] = sc.scorecard(
        rows, "Logistic regression (trained on 248,680 labelled CDC respondents)",
        {"note": f"fit on {len(train):,} labelled rows in {train_s:.1f}s - "
                 f"supervised learning, which Jev does not do"})

    json.dump({k: v for k, v in arms.items()},
              open(os.path.join(a.out, "baselines.json"), "w"), indent=1)
    md = ["# Baselines", ""]
    for k in ("majority", "rule", "logistic"):
        md.append(sc.report_md(arms[k]))
        md.append("\n---\n")
    open(os.path.join(a.out, "report.md"), "w").write("\n".join(md))
    for k, v in arms.items():
        print(f"{k:9s} acc {v['accuracy']:.3f}  AUC {v['auc']}  prec {v['precision']:.3f} "
              f"rec {v['recall']:.3f}  lift {v['lift']}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
