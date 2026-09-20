#!/usr/bin/env python3
"""
verify_lattice.py - prove the browser and Python agree on the lattice mapping.

Two things can silently break the app and neither is visible on the page:
  * the mixed-radix cell index drifting out of step with itertools.product order, which
    would show one profile's answer for another profile
  * the truth keys not matching what make_grid.py wrote, which would silently drop the
    "what actually happened" panel for every profile

This builds every one of the 29,952 combinations as LEVEL INDICES, computes the index and
the truth key in Python, then recomputes both with the exact function text used in the app
and compares all of them. It also asserts that every key in grid-truth.json is reachable.

    python verify_lattice.py
"""
import itertools, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_app import DIMS  # noqa: E402

NODE = os.environ.get("NODE_BIN") or shutil.which("node") or "node"
JS = """
const fs = require('fs');
const DIMS = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function cellIndex(s){
  let i = 0;
  for(let d=0; d<DIMS.length; d++) i = i*DIMS[d].length + s[d];
  return i;
}
function keyFor(s){ return DIMS.map((dim,d)=>String(dim[s[d]])).join("|"); }
function wideFor(s){ return [DIMS[0][s[0]], DIMS[3][s[3]], DIMS[4][s[4]], DIMS[9][s[9]]].join("|"); }
const all = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const idx = [], keys = [], wide = [];
for(const s of all){ idx.push(cellIndex(s)); keys.push(keyFor(s)); wide.push(wideFor(s)); }
process.stdout.write(JSON.stringify({idx: idx, keys: keys, wide: wide}));
"""


def main():
    # every combination as LEVEL INDICES, in itertools.product order
    combos = [list(c) for c in itertools.product(*[range(len(d)) for d in DIMS])]
    print(f"combinations: {len(combos):,}")

    # Python's own expectations
    py_idx = list(range(len(combos)))          # product order IS the index by construction
    py_keys = ["|".join(str(DIMS[d][s[d]]) for d in range(len(DIMS))) for s in combos]
    py_wide = ["|".join(str(DIMS[d][s[d]]) for d in (0, 3, 4, 9)) for s in combos]

    node = NODE if os.path.exists(NODE) else "node"
    js_file = os.path.join(HERE, ".verify-lattice.js")
    dims_file = os.path.join(HERE, ".verify-dims.json")
    combos_file = os.path.join(HERE, ".verify-combos.json")
    open(js_file, "w").write(JS)
    json.dump(DIMS, open(dims_file, "w"))
    json.dump(combos, open(combos_file, "w"))
    r = subprocess.run([node, js_file, dims_file, combos_file],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        sys.exit("node failed: " + r.stderr[-500:])
    got = json.loads(r.stdout)
    for f in (js_file, dims_file, combos_file):
        os.remove(f)

    fail = 0
    bad_idx = [(c, p, j) for c, p, j in zip(combos, py_idx, got["idx"]) if p != j]
    print(f"cell index mismatches   : {len(bad_idx):,}")
    fail += len(bad_idx)
    for c, p, j in bad_idx[:5]:
        print(f"   {c}: python {p} vs js {j}")

    bad_key = [(c, p, j) for c, p, j in zip(combos, py_keys, got["keys"]) if p != j]
    print(f"truth key mismatches    : {len(bad_key):,}")
    fail += len(bad_key)
    for c, p, j in bad_key[:5]:
        print(f"   {c}: python {p!r} vs js {j!r}")

    bad_wide = [(c, p, j) for c, p, j in zip(combos, py_wide, got["wide"]) if p != j]
    print(f"wide key mismatches     : {len(bad_wide):,}")
    fail += len(bad_wide)

    # every key the truth file carries must be reachable from the lattice
    truth = json.load(open(os.path.join(HERE, "grid-truth.json")))
    reachable = set(py_keys)
    reachable_wide = set(py_wide)
    orphan = [k for k in truth["exact"] if k not in reachable]
    orphan_w = [k for k in truth["wide"] if k not in reachable_wide]
    print(f"exact keys in the file  : {len(truth['exact']):,}   unreachable: {len(orphan):,}")
    print(f"wide keys in the file   : {len(truth['wide']):,}   unreachable: {len(orphan_w):,}")
    fail += len(orphan) + len(orphan_w)
    for k in orphan[:5]:
        print(f"   unreachable exact key: {k!r}")

    print(f"app computes            : {len(got['idx']):,} cells where make_grid wrote "
          f"{json.load(open(os.path.join(HERE, 'results', 'grid', 'grid.json')))['n']:,}")
    if len(got["idx"]) != 29952:
        fail += 1

    if fail:
        print(f"\nFAILED with {fail} problems")
        sys.exit(1)
    print("\nall checks passed: the app and the lattice agree on every combination")


if __name__ == "__main__":
    main()
