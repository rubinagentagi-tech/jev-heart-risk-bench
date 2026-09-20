#!/usr/bin/env python3
"""
score.py - one scorer for every arm (Jev, logistic regression, chat LLM, majority).

Every arm is reduced to the same normalised row shape so the numbers in the
report, the dashboard and the README cannot drift apart:

    {id, truth, band, band_confidence, p_positive, top_driver,
     modifiable, flag_followup, latency_s, input_tokens, output_tokens}

`truth` is always the recorded CDC answer, never a model output.
"""
import json, math, os, statistics
from collections import Counter

BANDS = ["low", "moderate", "elevated", "high"]
BAND_RANK = {b: i for i, b in enumerate(BANDS)}
POSITIVE_BANDS = {"elevated", "high"}


# ------------------------------------------------------------------ metric helpers
def auc(y, p):
    """Rank-based AUC with tie handling (Mann-Whitney U)."""
    pairs = sorted(zip(p, y))
    n_pos = sum(y); n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2.0          # 1-based average rank for the tie group
        for k in range(i, j):
            if pairs[k][1] == 1:
                rank_sum += avg_rank
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def _pct(sorted_probs_rows, q):
    """Percentile of the stated probability across rows, for spread comparison."""
    v = sorted(r["p_positive"] for r in sorted_probs_rows)
    if not v:
        return 0.0
    return v[min(len(v) - 1, int(q * len(v)))]


def band_from_prob(p):
    """Map a probability onto the four bands. The cut-offs are a POLICY decision and live
    in code, never in the model's instructions - that is the point of asking for a number."""
    if p < 0.05:
        return "low"
    if p < 0.12:
        return "moderate"
    if p < 0.25:
        return "elevated"
    return "high"


def threshold_sweep(rows, thresholds=None):
    """The table a deployer actually needs: what each cut-off buys and costs."""
    thresholds = thresholds or [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70]
    base = sum(r["truth"] for r in rows) / len(rows)
    out = []
    for t in thresholds:
        sel = [r for r in rows if (r.get("p_positive") or 0) >= t]
        tp = sum(1 for r in sel if r["truth"])
        fn = sum(1 for r in rows if (r.get("p_positive") or 0) < t and r["truth"])
        prec, rec, f1 = prf(tp, len(sel) - tp, fn)
        out.append({"threshold": t, "flagged": len(sel), "coverage": round(len(sel) / len(rows), 4),
                    "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
                    "lift": round(prec / base, 3) if base else None})
    return out


def prf(tp, fp, fn):
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return prec, rec, f1


def band_table(rows, key="band_confidence"):
    bands = [(0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 0.95), (0.95, 1.01)]
    out = []
    for lo, hi in bands:
        sel = [r for r in rows if r.get(key) is not None and lo <= r[key] < hi]
        if sel:
            out.append({"band": f"{lo:.2f}-{hi:.2f}", "n": len(sel),
                        "accuracy": sum(r["_correct"] for r in sel) / len(sel),
                        "actual_positive_rate": sum(r["truth"] for r in sel) / len(sel)})
    return out


def auto_accept(rows, thresholds=(0.5, 0.7, 0.85, 0.95), key="band_confidence"):
    out = []
    for t in thresholds:
        sel = [r for r in rows if r.get(key) is not None and r[key] >= t]
        if sel:
            out.append({"threshold": t, "n": len(sel), "coverage": len(sel) / len(rows),
                        "error_rate": 1 - sum(r["_correct"] for r in sel) / len(sel)})
        else:
            out.append({"threshold": t, "n": 0, "coverage": 0.0, "error_rate": None})
    return out


def calibration(rows, bins=None):
    """Jev's own probability that the person is positive vs how often they are."""
    sel = [r for r in rows if r.get("p_positive") is not None]
    if not sel:
        return []
    if bins is None:
        bins = [0.0, 0.10, 0.20, 0.30, 0.45, 0.60, 0.80, 1.0001]
    out = []
    for lo, hi in zip(bins, bins[1:]):
        s = [r for r in sel if lo <= r["p_positive"] < hi]
        if s:
            out.append({"lo": lo, "hi": min(hi, 1.0), "n": len(s),
                        "predicted": sum(r["p_positive"] for r in s) / len(s),
                        "actual": sum(r["truth"] for r in s) / len(s)})
    return out


