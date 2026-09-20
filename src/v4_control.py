#!/usr/bin/env python3
"""
v4_control.py - is Jev adding anything in the router, or just re-encoding the number?

In v4 Jev was handed a trained model's probability and asked to route and explain. The tiers
separated risk (1.2% to 35.8%), but the discriminating power might be entirely the number it
was handed. The control: threshold that same number into four bands at the SAME tier
proportions and compare. If naive thresholds separate risk as well as Jev's tiers do, then
Jev contributed the routing label and the reason but no discrimination.

No API calls. Reads results/v4-router/results.json.
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as sc  # noqa: E402


def main():
    d = json.load(open(os.path.join(HERE, "results", "v4-router", "results.json")))
    rows = d["rows"]
    y = np.array([r["truth"] for r in rows], dtype=float)
    lr = np.array([r["lr_p"] for r in rows], dtype=float)
    base = y.mean()
    print(f"n={len(rows):,}  base {base:.4f}")

    # proportions Jev actually used
    prop = {t: np.mean([r["tier"] == t for r in rows]) for t in d["tiers"]}
    print("tier proportions Jev chose:", {k: f"{v:.1%}" for k, v in prop.items()})

    # naive control: band the handed probability at the SAME proportions Jev used, ascending,
    # so band 0 is the lowest-risk 6.7% exactly as Jev's "no_action" is its lowest tier
    asc_order = np.argsort(lr)
    asc = np.full(len(rows), -1, dtype=int)
    pos = 0
    for i, t in enumerate(d["tiers"]):
        n_i = int(round(prop[t] * len(rows)))
        asc[asc_order[pos:pos + n_i]] = i
        pos += n_i
    assert (asc >= 0).all(), f"{int((asc < 0).sum())} rows unassigned"

    print()
    print(f"  {'tier':>17} {'n':>6} {'JEV tier rate':>14} {'naive band rate':>16} {'lift JEV':>9} {'lift naive':>11}")
    for i, t in enumerate(d["tiers"]):
        mj = np.array([r["tier"] == t for r in rows])
        mn = asc == i
        rj = y[mj].mean() if mj.sum() else float("nan")
        rn = y[mn].mean() if mn.sum() else float("nan")
        print(f"  {t:>17} {mj.sum():>6,} {rj:>14.1%} {rn:>16.1%} {rj/base:>8.2f}x {rn/base:>10.2f}x")

    jrank = np.array([d["tiers"].index(r["tier"]) for r in rows], dtype=float)
    a_jev = sc.auc(y.tolist(), jrank.tolist())
    a_naive = sc.auc(y.tolist(), asc.tolist())
    a_lr = sc.auc(y.tolist(), lr.tolist())
    print()
    print(f"  AUC of Jev's tier as a score      : {a_jev:.4f}")
    print(f"  AUC of the naive threshold bands  : {a_naive:.4f}")
    print(f"  AUC of the raw trained number     : {a_lr:.4f}   (upper bound, no judgement added)")
    print()
    lo_j = y[np.array([r['tier'] == 'no_action' for r in rows])].mean()
    hi_j = y[np.array([r['tier'] == 'urgent' for r in rows])].mean()
    lo_n = y[asc == 0].mean(); hi_n = y[asc == 3].mean()
    print(f"  spread Jev lowest to highest tier : {lo_j:.1%} -> {hi_j:.1%}  ({hi_j/lo_j:.1f}x)")
    print(f"  spread naive lowest to highest    : {lo_n:.1%} -> {hi_n:.1%}  ({hi_n/lo_n:.1f}x)")
    print()
    if a_jev >= a_naive - 0.005:
        print("  -> Jev's tiers are at least as informative as naive cuts at the same proportions.")
        print("     It added the action label and the reason, and did not lose discrimination.")
    else:
        print("  -> naive cuts of the handed number separate risk better than Jev's tiers.")
        print("     Jev added the action label and the reason, but its discrimination is the number's.")


if __name__ == "__main__":
    main()
