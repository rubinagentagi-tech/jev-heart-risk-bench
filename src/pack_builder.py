#!/usr/bin/env python3
"""
pack_builder.py - turn the CDC BRFSS cohort into a Jev decision pack.

Design rules this file obeys (learned on earlier packs):
  * the request must not reveal the answer - the state carries only survey answers,
    never the recorded diagnosis;
  * every option must be defined in the criteria, including the escape hatches;
  * no arithmetic is asked of the model - BMI is given as a number, the count of
    risk factors is computed in Python (see score.py);
  * the population base rate is stated so the model can calibrate instead of hedge.

    python pack_builder.py --n 5000 --seed 20260920
"""
import argparse, json, os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
COHORT = os.path.join(HERE, "cohort.parquet")

PRETTY = {
    "high_blood_pressure": "diagnosed high blood pressure",
    "high_cholesterol": "diagnosed high cholesterol",
    "cholesterol_checked": "blood cholesterol checked within the last 5 years",
    "smoked_100_cigarettes": "has smoked at least 100 cigarettes in their life",
    "ever_stroke": "has ever been told they had a stroke",
    "diabetes": "diagnosed diabetes",
    "any_physical_activity": "any physical activity or exercise in the past month",
    "fruit_daily": "eats fruit at least once a day",
    "vegetables_daily": "eats vegetables at least once a day",
    "heavy_alcohol": "heavy alcohol use",
    "has_health_coverage": "has health care coverage",
    "no_doctor_due_to_cost": "needed to see a doctor in the past year but could not afford it",
    "difficulty_walking": "serious difficulty walking or climbing stairs",
}

BANDS = ["low", "moderate", "elevated", "high"]

# ---- contract v2. v1 described each band by counting risk factors ("several risk
# factors acting together"), which is how MOST adults answer - so the model put 45% of
# respondents in "elevated" against a 9% base rate. v2 anchors the bands to the observed
# rate and says out loud which combinations actually carry a multiplier. Same model, same
# rows; only the contract changes.
CRITERIA_BAND_V2 = {
    "low": "Under 5 percent, clearly below the general adult rate. No cardiovascular diagnosis, "
           "no more than one mild risk factor, and general health rated good or better.",
    "moderate": "About 5 to 12 percent, around the general adult rate. This is the ordinary band: "
                "one or two risk factors, or age 55 or over with otherwise unremarkable answers, "
                "or general health rated good. Most adults belong here rather than higher.",
    "elevated": "About 12 to 25 percent, roughly one and a half to three times the general adult "
                "rate. Reserve it for a combination that genuinely multiplies risk: age 65 or over "
                "together with a risk factor; or two or more of diabetes, difficulty walking, and "
                "general health rated fair or poor.",
    "high": "Above 25 percent. A previous stroke, or age 75 or over with diabetes, or general "
            "health rated poor together with several risk factors.",
}

CRITERIA_BAND = CRITERIA_BAND_V2 if os.environ.get("CONTRACT", "v2") == "v2" else {
    "low": "Probability under 5 percent. No diagnosed cardiovascular condition and no more than one mild risk factor.",
    "moderate": "Probability about 5 to 12 percent, close to the general adult rate. One or two risk factors present, or age 60 or over with otherwise unremarkable answers.",
    "elevated": "Probability about 12 to 25 percent. Several risk factors acting together, for example high blood pressure plus high cholesterol, or diabetes, or a previous stroke.",
    "high": "Probability above 25 percent. Multiple strong risk factors stacking up, or an existing cardiovascular condition such as a prior stroke at an older age.",
}

CRITERIA_DRIVER = {
    "high_blood_pressure": "Recorded high blood pressure is the strongest risk factor actually present.",
    "high_cholesterol": "Recorded high cholesterol is the strongest risk factor actually present.",
    "smoking_history": "Having smoked at least 100 cigarettes is the strongest risk factor actually present.",
    "diabetes": "Recorded diabetes is the strongest risk factor actually present.",
    "obesity": "Body mass index of 30 or more is the strongest risk factor actually present.",
    "physical_inactivity": "No physical activity in the past month is the strongest risk factor actually present.",
    "age": "Age of 65 or over is the strongest risk factor actually present.",
    "poor_self_rated_health": "Self-rated general health of fair or poor is the strongest risk factor actually present.",
    "prior_stroke": "A recorded stroke is the strongest risk factor actually present.",
    "none_clear": "No single recorded factor stands out; on the recorded answers this respondent looks unremarkable.",
}