# ------------------------------------------------------------------ main scorecard
def scorecard(rows, name, meta=None, conf_key="band_confidence"):
    rows = [dict(r) for r in rows]
    for r in rows:
        r["_correct"] = bool((r["band"] in POSITIVE_BANDS) == bool(r["truth"]))
    n = len(rows)
    pos = sum(r["truth"] for r in rows)
    base = pos / n

    tp = sum(1 for r in rows if r["band"] in POSITIVE_BANDS and r["truth"])
    fp = sum(1 for r in rows if r["band"] in POSITIVE_BANDS and not r["truth"])
    fn = sum(1 for r in rows if r["band"] not in POSITIVE_BANDS and r["truth"])
    tn = n - tp - fp - fn
    prec, rec, f1 = prf(tp, fp, fn)

    ranked = [r for r in rows if r.get("p_positive") is not None]
    cards = {
        "name": name,
        "cases": n,
        "positives": pos,
        "base_rate": round(base, 4),
        "accuracy": round(sum(r["_correct"] for r in rows) / n, 4),
        "majority_baseline": round(max(base, 1 - base), 4),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "lift": round(prec / base, 3) if base else None,
        "auc": round(auc([r["truth"] for r in ranked],
                         [r["p_positive"] for r in ranked]), 4) if ranked else None,
        "confidence_bands": band_table(rows, key=conf_key),
        "auto_accept": auto_accept(rows, key=conf_key),
        "confidence_key": conf_key,
        "calibration": calibration(rows),
        "threshold_sweep": threshold_sweep(ranked) if ranked else [],
        "prob_p05": round(_pct(ranked, 0.05), 3) if ranked else None,
        "prob_p50": round(_pct(ranked, 0.50), 3) if ranked else None,
        "prob_p95": round(_pct(ranked, 0.95), 3) if ranked else None,
        "prob_mean": round(sum(r["p_positive"] for r in ranked) / len(ranked), 4) if ranked else None,
        "frac_stated_above_0.5": round(sum(1 for r in ranked if r["p_positive"] > 0.5) / len(ranked), 4)
                                 if ranked else None,
        "latency_mean_s": round(statistics.mean([r["latency_s"] for r in rows]), 4)
                          if any(r.get("latency_s") for r in rows) else None,
        "input_tokens": sum(r.get("input_tokens") or 0 for r in rows),
        "output_tokens": sum(r.get("output_tokens") or 0 for r in rows),
    }
    if cards["latency_mean_s"]:
        lat = sorted(r["latency_s"] for r in rows if r.get("latency_s"))
        cards["latency_p50_s"] = round(lat[len(lat) // 2], 4)
        cards["latency_p95_s"] = round(lat[int(0.95 * len(lat)) - 1], 4)

    # ---- secondary questions, only present in the Jev arm
    drv = [r for r in rows if r.get("top_driver")]
    named = [r for r in drv if r["top_driver"] != "none_clear"]
    if named:
        valid = [r for r in named if (r.get("driver_truth") or {}).get(r["top_driver"]) is True]
        cards["driver"] = {
            "answered": len(drv), "named_a_factor": len(named),
            "none_clear_rate": round(1 - len(named) / len(drv), 4),
            "driver_present_accuracy": round(len(valid) / len(named), 4),
            "distribution": dict(Counter(r["top_driver"] for r in drv).most_common()),
        }
    mod = [r for r in rows if r.get("modifiable") is not None and r.get("modifiable_truth") is not None]
    if mod:
        m_tp = sum(1 for r in mod if r["modifiable"] and r["modifiable_truth"])
        m_fp = sum(1 for r in mod if r["modifiable"] and not r["modifiable_truth"])
        m_fn = sum(1 for r in mod if not r["modifiable"] and r["modifiable_truth"])
        mp, mr, _ = prf(m_tp, m_fp, m_fn)
        cards["modifiable"] = {
            "cases": len(mod), "base_rate": round(sum(r["modifiable_truth"] for r in mod) / len(mod), 4),
            "accuracy": round(sum(1 for r in mod if bool(r["modifiable"]) == bool(r["modifiable_truth"])) / len(mod), 4),
            "precision": round(mp, 4), "recall": round(mr, 4),
            "lift": round(mp / (sum(r["modifiable_truth"] for r in mod) / len(mod)), 3),
        }
    flg = [r for r in rows if r.get("flag_followup") is not None]
    if flg:
        for t in (0.5, 0.7, 0.85):
            sel = [r for r in flg if r["flag_followup"] >= t]
            f_tp = sum(1 for r in sel if r["truth"])
            f_fp = len(sel) - f_tp
            f_fn = sum(1 for r in flg if r["flag_followup"] < t and r["truth"])
            p_, r_, f_ = prf(f_tp, f_fp, f_fn)
            cards.setdefault("flag_followup", {})[f"thr_{t}"] = {
                "flagged": len(sel), "coverage": round(len(sel) / len(flg), 4),
                "precision": round(p_, 4), "recall": round(r_, 4), "f1": round(f_, 4),
                "lift": round(p_ / cards["base_rate"], 3),
            }
    if meta:
        cards.update(meta)
    return cards


def report_md(cards):
    c = cards
    L = [f"# {c['name']}", ""]
    if c.get("model"):
        L.append(f"Model `{c['model']}` · {c['cases']:,} cases")
    else:
        L.append(f"{c['cases']:,} cases")
    L += ["",
          f"- base rate in this sample: **{c['base_rate']:.1%}** "
          f"({c['positives']:,} of {c['cases']:,} really had heart disease)",
          f"- majority-class baseline: {c['majority_baseline']:.1%}",
          f"- accuracy: **{c['accuracy']:.1%}**",
          f"- precision {c['precision']:.1%} · recall {c['recall']:.1%} · F1 {c['f1']:.3f} "
          f"· lift {c['lift']}x",
          f"- AUC (ranking, threshold-free): {c['auc'] if c['auc'] is not None else 'n/a'}",
          f"- confusion: TP {c['confusion']['tp']} · FP {c['confusion']['fp']} · "
          f"FN {c['confusion']['fn']} · TN {c['confusion']['tn']}", ""]
    if c.get("confidence_bands"):
        L += ["## Confidence band vs accuracy", "", "| band | cases | accuracy | actual positive rate |", "|---|---|---|---|"]
        for b in c["confidence_bands"]:
            L.append(f"| {b['band']} | {b['n']} | {b['accuracy']:.1%} | {b['actual_positive_rate']:.1%} |")
        L.append("")
    if c.get("auto_accept"):
        L += ["## Auto-accept coverage vs error", "", "| confidence >= | kept | coverage | error rate |", "|---|---|---|---|"]
        for a in c["auto_accept"]:
            er = "n/a" if a["error_rate"] is None else f"{a['error_rate']:.2%}"
            L.append(f"| {a['threshold']} | {a['n']} | {a['coverage']:.1%} | {er} |")
        L.append("")
    if c.get("calibration"):
        L += ["## Calibration: stated probability vs reality", "",
              "| stated | cases | mean stated | actual positive rate |", "|---|---|---|---|"]
        for b in c["calibration"]:
            L.append(f"| {b['lo']:.2f}-{b['hi']:.2f} | {b['n']} | {b['predicted']:.1%} | {b['actual']:.1%} |")
        L.append("")
    if c.get("threshold_sweep"):
        L += ["## Choosing the cut-off in code (stated probability >= threshold)", "",
              "| threshold | flagged | share of rows | precision | recall | F1 | lift |",
              "|---|---|---|---|---|---|---|"]
        for s in c["threshold_sweep"]:
            L.append(f"| {s['threshold']:.2f} | {s['flagged']:,} | {s['coverage']:.1%} | "
                     f"{s['precision']:.1%} | {s['recall']:.1%} | {s['f1']:.3f} | {s['lift']}x |")
        L.append("")
    if c.get("driver"):
        d = c["driver"]
        L += ["## Stated reason (explainability check)", "",
              f"- a named factor: {d['named_a_factor']:,} of {d['answered']:,} "
              f"(none_clear {d['none_clear_rate']:.1%})",
              f"- the named factor is actually present in the data: **{d['driver_present_accuracy']:.1%}**",
              "", "| factor named | count |", "|---|---|"]
        for k, v in d["distribution"].items():
            L.append(f"| {k} | {v} |")
        L.append("")
    if c.get("modifiable"):
        m = c["modifiable"]
        L += ["## Modifiable risk factor present", "",
              f"- accuracy {m['accuracy']:.1%} · precision {m['precision']:.1%} · "
              f"recall {m['recall']:.1%} · lift {m['lift']}x (base rate {m['base_rate']:.1%})", ""]
    if c.get("flag_followup"):
        L += ["## Flag for follow-up", "", "| threshold | flagged | coverage | precision | recall | lift |", "|---|---|---|---|---|---|"]
        for t, v in c["flag_followup"].items():
            L.append(f"| {t.replace('thr_', '')} | {v['flagged']} | {v['coverage']:.1%} | "
                     f"{v['precision']:.1%} | {v['recall']:.1%} | {v['lift']}x |")
        L.append("")
    if c.get("latency_mean_s"):
        L += ["## Cost and speed", "",
              f"- latency mean {c['latency_mean_s']}s · p50 {c.get('latency_p50_s')}s · p95 {c.get('latency_p95_s')}s",
              f"- input tokens {c['input_tokens']:,} · output tokens {c['output_tokens']:,}"]
        if c.get("cost_usd") is not None:
            L.append(f"- cost ${c['cost_usd']:.4f} total · ${c['cost_usd']/c['cases']*1000:.4f} per 1,000 cases")
        if c.get("proxy_estimate"):
            L.append(f"- {c['proxy_estimate']}")
        L.append("")
    return "\n".join(L)
