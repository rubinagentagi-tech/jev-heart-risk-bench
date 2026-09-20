#!/usr/bin/env python3
"""
run_llm_arm.py - the same decision, asked of a chat LLM, on the same 5,000 respondents.

This arm exists to make the Jev-vs-LLM comparison factual instead of rhetorical.
It gets the identical survey text and the identical choice definitions; the only
difference is that a chat model must return its answer as JSON, and every failure
to do so is counted rather than hidden.

    python run_llm_arm.py --pack cases.jsonl --out results/llm --limit 20
    python run_llm_arm.py --pack cases.jsonl --out results/llm --workers 24
"""
import argparse, json, os, re, sys, threading, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as sc                                  # noqa: E402

# The band and driver definitions are read from the PACK, not from pack_builder, so both
# arms are guaranteed to be answering exactly the same question. Reading them from the
# module instead would silently let the two arms drift onto different contracts.
API = "https://api.deepseek.com/chat/completions"
# List price from api-docs.deepseek.com/quick_start/pricing (checked 2026-09-20):
# deepseek-flash cache-miss input and output, off-peak. Peak hours are 01:00-04:00 and
# 06:00-10:00 UTC Mon-Fri, where every rate doubles. Weekends are always off-peak.
PRICE_IN_OFFPEAK, PRICE_OUT_OFFPEAK = 0.15 / 1e6, 0.60 / 1e6
REGISTRY, LOCK = [], threading.Lock()


def is_peak(now=None):
    from datetime import datetime, timezone
    now = now or datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    return 1 <= now.hour < 4 or 6 <= now.hour < 10


def build_prompt(state, band_criteria, driver_criteria):
    return (
        "You are scoring respondents from a US adult health survey.\n\n"
        + state +
        "\nAnswer the following about THIS respondent. Reply with a single JSON object and "
        "nothing else, no markdown fences, no commentary.\n\n"
        '{\n'
        '  "band": "one of: low, moderate, elevated, high",\n'
        '  "probability": 0.0 to 1.0, your probability that this respondent has ever been told '
        'by a doctor that they had a heart attack or coronary heart disease,\n'
        '  "driver": "the single recorded factor that most raises the risk, one of: '
        + ", ".join(driver_criteria.keys()) + '",\n'
        '  "modifiable": true or false, whether at least one modifiable risk factor is present,\n'
        '  "followup": true or false, whether to flag for a clinical follow-up conversation\n'
        '}\n\n'
        "Band definitions:\n"
        + "\n".join(f"- {k}: {v}" for k, v in band_criteria.items())
        + "\n\nDriver definitions:\n"
        + "\n".join(f"- {k}: {v}" for k, v in driver_criteria.items())
        + "\n\nAbout one in eleven US adults in this survey have been told that. Return only the JSON."
    )