def questions():
    # CONTRACT=v3 drops the four-way band and asks for the probability directly as a
    # typed judgement. The band forces the model to pick a label from a description; a
    # noul returns a calibrated number whose cut-off belongs in code, where it can be
    # tuned and reported as a precision/coverage trade-off.
    if os.environ.get("CONTRACT", "v2") == "v3":
        return {
            "has_heart_disease": {
                "type": "noul",
                "instructions": (
                    "Has THIS respondent ever been told by a doctor that they had a heart attack "
                    "or coronary heart disease? Judge only from the survey answers in the state. "
                    "About one in eleven US adults in this survey have been told that, so most "
                    "respondents have not."),
            },
            "top_driver": {
                "type": "choice",
                "instructions": (
                    "Which single recorded factor most raises THIS respondent's probability? Choose "
                    "only a factor that is actually recorded as present in the state."),
                "criteria": CRITERIA_DRIVER,
            },
            "modifiable_risk_present": {
                "type": "noul",
                "instructions": (
                    "Is at least one modifiable risk factor present that a lifestyle or treatment "
                    "change could address? Count high blood pressure, high cholesterol, diabetes, "
                    "smoking history, obesity (body mass index 30 or more), physical inactivity and "
                    "heavy alcohol use."),
            },
            "flag_for_followup": {
                "type": "noul",
                "instructions": (
                    "Should this respondent be flagged for a follow-up conversation with a clinician "
                    "about their heart disease risk?"),
            },
        }
    return {
        "risk_band": {
            "type": "choice",
            "instructions": (
                "Using only the survey answers in the state, which band best describes the probability "
                "that THIS respondent has ever been told by a doctor that they had a heart attack or "
                "coronary heart disease? About one in eleven US adults in this survey have been told that. "
                "Answer with the band that matches the answers you were given."),
            "criteria": CRITERIA_BAND,
        },
        "top_driver": {
            "type": "choice",
            "instructions": (
                "Which single recorded factor most raises THIS respondent's probability? Choose only a "
                "factor that is actually recorded as present in the state."),
            "criteria": CRITERIA_DRIVER,
        },
        "modifiable_risk_present": {
            "type": "noul",
            "instructions": (
                "Is at least one modifiable risk factor present that a lifestyle or treatment change "
                "could address? Count high blood pressure, high cholesterol, diabetes, smoking history, "
                "obesity (body mass index 30 or more), physical inactivity and heavy alcohol use."),
        },
        "flag_for_followup": {
            "type": "noul",
            "instructions": (
                "Should this respondent be flagged for a follow-up conversation with a clinician about "
                "their heart disease risk?"),
        },
    }


def yesno(v):
    return "yes" if v == 1.0 else ("no" if v == 0.0 else "unknown")


def state_text(r):
    """The whole input the model sees: plain survey answers, no diagnosis, no arithmetic."""
    return (
        f"US adult health survey respondent.\n"
        f"Age band: {r.age_band}\n"
        f"Sex: {r.sex}\n"
        f"Body mass index: {r.bmi:.1f}\n"
        f"Self-rated general health: {r.general_health}\n"
        f"Days of poor physical health in the past 30 days: {int(r.poor_physical_health_days)}\n"
        f"Days of poor mental health in the past 30 days: {int(r.poor_mental_health_days)}\n"
        f"Told by a doctor they have high blood pressure: {yesno(r.high_blood_pressure)}\n"
        f"Told by a doctor their blood cholesterol is high: {yesno(r.high_cholesterol)}\n"
        f"Blood cholesterol checked in the last 5 years: {yesno(r.cholesterol_checked)}\n"
        f"Ever told they have diabetes: {yesno(r.diabetes)}\n"
        f"Ever told they had a stroke: {yesno(r.ever_stroke)}\n"
        f"Smoked at least 100 cigarettes in their life: {yesno(r.smoked_100_cigarettes)}\n"
        f"Any physical activity or exercise in the past month: {yesno(r.any_physical_activity)}\n"
        f"Eats fruit at least once a day: {yesno(r.fruit_daily)}\n"
        f"Eats vegetables at least once a day: {yesno(r.vegetables_daily)}\n"
        f"Heavy alcohol use: {yesno(r.heavy_alcohol)}\n"
        f"Has any health care coverage: {yesno(r.has_health_coverage)}\n"
        f"Needed a doctor in the past 12 months but could not afford it: {yesno(r.no_doctor_due_to_cost)}\n"
        f"Serious difficulty walking or climbing stairs: {yesno(r.difficulty_walking)}\n"
        f"Education: {r.education}\n"
        f"Annual household income: {r.income}\n"
    )


