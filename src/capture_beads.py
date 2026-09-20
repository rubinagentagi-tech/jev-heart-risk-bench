#!/usr/bin/env python3
"""
capture_beads.py - screenshot the bead-field section of the app in each of its three views.

    python capture_beads.py
"""
import base64, json, os, socket, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/usr/sbin/chromium"
VENV_PY = "/tmp/cdp-venv/bin/python"
APP = os.path.join(HERE, "cardio-app.html")

DRIVER = r'''
import base64, json, sys, time, urllib.request
from websockets.sync.client import connect
port, src, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
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
        return "JS_EXCEPTION: " + str(r["exceptionDetails"])[:200]
    return r.get("result", {}).get("value")

call("Page.enable"); call("Runtime.enable")
call("Emulation.setDeviceMetricsOverride", width=1500, height=1180, deviceScaleFactor=1.5, mobile=False)
call("Page.navigate", url="file://" + src)
time.sleep(6)

# scroll so the canvas fills the viewport
js("""(()=>{const c=document.getElementById('c');
  const y=c.getBoundingClientRect().top+window.scrollY-70;
  window.scrollTo(0,y); return y;})()""")
time.sleep(1.2)

for view, name in ((0, "beads-jev-band"), (1, "beads-truth"), (2, "beads-wrong")):
    js("setView(%d)" % view)
    time.sleep(1.4)
    s = call("Page.captureScreenshot", format="png")
    path = outdir + "/" + name + ".png"
    open(path, "wb").write(base64.b64decode(s["data"]))
    print("wrote", path)
print("labels:", js("document.getElementById('legend').innerText"))
'''


def main():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    prof = f"/tmp/chrome-beads-{port}"
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
                             "--no-default-browser-check", "--hide-scrollbars",
                             "--user-data-dir=" + prof,
                             "--remote-debugging-port=%d" % port,
                             "--remote-allow-origins=*", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        drv = f"/tmp/capture-beads-{port}.py"
        open(drv, "w").write(DRIVER)
        r = subprocess.run([VENV_PY, drv, str(port), APP, HERE],
                           capture_output=True, text=True, timeout=300)
        print(r.stdout.strip() or r.stderr[-1500:])
    finally:
        proc.terminate()
        subprocess.run(["rm", "-rf", prof], check=False)


if __name__ == "__main__":
    main()