def call(prompt, key, model, timeout=120, attempts=4):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 300,
        "thinking": {"type": "disabled"},      # direct answer, not a reasoning transcript
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(API, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(1, attempts + 1):
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                p = json.loads(r.read().decode())
            usage = p.get("usage") or {}
            return {"ok": True,
                    "text": p["choices"][0]["message"]["content"],
                    "latency_s": round(time.time() - t0, 3),
                    "input_tokens": usage.get("prompt_tokens"),
                    "output_tokens": usage.get("completion_tokens")}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < attempts:
                time.sleep(float(e.headers.get("retry-after") or min(2 ** attempt, 20)))
                continue
            return {"ok": False, "error": f"HTTP {e.code}", "body": e.read()[:200].decode(errors="ignore")}
        except Exception as e:
            if attempt == attempts:
                return {"ok": False, "error": repr(e)}
            time.sleep(min(2 ** attempt, 20))


def parse_json(text):
    """Count real JSON failures instead of quietly repairing them."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?|```$", "", t, flags=re.M).strip()
    try:
        return json.loads(t), None
    except Exception:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            try:
                return json.loads(m.group(0)), "recovered_from_wrapped_text"
            except Exception as e:
                return None, f"unparseable: {e}"
        return None, "no JSON object found"


def worker(cases, out, key, model, band_criteria, driver_criteria):
    local = threading.local()
    for c in cases:
        if not hasattr(local, "n"):
            local.n = 0
        r = call(build_prompt(c["state_block"], band_criteria, driver_criteria), key, model)
        if not r.get("ok"):
            out.append({"id": c["id"], "error": r.get("error"), "body": str(r.get("body"))[:200]})
            continue
        with LOCK:
            REGISTRY.append((r["input_tokens"] or 0, r["output_tokens"] or 0))
        obj, parse_note = parse_json(r["text"])
        exp = c["expected"]
        if obj is None:
            out.append({"id": c["id"], "truth": exp["heart_disease"], "band": None,
                        "band_confidence": None, "p_positive": None,
                        "parse_error": parse_note, "raw": (r["text"] or "")[:200],
                        "latency_s": r["latency_s"]})
            continue
        p = obj.get("probability")
        try:
            p = float(p)
            p = min(max(p, 0.0), 1.0)
        except Exception:
            p = None
        out.append({
            "id": c["id"], "truth": exp["heart_disease"],
            "band": obj.get("band"), "band_confidence": p,
            "p_positive": p, "top_driver": obj.get("driver"),
            "driver_truth": exp["driver_truth"],
            "modifiable": obj.get("modifiable"), "modifiable_truth": exp["modifiable_risk_present"],
            "flag_followup": 1.0 if obj.get("followup") in (True, "true", "True") else 0.0,
            "latency_s": r["latency_s"], "input_tokens": r["input_tokens"],
            "output_tokens": r["output_tokens"], "parse_note": parse_note,
        })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--api-key", default=os.environ.get("DEEPSEEK_API_KEY"))
    a = ap.parse_args()
    if not a.api_key:
        sys.exit("no DEEPSEEK_API_KEY")
    peak = is_peak()
    pin = PRICE_IN_OFFPEAK * (2 if peak else 1)
    pout = PRICE_OUT_OFFPEAK * (2 if peak else 1)
    print(f"DeepSeek rate window at run time: {'PEAK' if peak else 'OFF-PEAK'} "
          f"(using ${pin*1e6:.2f}/Mtok in, ${pout*1e6:.2f}/Mtok out)", flush=True)

    cases = [json.loads(l) for l in open(a.pack) if l.strip()]
    if a.limit:
        cases = cases[:a.limit]
    os.makedirs(a.out, exist_ok=True)
    print(f"{len(cases):,} cases · {a.workers} workers · {a.model}", flush=True)

    chunks = [cases[i::a.workers] for i in range(a.workers)]
    qs = cases[0]["questions"]
    band_criteria = qs["risk_band"]["criteria"]
    driver_criteria = qs["top_driver"]["criteria"]
    # record the contract this run answered, so the report can prove both arms matched
    import hashlib
    contract_sha = hashlib.sha256(json.dumps(qs, sort_keys=True).encode()).hexdigest()[:12]
    json.dump(qs, open(os.path.join(a.out, "contract.json"), "w"), indent=1)
    print(f"contract sha256:{contract_sha} ({len(band_criteria)} bands, "
          f"{len(driver_criteria)} drivers)", flush=True)

    rows, t0 = [], time.time()
    ts = [threading.Thread(target=worker, args=(ch, rows, a.api_key, a.model,
                                                band_criteria, driver_criteria))
          for ch in chunks if ch]
    for t in ts:
        t.start()
    done = 0
    while any(t.is_alive() for t in ts):
        time.sleep(5)
        if len(rows) // 100 > done:
            done = len(rows) // 100
            print(f"  [{len(rows):,}/{len(cases):,}] elapsed {time.time()-t0:.0f}s", flush=True)
    for t in ts:
        t.join()
    wall = time.time() - t0

    good = [r for r in rows if r.get("band") in sc.BANDS]
    noreply = [r for r in rows if "error" in r]
    unparsed = [r for r in rows if r.get("parse_error")]
    tin = sum(x[0] for x in REGISTRY); tout = sum(x[1] for x in REGISTRY)
    cost = round(tin * pin + tout * pout, 4)
    print(f"done: {len(good):,} usable, {len(unparsed):,} unparseable, {len(noreply):,} transport errors, "
          f"{wall:.0f}s, in {tin:,} / out {tout:,} tokens, ${cost:.4f}", flush=True)

    if not good:
        sys.exit("no usable answers from the LLM arm")
    meta = {"model": a.model, "workers": a.workers, "wall_clock_s": round(wall, 1),
            "cost_usd": cost, "transport_errors": len(noreply),
            "unparseable_answers": len(unparsed),
            "unparseable_rate": round(len(unparsed) / max(1, len(rows)), 4),
            "pack": os.path.basename(a.pack),
            "note": f"temperature 0, JSON mode, thinking disabled, {'peak' if peak else 'off-peak'} "
                    f"rate ${pin*1e6:.2f}/Mtok in, ${pout*1e6:.2f}/Mtok out"}
    cards = sc.scorecard(good, f"Chat LLM ({a.model}) on the same {len(good):,} respondents",
                         meta, conf_key="p_positive")
    json.dump({"scorecard": cards, "rows": rows, "errors": noreply},
              open(os.path.join(a.out, "results.json"), "w"), indent=1)
    md = sc.report_md(cards)
    open(os.path.join(a.out, "report.md"), "w").write(md)
    print("\n" + md)


if __name__ == "__main__":
    main()
