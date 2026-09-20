#!/usr/bin/env python3
"""
verify_app.py - drive the built app in headless chromium and prove it works.

Checks that matter, in order of how embarrassing they would be:
  1. no uncaught JavaScript error on load
  2. the verdict panel actually rendered (not the "no lattice answer" fallback)
  3. the two extreme profiles land in different bands, so the lookup responds to the sliders
  4. the population panel resolves a real match with a real count
  5. the guessing game populated
  6. the bead canvas actually painted (not a blank rectangle)

Saves a screenshot of the top of the page.

    python verify_app.py
"""
import base64, json, os, socket, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/usr/sbin/chromium"
VENV_PY = "/tmp/cdp-venv/bin/python"
APP = os.environ.get("APP_TARGET", os.path.join(HERE, "cardio-app.html"))
SHOT = os.environ.get("APP_SHOT", os.path.join(HERE, "app-preview.png"))

DRIVER = r'''
import base64, json, sys, time, urllib.request
from websockets.sync.client import connect
port, src, shot = sys.argv[1], sys.argv[2], sys.argv[3]
http = "http://127.0.0.1:%s" % port
for _ in range(40):
    try:
        targets = json.load(urllib.request.urlopen(http + "/json/list", timeout=3)); break
    except Exception:
        time.sleep(0.5)
else:
    sys.exit("chrome never came up")
tgt = next(t for t in targets if t.get("type") == "page")
ws = connect(tgt["webSocketDebuggerUrl"], max_size=256*1024*1024, open_timeout=30, legacy=True)
_i = 0
def call(m, **p):
    global _i
    _i += 1
    ws.send(json.dumps({"id": _i, "method": m, "params": p}))
    while True:
        r = json.loads(ws.recv(timeout=120))
        if r.get("id") == _i:
            if "error" in r:
                raise RuntimeError("%s: %s" % (m, r["error"]))
            return r.get("result", {})
def js(e):
    r = call("Runtime.evaluate", expression=e, returnByValue=True)
    if r.get("exceptionDetails"):
        ex = r["exceptionDetails"]
        return "JS_EXCEPTION: " + str(ex.get("exception", {}).get("description") or ex.get("text"))[:300]
    return r.get("result", {}).get("value")
call("Page.enable"); call("Runtime.enable")
call("Emulation.setDeviceMetricsOverride", width=1440, height=1200, deviceScaleFactor=1.2, mobile=False)
# catch any error thrown from the first moment the page runs
call("Page.addScriptToEvaluateOnNewDocument",
     source="window.__errs=[];window.addEventListener('error',e=>window.__errs.push(String(e.message)));"
            "window.addEventListener('unhandledrejection',e=>window.__errs.push('rejection: '+String(e.reason)));")
call("Page.navigate", url=(src if src.startswith("http") else "file://" + src))
time.sleep(6)

out = {}
out["errors"] = js("window.__errs || 'handler missing'")
out["verdict_len"] = js("(document.getElementById('verdict')||{}).innerHTML?.length || 0")
out["verdict_head"] = js("(document.getElementById('verdict').innerText||'').slice(0,180)")
out["probe_cellindex"] = js("typeof cellIndex")
out["probe_sel"] = js("JSON.stringify(sel)")
out["probe_key"] = js("keyFor(sel)")
out["probe_lookup"] = js("JSON.stringify(lookup(sel)).slice(0,300)")
out["probe_truthkeys"] = js("Object.keys(TRUTH_EXACT).slice(0,3).join(' ~ ')")
out["probe_widekeys"] = js("Object.keys(TRUTH_WIDE).slice(0,3).join(' ~ ')")

def profile(name, expr):
    js(expr)
    return {"name": name,
            "verdict": js("(document.getElementById('verdict').innerText||'').slice(0,170)"),
            "band": js("BAND_NAMES[GRID[cellIndex(sel)][0]]"),
            "p": js("GRID[cellIndex(sel)][2]"),
            "truth_rows": js("(()=>{const t=document.getElementById('verdict').innerText||'';"
                             "const m=t.match(/Outcome among the ([\\d,]+) real/);return m?m[1]:null;})()"),
            "gap_line": js("(()=>{const t=document.getElementById('verdict').innerText||'';"
                           "const m=t.match(/Jev said [^.]*\\./);return m?m[0]:null;})()")}

young = profile("young + clean", "sel=[0,1,0,0,0,0,0,1,0,0,0]; render();")
old = profile("80+ + everything", "sel=[12,0,2,1,1,1,1,0,2,1,1]; render();")
mid = profile("55-59 + some factors", "sel=[7,0,1,1,0,0,0,1,1,0,0]; render();")
out["profiles"] = [young, mid, old]

out["quiz_cells"] = js("document.querySelectorAll('#qgrid span').length")
out["score_panel"] = js("(document.getElementById('score').innerText||'')")
out["canvas_nonblank"] = js("""(()=>{const c=document.getElementById('c');
  const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
  let lit=0; for(let i=0;i<d.length;i+=4*97){ if(d[i]+d[i+1]+d[i+2] > 90) lit++; }
  return lit;})()""")
out["embedded"] = {"grid": js("GRID.length"), "beads": js("BEADS.length"),
                   "truth_keys": js("Object.keys(TRUTH_EXACT).length"),
                   "wide_keys": js("Object.keys(TRUTH_WIDE).length"),
                   "quiz": js("QUIZ.length")}
out["em_dashes"] = js("(document.body.innerText.match(/\\u2014/g)||[]).length")

call("Emulation.setDeviceMetricsOverride", width=1440, height=1500, deviceScaleFactor=1.2, mobile=False)
time.sleep(1.0)
s = call("Page.captureScreenshot", format="png")
open(shot, "wb").write(base64.b64decode(s["data"]))
print("VERIFY_JSON=" + json.dumps(out))
'''


