#!/usr/bin/env python3
"""Verify every number in the published report against the raw benchmark artefacts."""
import json, os, re, statistics, csv

D = "/mnt/2king/build/ds41"
L = os.path.join(D, "logs")


def cells(bench_dir):
    d = os.path.join(L, bench_dir)

    def med(p):
        v = []
        for k in "abc":
            try:
                v.append(json.load(open(os.path.join(d, p + k + ".json")))["results"][0]["aggregate_tps"])
            except Exception:
                pass
        return round(statistics.median(v), 1) if v else None

    def one(c):
        try:
            return round(json.load(open(os.path.join(d, c + ".json")))["results"][0]["aggregate_tps"], 1)
        except Exception:
            return None

    pf = {}
    try:
        r = json.load(open(os.path.join(d, "prefill_ladder.json"))).get("prefill", {})
        for k in ("8192", "32768", "131072"):
            if k in r and "tok_per_sec" in r[k]:
                pf[k] = round(r[k]["tok_per_sec"])
    except Exception:
        pass
    return {"c1": med("c1_"), "c4": one("c4_a"), "c8": med("c8_"), "c16": one("c16_a"), "prefill": pf}


def acceptance():
    out = {}
    for lg in sorted(os.listdir(L)):
        if not (lg.startswith("hunt") and lg.endswith(".log")):
            continue
        txt = open(os.path.join(L, lg), errors="ignore").read()
        for m in re.finditer(r"([A-Za-z0-9]+) acceptance: Mean acceptance length: ([0-9.]+), Mean verification depth: ([0-9.]+)/([0-9]+)", txt):
            out[m.group(1)] = (float(m.group(2)), m.group(3) + "/" + m.group(4))
        for m in re.finditer(r"acceptance Mean acceptance length: ([0-9.]+), Mean verification depth: ([0-9.]+)/([0-9]+)", txt):
            out.setdefault("anon_" + m.group(1), (float(m.group(1)), m.group(2) + "/" + m.group(3)))
        for m in re.finditer(r"([A-Za-z0-9]+) breakable=[^ ]* acceptance Mean acceptance length: ([0-9.]+), Mean verification depth: ([0-9.]+)/([0-9]+)", txt):
            out[m.group(1)] = (float(m.group(2)), m.group(3) + "/" + m.group(4))
    return out


def nsys_report(fname):
    p = os.path.join(L, fname)
    if not os.path.exists(p):
        return None
    rows, started = [], False
    for r in csv.reader(open(p, errors="ignore")):
        if r and r[0].strip() == "Time (%)":
            started = True
            continue
        if started and len(r) >= 9:
            try:
                rows.append((float(r[1]), int(r[2]), r[8]))
            except Exception:
                pass
    tot = sum(x[0] for x in rows)
    nccl = sum(x[0] for x in rows if x[2].startswith("nccl"))

    def percall(sub):
        for t, n, name in rows:
            if sub in name:
                return n, t / n / 1e3
        return None, None
    arn, ar = percall("AllReduce_bf16")
    agn, ag = percall("AllGather")
    return {"share": nccl / tot, "ar": ar, "arn": arn, "ag": ag, "agn": agn}


def show(tag, c):
    pf = c["prefill"]
    print("  %-22s C1 %7s C4 %7s C8 %7s C16 %7s  pf %s/%s/%s" % (
        tag, c["c1"], c["c4"], c["c8"], c["c16"],
        pf.get("8192"), pf.get("32768"), pf.get("131072")))


print("=" * 84)
print("A. GRID TABLE ROWS — recomputed from bench JSON (report values in the generator)")
print("=" * 84)
USED = {
    "jovian reference":     ("bench-r39luk5-cu134-512", (157.3, 376.3, 524.4, 809.4, 10904, 10430, 9405)),
    "karmic raw":           ("bench-lil-karmic-kk", (123.5, 173.8, 242.8, 205.1, 7552, 7505, 7240)),
    "NET_PLUGIN=none only": ("bench-final-ncclonly", (116.8, 144.9, 137.3, 256.5, None, None, None)),
    "IB_DISABLE only":      ("bench-final-ibonly", (120.2, 152.6, 132.2, None, None, None, None)),
    "PCIe allreduce only":  ("bench-trio-pcieonly", (127.9, 206.6, 213.6, None, None, None, None)),
    "P2P_LEVEL only":       ("bench-bis-p2ponly", (139.8, 405.2, 511.8, None, None, None, None)),
    "intended profile":     ("bench-trio-intspcx", (139.0, 409.0, 550.1, None, None, None, None)),
    "fixed capture128":     ("bench-hunt-base128", (124.1, 406.4, 542.5, 848.8, 11195, 10787, 9750)),
    "MTP3":                 ("bench-hunt2-mtp3", (158.6, 378.9, 546.6, 818.6, 11263, 10815, 9763)),
    "PR810":                ("bench-hunt2-p810", (144.8, 400.0, 549.9, 832.2, 11198, 10792, 9725)),
    "MTP3+PR810":           ("bench-hunt3-mtp3p810", (151.5, 377.8, 579.6, 805.4, 11202, 10801, 9762)),
}

# --- 2026-09-24: newest LIL layer (hunt6) ---
USED.update({
    "integration tip 0924": ("bench-hunt6-int0924",   (168.0, 413.8, 598.6, 825.8, 11260, 10829, 9797)),
    "dev tip 0924":         ("bench-hunt6-dev0924",   (165.5, 429.8, 598.2, 843.0, 11339, 10864, 9825)),
    "dev tip + L2 prefetch":("bench-hunt6-dev0924pf", (162.0, 417.2, 585.3, 838.0, 11219, 10838, 9801)),
})

