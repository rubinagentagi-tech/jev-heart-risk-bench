#!/usr/bin/env python3
"""Minimal client for TypeSafe's System One endpoint. stdlib only.

    POST https://api.typesafe.ai/v1/systemone
    Authorization: Bearer $TYPESAFE_API_KEY
    {"model": "jev-1.13.0", "state": <str|obj|list>, "questions": {...}}

Works unchanged against a gateway that proxies the same shape (override --base-url).
Retries 429/5xx with backoff and honours Retry-After.
"""
import json, os, time, urllib.error, urllib.request

DEFAULT_URL = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-1.13.0"          # pin the version: thresholds are version-specific


def build_questions(task):
    if task == "hierarchy":
        return {"node": {"type": "choice",
                         "instructions": "Which inventory hierarchy node should this part be filed under? "
                                         "Choose 'other' when the description does not clearly belong to any listed node.",
                         "criteria": HIER_CRITERIA}}
    if task == "triage":
        return {
            "intent": {"type": "choice",
                       "instructions": "What is the main purpose of this supplier email?",
                       "criteria": {
                           "quotation": "Offers pricing or a quotation.",
                           "invoice": "An invoice or request for payment.",
                           "order_confirmation": "Confirms or acknowledges a purchase order.",
                           "status_chase": "Chases progress or requests an update.",
                           "technical_query": "Asks a specification, fit or compatibility question.",
                           "shipping_notice": "Reports a shipment, tracking or customs event.",
                           "marketing": "Promotional or newsletter content, not a transaction.",
                           "other": "None of the above (out of office, address change, notice)."}},
            "needs_human": {"type": "noul",
                            "instructions": "Does this email require a human buyer to read and act on it?"},
            "price_change": {"type": "noul",
                             "instructions": "Is the sender proposing or requesting a change to prices or rates?"},
        }
    if task == "quotematch":
        ids = [k for k in ("L-01", "L-02", "L-03", "L-04")]
        crit = {i: f"Candidate line {i} is the exact match for the RFQ line." for i in ids}
        crit["none"] = "No candidate line matches the RFQ line."
        return {
            "match": {"type": "choice",
                      "instructions": "Which candidate quote line matches `rfq_line`? Say 'none' if no candidate "
                                      "matches every attribute (size, material, rating, standard).",
                      "criteria": crit},
            "exact": {"type": "noul",
                      "instructions": "Is the match exact on every stated attribute, with no substitution?"},
        }
    raise ValueError(task)


HIER_CRITERIA = {
    "Pumps & Impellers": "Pumps, impellers, wear rings, seals, casings.",
    "Filters & Strainers": "Filters, strainers, elements, cartridges, coalescers.",
    "Valves": "Gate/globe/butterfly/check valves, actuators, seats.",
    "Bearings & Bushings": "Bearings, bushings, housings, pillow blocks.",
    "Gaskets & Packing": "Gaskets, o-rings, packing, flange sheets.",
    "Electrical & Motors": "Motors, contactors, breakers, terminals, cables, drives.",
    "Navigation & Comms": "Radar, VHF, AIS, GPS, gyro, antennas.",
    "Safety & Lifesaving": "Life rafts, immersion suits, extinguishers, EPIRB, detectors.",
    "Lubricants & Fluids": "Oils, greases, hydraulic fluid, coolants, samples.",
    "Deck & Mooring": "Mooring lines, bollards, windlass parts, chain stoppers, fairleads.",
    "Instrumentation": "Transmitters, meters, sensors, switches, gauges.",
    "Fasteners & Fittings": "Bolts, studs, nipples, elbows, unions, fittings.",
    "other": "Does not clearly belong to any of the above.",
}


class JevClient:
    def __init__(self, api_key, base_url=DEFAULT_URL, model=DEFAULT_MODEL, timeout=60, max_attempts=4):
        if not api_key:
            raise SystemExit("No API key. Set TYPESAFE_API_KEY or pass --api-key.")
        self.api_key, self.base_url, self.model = api_key, base_url, model
        self.timeout, self.max_attempts = timeout, max_attempts
        self.tokens_in = self.tokens_out = self.calls = self.errors = 0

    def ask(self, state, questions):
        body = json.dumps({"model": self.model, "state": state, "questions": questions}).encode()
        req = urllib.request.Request(self.base_url, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        for attempt in range(1, self.max_attempts + 1):
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    payload = json.loads(r.read().decode())
                self.calls += 1
                usage = payload.get("usage") or {}
                self.tokens_in += usage.get("input_tokens", 0)
                self.tokens_out += usage.get("output_tokens", 0)
                return {"ok": True, "answers": payload.get("answers", {}),
                        "model": payload.get("model", self.model),
                        "latency_s": round(time.time() - t0, 3) if "latency_s" not in payload else payload["latency_s"],
                        "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")}
            except urllib.error.HTTPError as e:
                code = e.code
                if code == 429 or 500 <= code < 600:
                    wait = float(e.headers.get("retry-after") or min(2 ** attempt, 30))
                    if attempt == self.max_attempts:
                        self.errors += 1
                        return {"ok": False, "error": f"HTTP {code}", "body": e.read()[:300].decode(errors="ignore")}
                    time.sleep(wait)
                    continue
                self.errors += 1
                return {"ok": False, "error": f"HTTP {code}", "body": e.read()[:300].decode(errors="ignore")}
            except Exception as e:
                if attempt == self.max_attempts:
                    self.errors += 1
                    return {"ok": False, "error": repr(e)}
                time.sleep(min(2 ** attempt, 30))

    def cost_usd(self, per_mtok=0.042):
        return round(self.tokens_in / 1_000_000 * per_mtok, 6)
