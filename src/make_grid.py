#!/usr/bin/env python3
"""
make_grid.py - build the lattice that powers the interactive app.

The app lets a visitor assemble a respondent from the same survey answers Jev is given,
then shows Jev's real answer beside what actually happened to the real CDC respondents
who matched that profile. For that to work with no API key in the browser, every
reachable profile has to be sent to Jev once, up front.

The lattice is therefore a full factorial over the answers the visitor can change - not a
sample - so every slider position maps to a cell that was genuinely scored:

    age band (13) x sex (2) x BMI (3) x high blood pressure (2) x high cholesterol (2)
    x diabetes (2) x smoking (2) x physical activity (2) x general health (3)
    x prior stroke (2) x difficulty walking (2)  = 14,976 cells

The remaining survey answers are held at neutral values and the app says so.

Outputs
  grid-cases.jsonl   one synthetic profile per cell, ready for run_jev.py
  grid-truth.json    what actually happened to the real CDC respondents in each cell,
                     plus a wider fallback match for cells the survey covers thinly
"""
import argparse, itertools, json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

AGE_BANDS = ["18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59",
             "60-64", "65-69", "70-74", "75-79", "80+"]
BMI_LEVELS = [("under 25", 23.0), ("25 to 30", 27.5), ("30 or more", 34.0)]
HEALTH_LEVELS = ["excellent", "good", "fair"]

FIXED = {
    "cholesterol_checked": 1.0, "fruit_daily": 1.0, "vegetables_daily": 1.0,
    "heavy_alcohol": 0.0, "has_health_coverage": 1.0, "no_doctor_due_to_cost": 0.0,
}
FIXED_TEXT = {"Education": "grade 12 or GED (high school graduate)",
              "Annual household income": "$35,000-$50,000"}


def state_text(age_band, sex, bmi, bp, chol, diab, smoke, active, health, stroke, walk):
    yn = lambda v: "yes" if v == 1 else "no"
    return (
        f"US adult health survey respondent.\n"
        f"Age band: {age_band}\n"
        f"Sex: {sex}\n"
        f"Body mass index: {bmi:.1f}\n"
        f"Self-rated general health: {health}\n"
        f"Days of poor physical health in the past 30 days: "
        f"{0 if health == 'excellent' else (3 if health == 'good' else 20)}\n"
        f"Days of poor mental health in the past 30 days: "
        f"{0 if health == 'excellent' else (3 if health == 'good' else 12)}\n"
        f"Told by a doctor they have high blood pressure: {yn(bp)}\n"
        f"Told by a doctor their blood cholesterol is high: {yn(chol)}\n"
        f"Blood cholesterol checked in the last 5 years: yes\n"
        f"Ever told they have diabetes: {yn(diab)}\n"
        f"Ever told they had a stroke: {yn(stroke)}\n"
        f"Smoked at least 100 cigarettes in their life: {yn(smoke)}\n"
        f"Any physical activity or exercise in the past month: {yn(active)}\n"
        f"Eats fruit at least once a day: yes\n"
        f"Eats vegetables at least once a day: yes\n"
        f"Heavy alcohol use: no\n"
        f"Has any health care coverage: yes\n"
        f"Needed a doctor in the past 12 months but could not afford it: no\n"
        f"Serious difficulty walking or climbing stairs: {yn(walk)}\n"
        f"Education: {FIXED_TEXT['Education']}\n"
        f"Annual household income: {FIXED_TEXT['Annual household income']}\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "grid-cases.jsonl"))
    ap.add_argument("--truth", default=os.path.join(HERE, "grid-truth.json"))
    ap.add_argument("--cohort", default=os.path.join(HERE, "cohort_clean.parquet"))
    a = ap.parse_args()

    import sys
    sys.path.insert(0, HERE)
    from pack_builder import questions
    qs = questions()

    cells = []
    for (age, sex, (bmi_lab, bmi), bp, chol, diab, smoke, active, health, stroke, walk) in itertools.product(
            AGE_BANDS, ["male", "female"], BMI_LEVELS, [0, 1], [0, 1], [0, 1], [0, 1], [0, 1],
            HEALTH_LEVELS, [0, 1], [0, 1]):
        cells.append({"age": age, "sex": sex, "bmi": bmi, "bmi_lab": bmi_lab, "bp": bp,
                      "chol": chol, "diab": diab, "smoke": smoke, "active": active,
                      "health": health, "stroke": stroke, "walk": walk})
    print(f"lattice cells: {len(cells):,}")

    with open(a.out, "w") as f:
        for i, c in enumerate(cells):
            f.write(json.dumps({
                "id": f"CELL-{i:05d}",
                "kind": "synthetic",
                "state_block": state_text(c["age"], c["sex"], c["bmi"], c["bp"], c["chol"],
                                          c["diab"], c["smoke"], c["active"], c["health"],
                                          c["stroke"], c["walk"]),
                "questions": qs,
                "expected": {},
            }) + "\n")
    print(f"wrote {a.out}")

    # ---- what actually happened to the real respondents in each cell
    df = pd.read_parquet(a.cohort)
    df["bmi_b"] = pd.cut(df.bmi, [0, 25, 30, 200], right=False,
                         labels=["under 25", "25 to 30", "30 or more"]).astype(str)
    df["health_b"] = df.general_health.map({"excellent": "excellent", "very good": "excellent",
                                            "good": "good", "fair": "fair", "poor": "fair"})
    # cast the flags to int so the group keys are "1"/"0" and not "1.0"/"0.0" - the app
    # builds these keys in JavaScript and a float string would silently never match
    flag_cols = ["high_blood_pressure", "high_cholesterol", "diabetes", "smoked_100_cigarettes",
                 "any_physical_activity", "ever_stroke", "difficulty_walking"]
    for c in flag_cols:
        df[c] = df[c].astype("int64")
    keys = ["age_band", "sex", "bmi_b", "high_blood_pressure", "high_cholesterol", "diabetes",
            "smoked_100_cigarettes", "any_physical_activity", "health_b", "ever_stroke",
            "difficulty_walking"]
    g = df.groupby(keys, observed=True).heart_disease.agg(["mean", "size"])
    exact = {("|".join(str(x) for x in idx)): [round(float(r["mean"]), 4), int(r["size"])]
             for idx, r in g.iterrows()}
    print(f"exact cells present in the survey: {len(exact):,}")

    # wider match: age band + the three conditions people can change most
    wide_keys = ["age_band", "high_blood_pressure", "high_cholesterol", "ever_stroke"]
    gw = df.groupby(wide_keys, observed=True).heart_disease.agg(["mean", "size"])
    wide = {("|".join(str(x) for x in idx)): [round(float(r["mean"]), 4), int(r["size"])]
            for idx, r in gw.iterrows()}

    out = {"exact": exact, "wide": wide, "cohort_n": int(len(df)),
           "cohort_rate": round(float(df.heart_disease.mean()), 4),
           "keys": keys, "wide_keys": wide_keys, "n_cells": len(cells)}
    json.dump(out, open(a.truth, "w"))
    print(f"wrote {a.truth} ({os.path.getsize(a.truth)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
