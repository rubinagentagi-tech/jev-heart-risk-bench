#!/usr/bin/env python3
"""
diagnose.py - before reporting a model failure, check the request itself.

Two probes:
  1. EXTREMES: two hand-built respondents who could not be more different. If the
     model returns the same band for both, the failure is in the plumbing.
  2. DISTRIBUTION: how the 5,000 answers spread across the four bands, against what
     the criteria imply they should be.
"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import jev_client as jc  # noqa: E402
from pack_builder import questions  # noqa: E402

PRISTINE = """US adult health survey respondent.
Age band: 25-29
Sex: female
Body mass index: 21.4
Self-rated general health: excellent
Days of poor physical health in the past 30 days: 0
Days of poor mental health in the past 30 days: 0
Told by a doctor they have high blood pressure: no
Told by a doctor their blood cholesterol is high: no
Blood cholesterol checked in the last 5 years: yes
Ever told they have diabetes: no
Ever told they had a stroke: no
Smoked at least 100 cigarettes in their life: no
Any physical activity or exercise in the past month: yes
Eats fruit at least once a day: yes
Eats vegetables at least once a day: yes
Heavy alcohol use: no
Has any health care coverage: yes
Needed a doctor in the past 12 months but could not afford it: no
Serious difficulty walking or climbing stairs: no
Education: college 4 years or more
Annual household income: $75,000 or more
"""

WRECKED = """US adult health survey respondent.
Age band: 80+
Sex: male
Body mass index: 38.9
Self-rated general health: poor
Days of poor physical health in the past 30 days: 30
Days of poor mental health in the past 30 days: 30
Told by a doctor they have high blood pressure: yes
Told by a doctor their blood cholesterol is high: yes
Blood cholesterol checked in the last 5 years: yes
Ever told they have diabetes: yes
Ever told they had a stroke: yes
Smoked at least 100 cigarettes in their life: yes
Any physical activity or exercise in the past month: no
Eats fruit at least once a day: no
Eats vegetables at least once a day: no
Heavy alcohol use: yes
Has any health care coverage: yes
Needed a doctor in the past 12 months but could not afford it: yes
Serious difficulty walking or climbing stairs: yes
Education: grades 9-11 (some high school)
Annual household income: under $10,000
"""

MIDDLE = """US adult health survey respondent.
Age band: 50-54
Sex: male
Body mass index: 27.1
Self-rated general health: good
Days of poor physical health in the past 30 days: 2
Days of poor mental health in the past 30 days: 0
Told by a doctor they have high blood pressure: yes
Told by a doctor their blood cholesterol is high: no
Blood cholesterol checked in the last 5 years: yes
Ever told they have diabetes: no
Ever told they had a stroke: no
Smoked at least 100 cigarettes in their life: yes
Any physical activity or exercise in the past month: yes
Eats fruit at least once a day: no
Eats vegetables at least once a day: yes
Heavy alcohol use: no
Has any health care coverage: yes
Needed a doctor in the past 12 months but could not afford it: no
Serious difficulty walking or climbing stairs: no
Education: grade 12 or GED (high school graduate)
Annual household income: $50,000-$75,000
"""


def show(tag, state, qs, client):
    r = client.ask(state, qs)
    if not r.get("ok"):
        print(f"{tag}: FAILED {r.get('error')}")
        return
    b = r["answers"].get("risk_band", {})
    probs = b.get("probabilities") or {}
    p_pos = sum(v for k, v in probs.items() if k in ("elevated", "high"))
    print(f"{tag:10s} band={b.get('choice'):9s} confidence={b.get('confidence')} "
          f"P(heart disease)={p_pos:.2f}  driver={(r['answers'].get('top_driver') or {}).get('choice')}")
    print(f"           probabilities={ {k: round(v,3) for k,v in sorted(probs.items())} }")


def main():
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        p = os.path.expanduser("~/.typesafe_key")
        if os.path.exists(p):
            key = open(p).read().strip()
    if not key:
        sys.exit("set TYPESAFE_API_KEY (any file, any secret store, your choice)")
    client = jc.JevClient(key)
    qs = questions()
    print("=== probe 1: three respondents engineered to span the range ===")
    for tag, st in (("PRISTINE", PRISTINE), ("MIDDLE", MIDDLE), ("WRECKED", WRECKED)):
        show(tag, st, qs, client)
    for i in range(3):
        show(f"WRECKED-{i+2}", WRECKED, qs, client)
    print()
    print("=== probe 2: band distribution over the scored 5,000 ===")
    res = json.load(open(os.path.join(HERE, "results", "jev", "results.json")))
    from collections import Counter
    c = Counter(r["band"] for r in res["rows"])
    n = len(res["rows"])
    for b in ("low", "moderate", "elevated", "high"):
        print(f"  {b:9s} {c[b]:5,}  {c[b]/n:6.1%}")
    flagged = (c['elevated'] + c['high']) / n
    print(f"  flagged positive: {flagged:.1%}  (base rate {res['scorecard']['base_rate']:.1%})")
    print()
    print("=== probe 3: are the answers actually discriminative? ===")
    rows = res["rows"]
    pos = [r for r in rows if r["truth"] == 1]
    neg = [r for r in rows if r["truth"] == 0]
    for lab, grp in (("真 positives", pos), ("negatives", neg)):
        import statistics as st
        print(f"  {lab:12s} n={len(grp):5,}  mean P(heart disease)="
              f"{st.mean([r['p_positive'] or 0 for r in grp]):.3f}  "
              f"mean risk factors={st.mean([r['risk_factor_count'] for r in grp]):.2f}  "
              f"mean confidence={st.mean([r['band_confidence'] or 0 for r in grp]):.3f}")


if __name__ == "__main__":
    main()
