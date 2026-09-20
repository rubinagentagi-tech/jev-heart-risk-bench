#!/usr/bin/env python3
"""
run_jev.py - score the CDC cohort with Jev (TypeSafe System One).

Threaded: one JevClient per worker thread, because the client accumulates call and
token counters on the instance and a shared client corrupts the cost accounting.

    python run_jev.py --pack cases.jsonl --out results/jev --limit 12   # smoke test
    python run_jev.py --pack cases.jsonl --out results/jev --workers 10
"""
import argparse, json, os, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))     # jev-poc/ -> jev_client
import jev_client as jc                                        # noqa: E402
import score as sc                                             # noqa: E402

REGISTRY, LOCK = [], threading.Lock()


def worker(cases, out_rows, api_key, base_url, model):
    local = threading.local()
    for c in cases:
        if not hasattr(local, "client"):
            local.client = jc.JevClient(api_key, base_url=base_url, model=model)
            with LOCK:
                REGISTRY.append(local.client)
        r = local.client.ask(c["state_block"], c["questions"])
        if not r.get("ok"):
            out_rows.append({"id": c["id"], "error": r.get("error"), "body": str(r.get("body"))[:200]})
            continue
        a = r["answers"]
        band_res = a.get("risk_band") or {}
        probs = band_res.get("probabilities") or {}
        p_pos = None
        if probs:
            p_pos = sum(v for k, v in probs.items() if k in sc.POSITIVE_BANDS)
        elif (a.get("has_heart_disease") or {}).get("noul") is not None:
            # v3 contract: the noul answer IS the calibrated probability
            p_pos = float(a["has_heart_disease"]["noul"])
        band, conf = band_res.get("choice"), band_res.get("confidence")
        if band is None and p_pos is not None:
            band = sc.band_from_prob(p_pos)
            conf = p_pos if p_pos >= 0.5 else 1 - p_pos
        exp = c["expected"]
        out_rows.append({
            "id": c["id"],
            "truth": exp["heart_disease"],
            "band": band,
            "band_confidence": conf,
            "probabilities": probs,
            "p_positive": round(p_pos, 6) if p_pos is not None else None,
            "top_driver": (a.get("top_driver") or {}).get("choice"),
            "driver_truth": exp["driver_truth"],
            "modifiable": (a.get("modifiable_risk_present") or {}).get("noul"),
            "modifiable_truth": exp["modifiable_risk_present"],
            "flag_followup": (a.get("flag_for_followup") or {}).get("noul"),
            "risk_factor_count": exp["risk_factor_count"],
            "latency_s": r["latency_s"],
            "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"],
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=10)
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
    # record the exact contract being answered, so the two arms can be proven to have
    # been given the same question
    import hashlib
    qs = cases[0]["questions"]
    contract_sha = hashlib.sha256(json.dumps(qs, sort_keys=True).encode()).hexdigest()[:12]
    json.dump(qs, open(os.path.join(a.out, "contract.json"), "w"), indent=1)
    print(f"{len(cases):,} cases · {a.workers} workers · model {a.model} · "
          f"contract sha256:{contract_sha}", flush=True)

    chunks = [cases[i::a.workers] for i in range(a.workers)]
    rows, t0 = [], time.time()
    threads = [threading.Thread(target=worker, args=(ch, rows, a.api_key, a.base_url, a.model))
               for ch in chunks if ch]
    for t in threads:
        t.start()
    done = 0
    while any(t.is_alive() for t in threads):
        time.sleep(5)
        if len(rows) // 100 > done:
            done = len(rows) // 100
            print(f"  [{len(rows):,}/{len(cases):,}] elapsed {time.time()-t0:.0f}s", flush=True)
    for t in threads:
        t.join()
    wall = time.time() - t0

    good = [r for r in rows if "error" not in r]
    bad = [r for r in rows if "error" in r]
    tokens_in = sum(c.tokens_in for c in REGISTRY)
    cost = round(tokens_in / 1e6 * 0.042, 6)
    print(f"done: {len(good):,} scored, {len(bad):,} transport errors, {wall:.0f}s wall, "
          f"{tokens_in:,} input tokens, ${cost:.4f}", flush=True)
    if bad:
        print("first errors:", json.dumps(bad[:3])[:500])

    meta = {"model": a.model, "workers": a.workers, "wall_clock_s": round(wall, 1),
            "cost_usd": cost, "transport_errors": len(bad),
            "pack": os.path.basename(a.pack)}
    cards = sc.scorecard(good, f"Jev ({a.model}) on CDC BRFSS 2015 heart disease", meta)
    json.dump({"scorecard": cards, "rows": good, "errors": bad},
              open(os.path.join(a.out, "results.json"), "w"), indent=1)
    md = sc.report_md(cards)
    open(os.path.join(a.out, "report.md"), "w").write(md)
    print("\n" + md)


if __name__ == "__main__":
    main()
