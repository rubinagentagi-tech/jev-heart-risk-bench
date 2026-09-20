import json, os, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
df = pd.read_parquet(os.path.join(HERE, "cohort_clean.parquet"))
print("cohort", len(df), "base rate", round(df.heart_disease.mean(), 4))
print("\n=== heart disease rate by factor present/absent ===")
for col in ["high_blood_pressure", "high_cholesterol", "diabetes", "smoked_100_cigarettes",
            "ever_stroke", "any_physical_activity", "heavy_alcohol", "difficulty_walking",
            "no_doctor_due_to_cost", "fruit_daily", "vegetables_daily"]:
    a = df[df[col] == 1].heart_disease.mean(); b = df[df[col] == 0].heart_disease.mean()
    print(f"{col:26s} present {a:.4f}  absent {b:.4f}   ratio {a/b if b else float('nan'):.2f}")
print("\n=== by age band ===")
print(df.groupby("age_band", observed=True).heart_disease.agg(['mean', 'size']).round(4).to_string())
print("\n=== by BMI bucket ===")
df["bmi_b"] = pd.cut(df.bmi, [0, 18.5, 25, 30, 35, 40, 100],
                     labels=['<18.5', '18.5-25', '25-30', '30-35', '35-40', '40+'])
print(df.groupby("bmi_b", observed=True).heart_disease.agg(['mean', 'size']).round(4).to_string())
cnt = ((df.high_blood_pressure == 1).astype(int) + (df.high_cholesterol == 1).astype(int)
       + (df.diabetes == 1).astype(int) + (df.smoked_100_cigarettes == 1).astype(int)
       + (df.bmi >= 30).astype(int) + (df.any_physical_activity == 0).astype(int)
       + (df.heavy_alcohol == 1).astype(int))
print("\n=== classic risk-factor count vs heart disease ===")
print(pd.DataFrame({'c': cnt, 'y': df.heart_disease}).groupby('c').y.agg(['mean', 'size']).round(4).to_string())
print("\n=== general health ===")
print(df.groupby("general_health", observed=True).heart_disease.agg(['mean', 'size']).round(4).to_string())
print("\n=== by age x stroke ===")
print(df.pivot_table(index="age_band", columns="ever_stroke", values="heart_disease",
                     aggfunc="mean", observed=True).round(3).to_string())
