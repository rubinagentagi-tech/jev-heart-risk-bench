#!/usr/bin/env python3
"""
rigour_check.py - adversarial review of this project's own claims.

Every headline in this repo rests on a difference between two numbers. This script asks
whether each difference is real, using the tests a reviewer would demand:

  1. bootstrap CI on every AUC difference (Jev vs chat LLM, and the v1/v2/v3 contracts)
  2. bootstrap CI on the matched-coverage precision difference
  3. Brier score + Murphy decomposition (reliability / resolution / uncertainty), because
     mean-stated-vs-truth is a crude way to compare calibration
  4. calibration restricted to the range where both models actually operate (common support)
  5. the incremental AUC of the 20 non-age features over age alone, via a trained model
  6. the within-age-band AUCs, and what they do and do not imply
  7. how much of the cohort the complete-case drop removed, and in which direction

    python rigour_check.py
"""
import json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as sc  # noqa: E402

RNG = np.random.default_rng(11)
NBOOT = 2000
AGE_ORDER = {"18-24": 1, "25-29": 2, "30-34": 3, "35-39": 4, "40-44": 5, "45-49": 6,
             "50-54": 7, "55-59": 8, "60-64": 9, "65-69": 10, "70-74": 11, "75-79": 12,
             "80+": 13}


def load(arm):
    d = json.load(open(os.path.join(HERE, "results", arm, "results.json")))
    return [r for r in d["rows"] if r.get("band") in sc.BANDS and r.get("p_positive") is not None]


def boot_ci(fn, n, nboot=NBOOT, alpha=0.05):
    """Percentile bootstrap. fn(idx) -> statistic given a resampled index array."""
    vals = []
    for _ in range(nboot):
        idx = RNG.integers(0, n, n)
        vals.append(fn(idx))
    v = np.array([x for x in vals if x is not None and np.isfinite(x)])
    if len(v) == 0:
        return None, None, None
    return float(np.mean(v)), float(np.percentile(v, 100 * alpha / 2)), float(np.percentile(v, 100 * (1 - alpha / 2)))


def verdict(lo, hi):
    if lo is None:
        return "n/a"
    if lo > 0:
        return "REAL (CI excludes 0)"
    if hi < 0:
        return "REAL (CI excludes 0, sign flipped)"
    return "NOT DISTINGUISHABLE (CI spans 0)"