def main():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    prof = f"/tmp/chrome-verify-{port}"
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                             "--no-default-browser-check", "--hide-scrollbars",
                             "--user-data-dir=" + prof,
                             "--remote-debugging-port=%d" % port,
                             "--remote-allow-origins=*", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        drv = f"/tmp/verify-app-{port}.py"
        open(drv, "w").write(DRIVER)
        r = subprocess.run([VENV_PY, drv, str(port), APP, SHOT],
                           capture_output=True, text=True, timeout=300)
        line = [l for l in r.stdout.splitlines() if l.startswith("VERIFY_JSON=")]
        if not line:
            print(r.stdout[-2000:]); print(r.stderr[-2000:]); sys.exit("driver produced nothing")
        d = json.loads(line[0][len("VERIFY_JSON="):])
    finally:
        proc.terminate()
        subprocess.run(["rm", "-rf", prof], check=False)

    print(f"js errors on load      : {d['errors']}")
    print(f"cellIndex              : {d['probe_cellindex']}")
    print(f"default sel            : {d['probe_sel']}")
    print(f"key built in the page  : {d['probe_key']}")
    print(f"lookup result          : {d['probe_lookup']}")
    print(f"first truth keys       : {d['probe_truthkeys']}")
    print(f"first wide keys        : {d['probe_widekeys']}")
    print(f"embedded               : {d['embedded']}")
    print(f"quiz grid populated    : {d['quiz_cells']} fields")
    print(f"canvas lit samples     : {d['canvas_nonblank']}")
    print(f"em dashes in body text : {d['em_dashes']}")
    print(f"score panel            : {d['score_panel'][:90]!r}")
    print()
    for p in d["profiles"]:
        print(f"  {p['name']:24s} band={p['band']:9s} p={p['p']:>5}  matched_rows={p['truth_rows']}")
        print(f"    {p['verdict'][:150]!r}")
    print()

    fail = []
    if d["errors"]:
        fail.append(f"JS errors: {d['errors']}")
    if not d["verdict_len"]:
        fail.append("verdict panel empty")
    if d["embedded"]["grid"] != 29952:
        fail.append(f"grid length {d['embedded']['grid']} != 29952")
    if d["embedded"]["beads"] < 4900:
        fail.append(f"beads {d['embedded']['beads']}")
    if not d["embedded"]["truth_keys"]:
        fail.append("no truth keys")
    if d["quiz_cells"] < 10:
        fail.append(f"quiz grid only {d['quiz_cells']} fields")
    if d["canvas_nonblank"] < 200:
        fail.append(f"canvas looks blank ({d['canvas_nonblank']} lit samples)")
    bands = {p["name"]: p["band"] for p in d["profiles"]}
    if bands.get("young + clean") == bands.get("80+ + everything"):
        fail.append(f"sliders do not change the verdict, all bands {bands}")
    if not all(p["truth_rows"] for p in d["profiles"]):
        fail.append("truth match did not resolve for every profile")
    if d["em_dashes"]:
        fail.append(f"{d['em_dashes']} em dashes in the rendered text")

    print(f"screenshot: {SHOT} ({os.path.getsize(SHOT)/1024:.0f} KB)")
    if fail:
        print("\nFAILED:")
        for f in fail:
            print("  -", f)
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