fails = 0
for label, (bd, used) in USED.items():
    c = cells(bd)
    got = (c["c1"], c["c4"], c["c8"], c["c16"], c["prefill"].get("8192"), c["prefill"].get("32768"), c["prefill"].get("131072"))
    bad = [i for i, (u, g) in enumerate(zip(used, got)) if u is not None and (g is None or abs(u - g) > 0.051)]
    if bad:
        print("  MISMATCH %s at cols %s: report=%s source=%s" % (label, bad, used, got))
        fails += 1
    else:
        print("  ok ", end="")
        show(label, c)

print()
print("=" * 84)
print("B. DEPTH / LAW TABLE ROWS")
print("=" * 84)
DEEP = {
    "MTP5":               "bench-hunt4-mtp5",
    "MTP7 breakable off": "bench-hunt5-brk0",
    "MTP7 cost05":        "bench-hunt4-cost05",
    "MTP7 pcieoff":       "bench-hunt4-pcieoff",
    "MTP3 breakable on":  "bench-hunt5-brk1mtp3",
    "MTP3 breakable off": "bench-hunt5-brk0mtp3",
    "qualified defaults": "bench-hunt3-qual",
    "b12x contract6":     "bench-hunt-b6abase",
}
for label, bd in DEEP.items():
    show(label, cells(bd))

print()
print("=" * 84)
print("C. ACCEPTANCE / DEPTH — from engine-reported lines in the runner logs")
print("=" * 84)
acc = acceptance()
for k in sorted(acc):
    print("  %-22s acceptance %.2f   depth %s" % (k, acc[k][0], acc[k][1]))

print()
print("=" * 84)
print("D. nsys NUMBERS — recomputed from the CSV summaries")
print("=" * 84)
for tag in ("nsys-kk-kernels.csv", "nsys-r39-kernels.csv", "nsys-base-kernels.csv"):
    n = nsys_report(tag)
    if n:
        print("  %-22s NCCL share %5.1f%%   AllReduce %6.0f us/call (n=%s)   AllGather %6.0f us/call (n=%s)"
              % (tag, n["share"] * 100, n["ar"] or 0, n["arn"], n["ag"] or 0, n["agn"]))
    else:
        print("  %-22s MISSING" % tag)

print()
print("=" * 84)
print("E. PROSE RATIOS — recomputed so every claim in the text can be checked")
print("=" * 84)
ref = cells("bench-r39luk5-cu134-512")
raw = cells("bench-lil-karmic-kk")
base = cells("bench-hunt-base128")
for cell, name in (("c1", "C1"), ("c4", "C4"), ("c8", "C8"), ("c16", "C16")):
    print("  gap %-4s ref/raw = %.2fx   (ref %.1f / raw %.1f)" % (name, ref[cell] / raw[cell], ref[cell], raw[cell]))
print("  prefill 8k: raw is %.1f%% below ref (%.0f vs %.0f)" % (
    (ref["prefill"]["8192"] - raw["prefill"]["8192"]) / ref["prefill"]["8192"] * 100,
    raw["prefill"]["8192"], ref["prefill"]["8192"]))
mk = json.load(open(os.path.join(L, "profile-matched-c8.json")))["results"][0]["aggregate_tps"]
rk = json.load(open(os.path.join(L, "profile-r39-c8.json")))["results"][0]["aggregate_tps"]
print("  matched profile C8: karmic %.1f vs r39 %.1f -> %.2fx" % (mk, rk, rk / mk))
m3 = cells("bench-hunt2-mtp3")
p8 = cells("bench-hunt2-p810")
po = cells("bench-hunt4-pcieoff")
print("  MTP3 vs MTP7 C1: %.1f vs %.1f -> %+.1f%%" % (m3["c1"], base["c1"], (m3["c1"] / base["c1"] - 1) * 100))
print("  PR810 vs base C1: %.1f vs %.1f -> %+.1f%%" % (p8["c1"], base["c1"], (p8["c1"] / base["c1"] - 1) * 100))
print("  PCIe off vs on C1: %.1f vs %.1f -> %+.1f%%" % (po["c1"], base["c1"], (po["c1"] / base["c1"] - 1) * 100))
ei = cells("bench-eager-kk")
e39 = cells("bench-eager-r39")
print("  eager collapse: karmic %.1f vs graphs %.1f = %.1fx ; r39 %.1f vs graphs %.1f = %.1fx" % (
    ei["c1"], base["c1"], base["c1"] / ei["c1"], e39["c1"], ref["c1"], ref["c1"] / e39["c1"]))
intd = cells("bench-final-intended")
print("  capture 64->128: C8 %.1f -> %.1f (%+.1f%%), C16 %.1f -> %.1f (%+.1f%%)" % (
    intd["c8"], base["c8"], (base["c8"] / intd["c8"] - 1) * 100,
    intd["c16"], base["c16"], (base["c16"] / intd["c16"] - 1) * 100))
rev = cells("bench-lil-revert318-rv")
print("  revert318: C4 %.1f (raw %.1f), C8 %.1f (raw %.1f)" % (rev["c4"], raw["c4"], rev["c8"], raw["c8"]))
print()
print("FAILURES:", fails)
