#!/usr/bin/env python3
"""rescore.py - re-score an arm's saved rows without re-calling the API.

Scoring changes far more often than the calls do, and re-running 5,000 paid calls to
change a table would be silly. Reads results/<arm>/results.json, rebuilds the scorecard,
rewrites results.json + report.md.

    python rescore.py results/llm results/jev results/ab-v1
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as sc  # noqa: E402

KEYS = {"llm": "p_positive", "jev": "band_confidence", "ab-v1": "band_confidence",
        "ab-v2": "band_confidence", "grid": None}


def main():
    for arm in sys.argv[1:]:
        path = os.path.join(HERE, arm if os.path.isabs(arm) else arm, "results.json")
        if not os.path.exists(path):
            print(f"skip {path} (missing)")
            continue
        d = json.load(open(path))
        rows, old = d["rows"], d["scorecard"]
        name = old["name"]
        meta = {k: old[k] for k in ("model", "workers", "wall_clock_s", "cost_usd",
                                    "transport_errors", "pack", "note", "unparseable_answers",
                                    "unparseable_rate") if k in old}
        ck = KEYS.get(os.path.basename(os.path.dirname(path)), "band_confidence")
        if ck == "p_positive" and not any(r.get("p_positive") is not None for r in rows):
            ck = "band_confidence"
        cards = sc.scorecard([r for r in rows if r.get("band") in sc.BANDS], name, meta, conf_key=ck)
        # the pre-rename model string: keep whatever the API actually reported
        d["scorecard"] = cards
        json.dump(d, open(path, "w"), indent=1)
        open(os.path.join(os.path.dirname(path), "report.md"), "w").write(sc.report_md(cards))
        print(f"rescored {arm}: acc {cards['accuracy']:.3f} auc {cards['auc']} "
              f"conf_key={cards['confidence_key']} prob p50={cards['prob_p50']} "
              f"p95={cards['prob_p95']} frac>0.5={cards['frac_stated_above_0.5']}")


if __name__ == "__main__":
    main()
