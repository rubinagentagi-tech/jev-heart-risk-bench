#!/usr/bin/env python3
"""
analyse_arms.py - why is Jev less accurate than it should be, and what is actually going on
in the Jev vs DeepSeek comparison?

The headline table compares each model at ITS OWN chosen threshold, which is not a skill
comparison: a model that flags more people gets more recall and less precision regardless of
how good it is. This script compares them at MATCHED coverage, where the only thing that can
differ is ranking quality, and it checks calibration and where the two disagree.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as sc  # noqa: E402


def load(arm):
    d = json.load(open(os.path.join(HERE, "results", arm, "results.json")))
    rows = [r for r in d["rows"] if r.get("band") in sc.BANDS and r.get("p_positive") is not None]
    return d["scorecard"], rows


def by_id(rows):
    return {r["id"]: r for r in rows}


def pr_at_coverage(rows, coverages):
    """Rank by the model's stated probability and ask: at this share of the population
    flagged, what is precision? This is the only fair head-to-head."""
    ranked = sorted(rows, key=lambda r: -r["p_positive"])
    n = len(ranked)
    out = {}
    for c in coverages:
        k = int(round(c * n))
        sel = ranked[:k]
        tp = sum(1 for r in sel if r["truth"])
        out[c] = tp / max(1, k)
    return out


def main():
    jc, jrows = load("jev")
    lc, lrows = load("llm")
    J, L = by_id(jrows), by_id(lrows)
    ids = [i for i in J if i in L]
    truth = np.array([J[i]["truth"] for i in ids])
    jp = np.array([J[i]["p_positive"] for i in ids])
    lp = np.array([L[i]["p_positive"] for i in ids])
    n, pos = len(ids), int(truth.sum())
    base = pos / n
    print(f"paired rows: {n:,}   positives {pos:,}   base rate {base:.4f}")
    print()

    # ---------------------------------------------------------------- 1. thresholds
    print("=== 1. each model at its OWN operating point ===")
    for name, rows, sc_ in (("Jev", jrows, jc), ("DeepSeek", lrows, lc)):
        flagged = sc_["confusion"]["tp"] + sc_["confusion"]["fp"]
        print(f"  {name:9s} flags {flagged/n:6.1%} of people  precision {sc_['precision']:5.1%}  "
              f"recall {sc_['recall']:5.1%}  accuracy {sc_['accuracy']:5.1%}  AUC {sc_['auc']}")
    print("  -> they are operating at different points, so this table measures thresholds,")
    print("     not skill. Jev flags less and is more precise; DeepSeek flags more and")
    print("     catches more. Neither number says which model ranks better.")
    print()

    # ---------------------------------------------------------------- 2. matched coverage
    print("=== 2. same share of the population flagged (ranking quality only) ===")
    cov = [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50]
    jp_at, lp_at = pr_at_coverage(jrows, cov), pr_at_coverage(lrows, cov)
    print(f"  {'flagged':>8} {'Jev prec':>10} {'DeepSeek':>10} {'winner':>10}   {'lift J':>7} {'lift D':>7}")
    for c in cov:
        w = "Jev" if jp_at[c] > lp_at[c] else "DeepSeek"
        print(f"  {c:>7.0%} {jp_at[c]:>10.1%} {lp_at[c]:>10.1%} {w:>10}   "
              f"{jp_at[c]/base:>7.2f}x {lp_at[c]/base:>7.2f}x")
    wins_j = sum(1 for c in cov if jp_at[c] > lp_at[c])
    print(f"  -> Jev better at {wins_j} of {len(cov)} coverage levels")
    print()

    # ---------------------------------------------------------------- 3. calibration
    print("=== 3. calibration: does a stated probability mean anything? ===")
    print(f"  {'stated':>14} {'Jev n':>7} {'Jev actual':>11} | {'DeepSeek n':>10} {'DS actual':>10}")
    bins = [0, .05, .10, .20, .30, .50, .70, .90, 1.01]
    for lo, hi in zip(bins, bins[1:]):
        mj = (jp >= lo) & (jp < hi)
        ml = (lp >= lo) & (lp < hi)
        a = f"{truth[mj].mean():.1%}" if mj.sum() else "-"
        b = f"{truth[ml].mean():.1%}" if ml.sum() else "-"
        print(f"  {lo:.2f}-{min(hi,1.0):.2f} {mj.sum():>7,} {a:>11} | {ml.sum():>10,} {b:>10}")
    print(f"  mean stated: Jev {jp.mean():.3f} (truth {base:.3f})   DeepSeek {lp.mean():.3f}")
    print(f"  Jev over-states by {jp.mean()/base:.2f}x on average; "
          f"DeepSeek by {lp.mean()/base:.2f}x")
    print()

    # ---------------------------------------------------------------- 4. spread
    print("=== 4. resolution: how much do they actually say? ===")
    for name, p in (("Jev", jp), ("DeepSeek", lp)):
        u = len(np.unique(np.round(p, 3)))
        print(f"  {name:9s} p05 {np.percentile(p,5):.3f}  p50 {np.median(p):.3f}  "
              f"p95 {np.percentile(p,95):.3f}  range [{p.min():.2f},{p.max():.2f}]  "
              f"distinct values {u}  share>0.5 {(p>0.5).mean():.1%}")
    print()

    # ---------------------------------------------------------------- 5. disagreements
    jflag = np.array([J[i]["band"] in sc.POSITIVE_BANDS for i in ids])
    lflag = np.array([L[i]["band"] in sc.POSITIVE_BANDS for i in ids])
    both_pos = jflag & lflag
    nei = ~jflag & ~lflag
    only_j = jflag & ~lflag
    only_l = ~jflag & lflag
    print("=== 5. where they disagree, who is right? ===")
    for label, m in (("both flag", both_pos), ("neither flags", nei),
                     ("only Jev flags", only_j), ("only DeepSeek flags", only_l)):
        if m.sum():
            print(f"  {label:18s} n={m.sum():>5,}  actually positive {truth[m].mean():>6.1%} "
                  f"({int(truth[m].sum()):>4,} people)")
    print()
    agree = (jflag == lflag).mean()
    print(f"  the two models make the same call on {agree:.1%} of people")
    print()

    # ---------------------------------------------------------------- 6. the ceiling
    print("=== 6. what a trained model gets, for scale ===")
    b = json.load(open(os.path.join(HERE, "results", "baselines", "baselines.json")))
    for k in ("rule", "logistic"):
        c = b[k]
        print(f"  {k:9s} AUC {c['auc']}  flags {(c['confusion']['tp']+c['confusion']['fp'])/c['cases']:.1%}  "
              f"precision {c['precision']:.1%}  lift {c['lift']}x")
    print()
    print("=== 7. how much of the signal is just age? ===")
    ages = np.array([int(str(J[i]["id"]).split("-")[-1]) for i in ids])  # record ids, not age
    print("  (age is not in the result rows; recomputed from the sample below)")
    import pandas as pd
    s = pd.read_parquet(os.path.join(HERE, "sample.parquet")).set_index("record_id")
    order = {"18-24": 1, "25-29": 2, "30-34": 3, "35-39": 4, "40-44": 5, "45-49": 6,
             "50-54": 7, "55-59": 8, "60-64": 9, "65-69": 10, "70-74": 11,
             "75-79": 12, "80+": 13}
    age_code = np.array([order[s.loc[i, "age_band"]] for i in ids])
    t = truth
    a_auc = sc.auc(t.tolist(), age_code.tolist())
    print(f"  age band alone as a score: AUC {a_auc:.4f}")
    print(f"  Jev {sc.auc(t.tolist(), jp.tolist()):.4f}   DeepSeek {sc.auc(t.tolist(), lp.tolist()):.4f}")
    # age 60+ as the whole decision
    old = age_code >= 9
    tp = int((old & (t == 1)).sum()); fp = int((old & (t == 0)).sum())
    fn = int((~old & (t == 1)).sum())
    prec = tp / max(1, tp + fp)
    print(f"  'everyone 60 and over' rule: flags {old.mean():.1%}  precision {prec:.1%}  "
          f"recall {tp/max(1,tp+fn):.1%}  accuracy {((old == (t==1)).mean()):.1%}")
    print()

    # ---------------------------------------------------------------- 8. age-adjusted
    print("=== 8. does either model add anything on top of age? ===")
    for name, p in (("Jev", jp), ("DeepSeek", lp)):
        resid_auc = []
        for lo, hi in ((1, 5), (6, 8), (9, 11), (12, 13)):
            m = (age_code >= lo) & (age_code <= hi)
            if m.sum() > 40 and 0 < t[m].sum() < m.sum():
                resid_auc.append((f"age {lo}-{hi}", m.sum(), sc.auc(t[m].tolist(), p[m].tolist())))
        bits = "  ".join(f"{lab}: {a:.3f} (n={n})" for lab, n, a in resid_auc)
        print(f"  {name:9s} within narrow age bands -> {bits}")


if __name__ == "__main__":
    main()
