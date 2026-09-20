#!/usr/bin/env python3
"""
derive_cohort.py - build the analysis cohort DIRECTLY from the raw CDC BRFSS 2015 file.

Source (public domain, US federal government work - 17 U.S.C. 105):
  Centers for Disease Control and Prevention, Behavioral Risk Factor Surveillance System,
  2015 annual survey data (all states + territories, landline and cell phone).
  https://www.cdc.gov/brfss/annual_data/annual_2015.html
  File: LLCP2015XPT.zip  ->  LLCP2015.XPT   (441,456 records)

Every value mapping below is taken from the official BRFSS 2015 Codebook Report
(https://www.cdc.gov/brfss/annual_data/2015/pdf/codebook15_llcp.pdf), not guessed:
each variable's code list is quoted in the MAPPING dict comments.

Output: cohort.parquet - one row per respondent who answered every question the
decision model is given. The label column `heart_disease` is NEVER sent to the model;
it is the answer key.
"""
import sys, os, time
import numpy as np
import pandas as pd
import pyreadstat

DATA = os.environ.get("BRFSS_XPT", "/tmp/brfss2015.xpt")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cohort.parquet")

# Raw BRFSS columns we pull out of the 1.1 GB transport file.
RAW = ["_MICHD", "CVDINFR4", "CVDCRHD4", "_RFHYPE5", "_RFCHOL", "CHOLCHK", "_BMI5",
       "SMOKE100", "CVDSTRK3", "DIABETE3", "EXERANY2", "_FRTLT1", "_VEGLT1", "_RFDRHV5",
       "HLTHPLN1", "MEDCOST", "GENHLTH", "MENTHLTH", "PHYSHLTH", "DIFFWALK", "SEX",
       "_AGEG5YR", "EDUCA", "INCOME2", "_STATE"]

# ---------------------------------------------------------------- mappings
# Each raw code is taken from the official BRFSS 2015 Codebook Report. Watch the
# two computed flags below: _RFHYPE5 and _RFCHOL are coded 1 = No, 2 = Yes, the
# opposite of the raw question variables. Getting that backwards silently inverts
# two of the strongest risk factors - which is exactly what happened on the first
# run of this pack, and it made the model look worthless when the data was wrong.
def yn(df, col, yes=1, no=2):
    """BRFSS yes/no column -> 1 / 0 / NaN (7 don't know and 9 refused become NaN)."""
    v = df[col]
    out = pd.Series(np.nan, index=df.index, dtype="float")
    out[v == yes] = 1.0
    out[v.isin(no if isinstance(no, (list, tuple, set)) else [no])] = 0.0
    return out


AGE_BANDS = {1: "18-24", 2: "25-29", 3: "30-34", 4: "35-39", 5: "40-44", 6: "45-49",
             7: "50-54", 8: "55-59", 9: "60-64", 10: "65-69", 11: "70-74",
             12: "75-79", 13: "80+"}
EDU = {1: "never attended school or kindergarten only", 2: "grades 1-8 (elementary)",
       3: "grades 9-11 (some high school)", 4: "grade 12 or GED (high school graduate)",
       5: "college 1-3 years (some college or technical school)", 6: "college 4 years or more"}
INCOME = {1: "under $10,000", 2: "$10,000-$15,000", 3: "$15,000-$20,000", 4: "$20,000-$25,000",
          5: "$25,000-$35,000", 6: "$35,000-$50,000", 7: "$50,000-$75,000", 8: "$75,000 or more"}
GENHLTH = {1: "excellent", 2: "very good", 3: "good", 4: "fair", 5: "poor"}


def days(v):
    """MENTHLTH / PHYSHLTH: 1-30 days, 88 = None, 77/99 = don't know / refused."""
    v = v.copy()
    v[v == 88] = 0
    v[~v.isin(range(0, 31))] = np.nan
    return v


def sanity_check(out):
    """Known-direction check. A sign flip in any of these means a codebook mapping is
    wrong, and it must stop the build rather than quietly poison the benchmark."""
    checks = []
    for col in ("high_blood_pressure", "high_cholesterol", "diabetes", "ever_stroke",
                "smoked_100_cigarettes", "difficulty_walking"):
        present = out.loc[out[col] == 1, "heart_disease"].mean()
        absent = out.loc[out[col] == 0, "heart_disease"].mean()
        checks.append((col, present, absent, present > absent))
    for col in ("any_physical_activity",):
        present = out.loc[out[col] == 1, "heart_disease"].mean()
        absent = out.loc[out[col] == 0, "heart_disease"].mean()
        checks.append((col, present, absent, present < absent))
    young = out.loc[out.age_band.isin(["18-24", "25-29", "30-34"]), "heart_disease"].mean()
    old = out.loc[out.age_band.isin(["70-74", "75-79", "80+"]), "heart_disease"].mean()
    checks.append(("age (old > young)", old, young, old > young))

    bad = [c for c in checks if not c[3]]
    print("  data integrity checks (rate with factor vs without):", flush=True)
    for name, a, b, ok in checks:
        print(f"    {'ok ' if ok else 'FAIL'} {name:24s} {a:.4f} vs {b:.4f}", flush=True)
    if bad:
        raise SystemExit(f"ABORT: {len(bad)} mapping(s) have the wrong sign: "
                         f"{[b[0] for b in bad]}")
    print(f"  all {len(checks)} checks passed", flush=True)


