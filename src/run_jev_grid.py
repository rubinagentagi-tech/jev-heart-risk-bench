#!/usr/bin/env python3
"""
run_jev_grid.py - score every cell of the lattice with Jev, once, up front.

Same threaded client pattern as run_jev.py. There is no answer key here: this arm exists
so the interactive app can show a real Jev answer for every profile a visitor can build,
without shipping an API key to the browser.

    python run_jev_grid.py --pack grid-cases.jsonl --out results/grid --workers 10
"""
import argparse, json, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import jev_client as jc  # noqa: E402
import score as sc       # noqa: E402

REGISTRY, LOCK = [], threading.Lock()
DRIVERS = ["high_blood_pressure", "high_cholesterol", "smoking_history", "diabetes", "obesity",
           "physical_inactivity", "age", "poor_self_rated_health", "prior_stroke", "none_clear"]


def worker(cases, out, key, base_url, model):
    local = threading.local()
    for c in cases:
        if not hasattr(local, "client"):
            local.client = jc.JevClient(key, base_url=base_url, model=model)
            with LOCK:
                REGISTRY.append(local.client)
        r = local.client.ask(c["state_block"], c["questions"])
        if not r.get("ok"):
            out.append({"id": c["id"], "error": r.get("error")})
            continue
        a = r["answers"]
        b = a.get("risk_band") or {}
        probs = b.get("probabilities") or {}
        p_pos = sum(v for k, v in probs.items() if k in sc.POSITIVE_BANDS)
        drv = (a.get("top_driver") or {}).get("choice")
        out.append({
            "id": c["id"],
            "band": b.get("choice"),
            "conf": b.get("confidence"),
            "p": round(p_pos, 4) if probs else None,
            "driver": DRIVERS.index(drv) if drv in DRIVERS else 9,
            "modif": (a.get("modifiable_risk_present") or {}).get("noul"),
            "flag": (a.get("flag_for_followup") or {}).get("noul"),
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--api-key", default=os.environ.get("TYPESAFE_API_KEY"))
    ap.add_argument("--base-url", default=jc.DEFAULT_URL)
    ap.add_argument("--model", default=jc.DEFAULT_MODEL)
    a = ap.parse_args()
    if not a.api_key:
        sys.exit("no TYPESAFE_API_KEY")

    cases = [json.loads(l) for l in open(a.pack) if l.strip()]
    if a.limit:
        cases = cases[:a.limit]
    os.makedirs(a.out, exist_ok=True)
    print(f"{len(cases):,} lattice cells · {a.workers} workers · {a.model}", flush=True)

    chunks = [cases[i::a.workers] for i in range(a.workers)]
    rows, t0 = [], time.time()
    ts = [threading.Thread(target=worker, args=(ch, rows, a.api_key, a.base_url, a.model))
          for ch in chunks if ch]
    for t in ts:
        t.start()
    done = 0
    while any(t.is_alive() for t in ts):
        time.sleep(10)
        if len(rows) // 500 > done:
            done = len(rows) // 500
            print(f"  [{len(rows):,}/{len(cases):,}] elapsed {time.time()-t0:.0f}s", flush=True)
    for t in ts:
        t.join()
    wall = time.time() - t0
    good = [r for r in rows if "error" not in r]
    tin = sum(c.tokens_in for c in REGISTRY)
    cost = round(tin / 1e6 * 0.042, 4)
    print(f"done: {len(good):,} cells, {len(rows)-len(good)} errors, {wall:.0f}s, "
          f"{tin:,} input tokens, ${cost:.4f}", flush=True)

    good.sort(key=lambda r: r["id"])
    from collections import Counter
    dist = Counter(r["band"] for r in good)
    json.dump({"cells": good, "model": a.model, "wall_clock_s": round(wall, 1),
               "input_tokens": tin, "cost_usd": cost, "n": len(good),
               "band_distribution": dict(dist)},
              open(os.path.join(a.out, "grid.json"), "w"), separators=(",", ":"))
    print("band distribution:", {k: f"{v/len(good):.1%}" for k, v in dist.most_common()})
    print(f"wrote {os.path.join(a.out, 'grid.json')}")


if __name__ == "__main__":
    main()