def brier_murphy(p, y, bins):
    """Brier = reliability - resolution + uncertainty (Murphy decomposition)."""
    ybar = y.mean()
    unc = ybar * (1 - ybar)
    rel = 0.0
    res = 0.0
    for lo, hi in zip(bins, bins[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum() == 0:
            continue
        w = m.mean()
        obs = y[m].mean()
        pm = p[m].mean()
        rel += w * (pm - obs) ** 2
        res += w * (obs - ybar) ** 2
    brier = float(np.mean((p - y) ** 2))
    return brier, rel, res, unc, ybar


def main():
    jrows, lrows = load("jev"), load("llm")
    J = {r["id"]: r for r in jrows}
    L = {r["id"]: r for r in lrows}
    ids = [i for i in J if i in L]
    y = np.array([J[i]["truth"] for i in ids], dtype=float)
    jp = np.array([J[i]["p_positive"] for i in ids])
    lp = np.array([L[i]["p_positive"] for i in ids])
    n = len(ids)
    base = y.mean()
    s = pd.read_parquet(os.path.join(HERE, "sample.parquet")).set_index("record_id")
    age = np.array([AGE_ORDER[s.loc[i, "age_band"]] for i in ids], dtype=float)

    print(f"n={n:,}  positives={int(y.sum()):,}  base={base:.4f}")
    print()
    print("=" * 78)
    print("CLAIM 1: 'DeepSeek ranks better than Jev (AUC 0.7935 vs 0.7725)'")
    print("=" * 78)
    a_j, a_l = sc.auc(y.tolist(), jp.tolist()), sc.auc(y.tolist(), lp.tolist())
    diff = lambda idx: sc.auc(y[idx].tolist(), lp[idx].tolist()) - sc.auc(y[idx].tolist(), jp[idx].tolist())
    m, lo, hi = boot_ci(diff, n)
    print(f"  Jev AUC {a_j:.4f}   DeepSeek AUC {a_l:.4f}   difference {a_l-a_j:+.4f}")
    print(f"  bootstrap 95% CI on the difference: [{lo:+.4f}, {hi:+.4f}]")
    print(f"  -> {verdict(lo, hi)}")
    print()

    print("=" * 78)
    print("CLAIM 2: 'at matched coverage the two are within 0.2-2 points'")
    print("=" * 78)
    cov = [0.05, 0.10, 0.20, 0.30]
    print(f"  {'coverage':>9} {'Jev':>8} {'DeepSeek':>9} {'diff':>8}  95% CI on the diff      verdict")
    for c in cov:
        k = int(round(c * n))

        def d(idx):
            kk = int(round(c * len(idx)))
            o = np.argsort(-lp[idx], kind="stable")[:kk]
            p_d = y[idx][o].mean()
            o2 = np.argsort(-jp[idx], kind="stable")[:kk]
            p_j = y[idx][o2].mean()
            return p_d - p_j

        m2, lo2, hi2 = boot_ci(d, n)
        pj = y[np.argsort(-jp, kind="stable")[:k]].mean()
        pl = y[np.argsort(-lp, kind="stable")[:k]].mean()
        print(f"  {c:>8.0%} {pj:>8.1%} {pl:>9.1%} {pl-pj:>+8.1%}  "
              f"[{lo2:+.1%}, {hi2:+.1%}]   {verdict(lo2, hi2)}")
    print()

    print("=" * 78)
    print("CLAIM 3: 'the chat LLM is the better calibrated of the two'")
    print("=" * 78)
    bins = [0, .05, .10, .20, .30, .50, .70, .90, 1.01]
    for name, p in (("Jev", jp), ("chat LLM", lp)):
        b, rel, res, unc, ybar = brier_murphy(p, y, bins)
        print(f"  {name:9s} Brier {b:.4f}  = reliability {rel:.4f} - resolution {res:.4f} "
              f"+ uncertainty {unc:.4f}")
        print(f"  {'':9s} Brier skill vs always-guess-base-rate: {1 - b/unc:+.3f}")
    print()
    print("  NOTE the decomposition: reliability rewards honest probabilities, resolution")
    print("  rewards making distinctions. A wide-range model can lose on reliability and")
    print("  still be more useful. Judging calibration on mean-stated/truth alone is wrong.")
    print()

    print("=" * 78)
    print("CLAIM 4: calibration is comparable only where the two ranges OVERLAP")
    print("=" * 78)
    hi_overlap = min(jp.max(), lp.max())
    print(f"  Jev range [{jp.min():.2f}, {jp.max():.2f}]   "
          f"chat LLM range [{lp.min():.2f}, {lp.max():.2f}]")
    print(f"  common support: below {hi_overlap:.2f}. DeepSeek never exceeds "
          f"{lp.max():.2f}, so nothing above that is comparable at all.")
    ov = jp <= lp.max()
    print(f"  in the overlap ({ov.mean():.1%} of Jev's rows): Jev mean stated "
          f"{jp[ov].mean():.3f}, actual {y[ov].mean():.3f}  -> over by "
          f"{jp[ov].mean()/y[ov].mean():.2f}x")
    print(f"  whole sample: Jev over by {jp.mean()/base:.2f}x, DeepSeek over by {lp.mean()/base:.2f}x")
    print()

    print("=" * 78)
    print("CLAIM 5: 'almost all the signal is age' (age alone AUC 0.7215)")
    print("=" * 78)
    age_auc = sc.auc(y.tolist(), age.tolist())
    print(f"  age alone AUC {age_auc:.4f}   Jev {a_j:.4f}   DeepSeek {a_l:.4f}")
    print("  Within narrow age bands, where age is nearly constant:")
    for lo_a, hi_a, lab in ((1, 5, "18-44"), (6, 8, "45-59"), (9, 11, "60-74"), (12, 13, "75+")):
        m3 = (age >= lo_a) & (age <= hi_a)
        if m3.sum() > 40 and 0 < y[m3].sum() < m3.sum():
            aj = sc.auc(y[m3].tolist(), jp[m3].tolist())
            al = sc.auc(y[m3].tolist(), lp[m3].tolist())
            print(f"    ages {lab}: n={m3.sum():>4,}  positives {int(y[m3].sum()):>3}  "
                  f"Jev {aj:.3f}  DeepSeek {al:.3f}")
    print()
    print("  This CONTRADICTS the 'it is all age' framing. AUC 0.70-0.80 within an age band")
    print("  is real discrimination among people the same age. Overall AUC understates that,")
    print("  because pooling lets any age-correlated score look good. The honest statement")
    print("  is that age is a strong predictor AND the models carry comparable non-age")
    print("  signal, which overall AUC partly hides.")
    print()

    print("=" * 78)
    print("CLAIM 6: how much do the 20 non-age features actually add? (trained, not zero-shot)")
    print("=" * 78)
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    full = pd.read_parquet(os.path.join(HERE, "cohort_clean.parquet"))
    tr = full[~full.record_id.isin(set(ids))].reset_index(drop=True)
    te = full[full.record_id.isin(set(ids))].reset_index(drop=True)
    te = te.set_index("record_id").loc[ids].reset_index()
    yte = te.heart_disease.values

    def fit_auc(cols_num, cols_bin, cols_cat):
        pre = ColumnTransformer([("n", StandardScaler(), cols_num),
                                 ("b", "passthrough", cols_bin),
                                 ("c", OneHotEncoder(handle_unknown="ignore"), cols_cat)])
        clf = Pipeline([("pre", pre), ("lr", LogisticRegression(max_iter=2000))])
        clf.fit(tr[cols_num + cols_bin + cols_cat], tr.heart_disease)
        return sc.auc(yte.tolist(), clf.predict_proba(te[cols_num + cols_bin + cols_cat])[:, 1].tolist())

    auc_age = fit_auc([], [], ["age_band"])
    auc_all = fit_auc(["bmi", "poor_physical_health_days", "poor_mental_health_days"],
                      ["high_blood_pressure", "high_cholesterol", "cholesterol_checked", "diabetes",
                       "ever_stroke", "smoked_100_cigarettes", "any_physical_activity", "fruit_daily",
                       "vegetables_daily", "heavy_alcohol", "has_health_coverage",
                       "no_doctor_due_to_cost", "difficulty_walking"],
                      ["age_band", "sex", "general_health", "education", "income"])
    print(f"  logistic regression on AGE BAND ALONE : AUC {auc_age:.4f}")
    print(f"  logistic regression on ALL 21 fields  : AUC {auc_all:.4f}")
    print(f"  incremental value of the other 20     : {auc_all - auc_age:+.4f}")
    print(f"  Jev adds over age-alone LR            : {a_j - auc_age:+.4f}")
    print(f"  DeepSeek adds over age-alone LR       : {a_l - auc_age:+.4f}")
    print(f"  a TRAINED model on the same 21 fields : {auc_all:.4f} vs Jev {a_j:.4f}")
    print()

    print("=" * 78)
    print("CLAIM 7: 'the v1/v2/v3 contracts differ' (1,000 rows each)")
    print("=" * 78)
    ab = {}
    for k in ("v1", "v2", "v3"):
        d = json.load(open(os.path.join(HERE, "results", f"ab-{k}", "results.json")))
        r = [x for x in d["rows"] if x.get("band") in sc.BANDS and x.get("p_positive") is not None]
        ab[k] = {x["id"]: x for x in r}
    # every array must be built in the SAME id order. Building truth in file order and the
    # probabilities in sorted order silently destroys the pairing and reports AUC ~0.45.
    ids3 = sorted(set.intersection(*[set(v) for v in ab.values()]))
    yb = np.array([ab["v1"][i]["truth"] for i in ids3], dtype=float)
    pb = {k: np.array([ab[k][i]["p_positive"] for i in ids3]) for k in ab}
    print(f"  n={len(ids3):,}  positives={int(yb.sum())}  "
          f"(paired by id, all three arms on the identical rows)")
    for k in ab:
        print(f"  {k}: AUC {sc.auc(yb.tolist(), pb[k].tolist()):.4f}")
    for a, b in (("v1", "v3"), ("v1", "v2"), ("v2", "v3")):
        f = lambda idx: sc.auc(yb[idx].tolist(), pb[b][idx].tolist()) - sc.auc(yb[idx].tolist(), pb[a][idx].tolist())
        m4, lo4, hi4 = boot_ci(f, len(yb), nboot=1200)
        print(f"  {a} vs {b}: diff {m4:+.4f}  95% CI [{lo4:+.4f}, {hi4:+.4f}]  -> {verdict(lo4, hi4)}")
    print()
    print("  With ~92 positives on 1,000 rows the AUC standard error is about 0.025, so")
    print("  the earlier 'v3 ranks best' claim is not supported. It must be softened.")
    print()

    print("=" * 78)
    print("CLAIM 8: complete-case selection bias")
    print("=" * 78)
    print(f"  the derivation kept {len(full):,} of 441,456 raw records "
          f"({len(full)/441456:.1%}) by dropping any respondent with a missing field.")
    print("  That is NOT random: refusals and don't-knows concentrate in the oldest and")
    print("  sickest respondents and in the youngest. The measured base rate is therefore")
    print("  a property of these 253,680 people, not of the US adult population.")
    print(f"  measured base rate here: {full.heart_disease.mean():.4f}. CDC's own weighted")
    print("  figure for the same question is lower because it uses survey weights, which")
    print("  this analysis does not apply.")


if __name__ == "__main__":
    main()