def main():
    t0 = time.time()
    print(f"reading {DATA} ...", flush=True)
    df, meta = pyreadstat.read_xport(DATA, usecols=RAW)
    print(f"  read {len(df):,} records x {df.shape[1]} variables in {time.time()-t0:.0f}s", flush=True)

    out = pd.DataFrame(index=df.index)
    # ---- answer key: "ever told had a heart attack or coronary heart disease"
    out["heart_disease"] = np.where(df["_MICHD"] == 1, 1.0,
                                    np.where(df["_MICHD"] == 2, 0.0, np.nan))
    out["ever_heart_attack"] = yn(df, "CVDINFR4")
    out["ever_chd_angina"] = yn(df, "CVDCRHD4")
    # ---- risk factors
    out["high_blood_pressure"] = yn(df, "_RFHYPE5", yes=2, no=1)   # 1=No 2=Yes
    out["high_cholesterol"] = yn(df, "_RFCHOL", yes=2, no=1)       # 1=No 2=Yes
    out["cholesterol_checked"] = np.where(df["CHOLCHK"].isin([1, 2, 3, 4]), 1.0,
                                 np.where(df["CHOLCHK"].isin([7, 9]), np.nan, 0.0))
    out["smoked_100_cigarettes"] = yn(df, "SMOKE100")
    out["ever_stroke"] = yn(df, "CVDSTRK3")
    out["diabetes"] = np.where(df["DIABETE3"] == 1, 1.0,
                      np.where(df["DIABETE3"].isin([2, 3, 4]), 0.0, np.nan))
    out["any_physical_activity"] = yn(df, "EXERANY2")
    out["fruit_daily"] = np.where(df["_FRTLT1"] == 1, 1.0, np.where(df["_FRTLT1"] == 2, 0.0, np.nan))
    out["vegetables_daily"] = np.where(df["_VEGLT1"] == 1, 1.0, np.where(df["_VEGLT1"] == 2, 0.0, np.nan))
    out["heavy_alcohol"] = np.where(df["_RFDRHV5"] == 2, 1.0, np.where(df["_RFDRHV5"] == 1, 0.0, np.nan))
    out["has_health_coverage"] = yn(df, "HLTHPLN1")
    out["no_doctor_due_to_cost"] = yn(df, "MEDCOST")
    out["difficulty_walking"] = yn(df, "DIFFWALK")
    # ---- self-reported health
    out["general_health"] = df["GENHLTH"].map(GENHLTH)
    out["poor_mental_health_days"] = days(df["MENTHLTH"])
    out["poor_physical_health_days"] = days(df["PHYSHLTH"])
    # ---- demographics / context
    out["bmi"] = pd.to_numeric(df["_BMI5"], errors="coerce") / 100.0
    out["bmi"] = out["bmi"].where(out["bmi"].between(10, 100))
    out["sex"] = df["SEX"].map({1: "male", 2: "female"})
    out["age_band"] = df["_AGEG5YR"].map(AGE_BANDS)
    out["education"] = df["EDUCA"].map(EDU)
    out["income"] = df["INCOME2"].map(INCOME)

    # ---- keep only complete rows over the fields the decision model actually sees
    features = [c for c in out.columns if c not in ("heart_disease", "ever_heart_attack", "ever_chd_angina")]
    before = len(out)
    out = out.dropna(subset=["heart_disease"] + features)
    print(f"  complete-case filter: {before:,} -> {len(out):,} ({len(out)/before:.1%})", flush=True)
    print(f"  base rate (heart disease): {out['heart_disease'].mean():.4f} "
          f"({int(out['heart_disease'].sum()):,} positives)", flush=True)

    out = out.reset_index(drop=True)
    out.insert(0, "record_id", ["BRFSS2015-%06d" % (i + 1) for i in range(len(out))])
    sanity_check(out)
    out.to_parquet(OUT, index=False)
    print(f"wrote {OUT}  rows={len(out):,} cols={out.shape[1]}  in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