def answer_key(r):
    """Deterministic truth, computed in Python. Never sent to the model."""
    modifiable = [
        r.high_blood_pressure == 1.0,
        r.high_cholesterol == 1.0,
        r.diabetes == 1.0,
        r.smoked_100_cigarettes == 1.0,
        r.bmi >= 30,
        r.any_physical_activity == 0.0,
        r.heavy_alcohol == 1.0,
    ]
    driver_truth = {
        "high_blood_pressure": r.high_blood_pressure == 1.0,
        "high_cholesterol": r.high_cholesterol == 1.0,
        "smoking_history": r.smoked_100_cigarettes == 1.0,
        "diabetes": r.diabetes == 1.0,
        "obesity": r.bmi >= 30,
        "physical_inactivity": r.any_physical_activity == 0.0,
        "age": int(r._age_code) >= 10,                      # 65 or over
        "poor_self_rated_health": r.general_health in ("fair", "poor"),
        "prior_stroke": r.ever_stroke == 1.0,
    }
    return {
        "heart_disease": int(r.heart_disease),
        "modifiable_risk_present": any(modifiable),
        "risk_factor_count": int(sum(modifiable)),
        "driver_truth": driver_truth,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5000, help="number of respondents to score")
    ap.add_argument("--seed", type=int, default=20260920)
    ap.add_argument("--out", default=os.path.join(HERE, "cases.jsonl"))
    a = ap.parse_args()

    df = pd.read_parquet(COHORT)
    # keep the raw age code around for the key (65+ = codes 10-13)
    from derive_cohort import AGE_BANDS
    codes = {v: k for k, v in AGE_BANDS.items()}
    df["_age_code"] = df["age_band"].map(codes)
    print(f"cohort {len(df):,} rows, base rate {df.heart_disease.mean():.4f}")

    # random sample preserving the natural base rate: a stratified sample would
    # distort exactly what we are measuring (calibration against the real rate)
    n = min(a.n, len(df))
    rng = np.random.default_rng(a.seed)
    idx = rng.choice(len(df), size=n, replace=False)   # already in random order:
    sample = df.iloc[idx].reset_index(drop=True)       # a prefix slice stays representative
    print(f"sample {len(sample):,} rows, base rate {sample.heart_disease.mean():.4f} "
          f"({int(sample.heart_disease.sum()):,} positives)")

    qs = questions()
    with open(a.out, "w") as f:
        for _, r in sample.iterrows():
            case = {
                "id": r.record_id,
                "kind": "positive" if r.heart_disease == 1 else "negative",
                "state_block": state_text(r),
                "questions": qs,
                "expected": answer_key(r),
            }
            f.write(json.dumps(case) + "\n")
    print(f"wrote {a.out}")
    # sidecar: full sample table for the baselines + visualisation
    keep = ["record_id", "heart_disease", "age_band", "sex", "bmi", "general_health",
            "poor_physical_health_days", "poor_mental_health_days", "high_blood_pressure",
            "high_cholesterol", "cholesterol_checked", "diabetes", "ever_stroke",
            "smoked_100_cigarettes", "any_physical_activity", "fruit_daily", "vegetables_daily",
            "heavy_alcohol", "has_health_coverage", "no_doctor_due_to_cost", "difficulty_walking",
            "education", "income"]
    sample[keep].to_parquet(os.path.join(HERE, "sample.parquet"), index=False)
    df[keep].to_parquet(os.path.join(HERE, "cohort_clean.parquet"), index=False)
    print(f"wrote sample.parquet ({len(sample):,}) and cohort_clean.parquet ({len(df):,})")


if __name__ == "__main__":
    main()
