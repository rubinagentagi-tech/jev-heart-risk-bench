#!/usr/bin/env python3
"""Probe the CDC BRFSS 2015 XPORT file: confirm it parses and list the variables we need."""
import pandas as pd, os, sys, time

PATH = os.environ.get("BRFSS_XPT", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "data", "LLCP2015.XPT"))

NEED = ["_MICHD", "_RFHYPE5", "_RFCHOL", "CHOLCHK", "_BMI5", "SMOKE100", "CVDSTRK3",
        "DIABETE3", "EXERANY2", "_FRTLT1", "_VEGLT1", "_RFDRHV5", "HLTHPLN1", "MEDCOST",
        "GENHLTH", "MENTHLTH", "PHYSHLTH", "DIFFWALK", "SEX", "_AGEG5YR", "EDUCA",
        "INCOME2", "_STATE", "_PSU", "_STSTR", "X_AGEG5YR", "BPHIGH4", "TOLDHI2"]

t0 = time.time()
it = pd.read_sas(PATH, format="xport", chunksize=3000)
chunk = next(it)
print(f"parsed first chunk in {time.time()-t0:.1f}s  shape={chunk.shape}")
cols = list(chunk.columns)
print(f"total columns: {len(cols)}")
print("first 25 cols:", cols[:25])
print()
present = [c for c in NEED if c in cols]
missing = [c for c in NEED if c not in cols]
print(f"NEEDED present ({len(present)}):", present)
print(f"NEEDED missing ({len(missing)}):", missing)
print()
print(chunk[present].head(5).to_string())
print()
print("dtypes:", dict(chunk[present].dtypes.astype(str)))
