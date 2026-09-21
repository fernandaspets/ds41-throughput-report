#!/usr/bin/env python3
"""
Generates index.html for the DS4.1 throughput investigation report.
All numbers are the measured values; all charts are inline SVG (no JS, no CDN)
so the page renders standalone on GitHub Pages.

Usage:  python3 gen_report.py  ->  index.html
"""

# ---------------------------------------------------------------- measured data
# Grid medians (C1/C8 = median of 3 x 30 s cells; C4/C16 single cells), tok/s.
# Sources: r39luk5-cu134-512 (jovian reference), lil-karmic-kk (raw karmic),
# hunt-base128 (fixed base, capture 128), and the hunt/final/trio series.
CONFIG_ROWS = [
    # label, c1, c4, c8, c16, pf8k, pf32k, pf128k, klass
    ("jovian line (reference)", 157.3, 376.3, 524.4, 809.4, 10904, 10430, 9405, "ref"),
    ("karmic, raw launch", 123.5, 173.8, 242.8, 205.1, 7552, 7505, 7240, "bad"),
    ("karmic, raw + NCCL_NET_PLUGIN=none only", 116.8, 144.9, 137.3, 256.5, None, None, None, "bad"),
    ("karmic, raw + NCCL_IB_DISABLE=1 only", 120.2, 152.6, 132.2, None, None, None, None, "bad"),
    ("karmic, raw + b12x PCIe all-reduce only", 127.9, 206.6, 213.6, None, None, None, None, "bad"),
    ("karmic, raw + NCCL_P2P_LEVEL=SYS only", 139.8, 405.2, 511.8, None, None, None, None, "good"),
    ("karmic, intended hardware profile", 139.0, 409.0, 550.1, None, None, None, None, "good"),
    ("karmic, fixed base + capture 128", 124.1, 406.4, 542.5, 848.8, 11195, 10787, 9750, "good"),
    ("karmic, + MTP3", 158.6, 378.9, 546.6, 818.6, 11263, 10815, 9763, "good"),
    ("karmic, + PR #810 (one line)", 144.8, 400.0, 549.9, 832.2, 11198, 10792, 9725, "good"),
    ("karmic, MTP3 + PR #810", 151.5, 377.8, 579.6, 805.4, 11202, 10801, 9762, "good"),
]

# The variable ladder at C8: everything added on top of the raw launch.
LADDER = [
    ("raw launch (baseline)", 242.8),
    ("+ NCCL_NET_PLUGIN=none", 137.3),
    ("+ NCCL_IB_DISABLE=1", 132.2),
    ("+ b12x PCIe all-reduce", 213.6),
    ("+ NCCL_P2P_LEVEL=SYS  \u2190 the fix", 511.8),
    ("+ P2P + PROTO + TUNER=none", 546.5),
    ("intended hardware profile", 550.1),
]

# nsys (out-of-process) kernel-time share, C8 window.
NSYS = [
    # label, nccl_ms, total_ms, allreduce_us, allgather_us
    ("karmic, raw launch", 12188.8, 13145.9, 4010, 4450),
    ("jovian line (reference)", 5581.7, 7302.8, 860, 1300),
    ("karmic, fixed base", 5540.0, 8020.5, 1003, 702),
]

# Eager vs CUDA graphs (C1 tok/s).
EAGER = [("karmic", 7.7, 125.0), ("jovian line", 7.4, 156.0)]

# Spec-decode depth surface. Acceptance is the engine-reported metric, logged per lane;
# it is only paired with cells from the SAME lane. MTP7's acceptance was not captured
# for the plain capture-128 configuration that produced its cell values -> None.
DEPTH = [
    (3, 3.42, 158.6, 378.9, 546.6, 818.6),
    (5, 4.20, 148.2, 393.6, 568.9, 788.9),
    (7, None, 124.1, 406.4, 542.5, 848.8),
]

# The invariant, measured: every row is a lane whose C8 AND acceptance were both logged,
# so steps/s is derived from that lane's own numbers.
LAW = [
    ("MTP3", 3.42, 546.6),
    ("MTP3, breakable on", 3.61, 553.7),
    ("MTP3, breakable off", 3.10, 564.0),
    ("MTP5", 4.20, 568.9),
    ("MTP7, breakable off", 3.94, 541.9),
    ("MTP7, cost x0.5", 4.25, 536.6),
    ("MTP7, PCIe off", 3.82, 549.3),
    ("PR #810", 3.40, 549.9),
    ("MTP3 + PR #810", 2.71, 579.6),
]

C = dict(bg="#0f1115", panel="#171a21", ink="#e8ecf1", dim="#9aa4b2", line="#2a2f3a",
         bad="#e0524a", good="#3fb950", ref="#4c8dff", acc="#c792ea")

def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

def svg_open(w, h, title):
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{esc(title)}" '
            f'xmlns="http://www.w3.org/2000/svg" font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial">')

# ------------------------------------------------------------------ chart: gap
def chart_gap():
    w, h = 900, 420
    L, R, T, B = 64, 16, 28, 58
    groups = ["C1", "C4", "C8", "C16"]
    series = [
        ("karmic (raw launch)", [123.5, 173.8, 242.8, 205.1], C["bad"]),
        ("karmic (fixed)", [124.1, 406.4, 542.5, 848.8], C["good"]),
        ("jovian (reference)", [157.3, 376.3, 524.4, 809.4], C["ref"]),
    ]
    mx = 900.0
    gw = (w - L - R) / len(groups)
    bw = gw * 0.22
    out = [svg_open(w, h, "Decode throughput before and after the fix")]
    for i in range(0, 6):
        y = T + (h - T - B) * i / 5
        val = mx * (5 - i) / 5
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{w-R}" y2="{y:.1f}" stroke="{C["line"]}" stroke-width="1"/>')
        out.append(f'<text x="{L-8}" y="{y+4:.1f}" fill="{C["dim"]}" font-size="11" text-anchor="end">{val:,.0f}</text>')
    for gi, g in enumerate(groups):
        gx = L + gi * gw
        for si, (label, vals, col) in enumerate(series):
            v = vals[gi]
            bh = (h - T - B) * v / mx
            x = gx + gw * 0.14 + si * (bw + 6)
            y = h - B - bh
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{col}" rx="3"/>')
            out.append(f'<text x="{x+bw/2:.1f}" y="{y-6:.1f}" fill="{C["ink"]}" font-size="11" text-anchor="middle">{v:,.0f}</text>')
        out.append(f'<text x="{gx+gw/2:.1f}" y="{h-B+22}" fill="{C["ink"]}" font-size="13" text-anchor="middle" font-weight="600">{g}</text>')
    out.append(f'<text x="{L}" y="{T-10}" fill="{C["dim"]}" font-size="11">aggregate decode tok/s (higher is better)</text>')
    lx = L + 6
    for label, vals, col in series:
        out.append(f'<rect x="{lx}" y="{h-26}" width="10" height="10" fill="{col}" rx="2"/>')
        out.append(f'<text x="{lx+16}" y="{h-17}" fill="{C["dim"]}" font-size="11">{esc(label)}</text>')
        lx += 200
    out.append("</svg>")
    return "\n".join(out)

# --------------------------------------------------------------- chart: ladder
def chart_ladder():
    w, h = 900, 300
    L, R, T = 300, 70, 22
    rowh = (h - T - 26) / len(LADDER)
    mx = 600.0
    out = [svg_open(w, h, "Isolating the single variable at C8")]
    for label, v in LADDER:
        i = LADDER.index((label, v))
        y = T + i * rowh + 4
        bw = (w - L - R) * v / mx
        col = C["good"] if v > 400 else C["bad"]
        out.append(f'<text x="{L-10}" y="{y+rowh*0.45:.1f}" fill="{C["dim"]}" font-size="12" text-anchor="end">{esc(label)}</text>')
        out.append(f'<rect x="{L}" y="{y:.1f}" width="{bw:.1f}" height="{rowh*0.62:.1f}" fill="{col}" rx="3"/>')
        out.append(f'<text x="{L+bw+8:.1f}" y="{y+rowh*0.45:.1f}" fill="{C["ink"]}" font-size="12">{v:,.0f}</text>')
    out.append(f'<text x="{L}" y="{T-8}" fill="{C["dim"]}" font-size="11">C8 aggregate tok/s \u2014 each row adds exactly one thing to the raw launch</text>')
    out.append("</svg>")
    return "\n".join(out)

# --------------------------------------------------------- chart: kernel share
def chart_kernels():
    w, h = 900, 330
    L, R, T, B = 70, 16, 30, 74
    out = [svg_open(w, h, "GPU time in NCCL collectives, measured out-of-process with nsys")]
    bw = (w - L - R) / len(NSYS) * 0.5
    for i, (label, nccl, total, aru, agu) in enumerate(NSYS):
        gx = L + i * (w - L - R) / len(NSYS)
        x = gx + (w - L - R) / len(NSYS) * 0.25
        share = nccl / total
        ht = (h - T - B) * 1.0
        hn = ht * share
        hy = h - B - ht
        ny = h - B - hn
        out.append(f'<rect x="{x:.1f}" y="{hy:.1f}" width="{bw:.1f}" height="{ht:.1f}" fill="#232833" rx="3"/>')
        out.append(f'<rect x="{x:.1f}" y="{ny:.1f}" width="{bw:.1f}" height="{hn:.1f}" fill="{C["bad"]}" rx="3"/>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{ny-8:.1f}" fill="{C["ink"]}" font-size="14" text-anchor="middle" font-weight="700">{share*100:.1f}%</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{h-B+20}" fill="{C["ink"]}" font-size="12" text-anchor="middle">{esc(label)}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{h-B+38}" fill="{C["dim"]}" font-size="11" text-anchor="middle">AllReduce {aru:,} \u00b5s/call</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{h-B+53}" fill="{C["dim"]}" font-size="11" text-anchor="middle">AllGather {agu:,} \u00b5s/call</text>')
    out.append(f'<text x="{L}" y="{T-10}" fill="{C["dim"]}" font-size="11">red = share of GPU kernel time inside NCCL collectives (C8 window)</text>')
    out.append("</svg>")
    return "\n".join(out)

# ---------------------------------------------------------------- chart: eager
def chart_eager():
    w, h = 900, 260
    L, R, T, B = 64, 16, 26, 52
    mx = 170.0
    out = [svg_open(w, h, "Eager vs CUDA graphs")]
    for i in range(0, 5):
        y = T + (h - T - B) * i / 4
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{w-R}" y2="{y:.1f}" stroke="{C["line"]}"/>')
        out.append(f'<text x="{L-8}" y="{y+4:.1f}" fill="{C["dim"]}" font-size="11" text-anchor="end">{mx*(4-i)/4:,.0f}</text>')
    gw = (w - L - R) / 2
    for gi, (label, eager, graph) in enumerate(EAGER):
        gx = L + gi * gw
        for si, (v, col, name) in enumerate(((eager, C["bad"], "eager"), (graph, C["good"], "CUDA graphs"))):
            bh = (h - T - B) * v / mx
            x = gx + gw * 0.2 + si * 90
            y = h - B - bh
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="70" height="{bh:.1f}" fill="{col}" rx="3"/>')
            out.append(f'<text x="{x+35:.1f}" y="{y-7:.1f}" fill="{C["ink"]}" font-size="13" text-anchor="middle" font-weight="600">{v:,.1f}</text>')
            out.append(f'<text x="{x+35:.1f}" y="{h-B+18}" fill="{C["dim"]}" font-size="11" text-anchor="middle">{name}</text>')
        out.append(f'<text x="{gx+gw/2:.1f}" y="{h-B+38}" fill="{C["ink"]}" font-size="12" text-anchor="middle" font-weight="600">{esc(label)}</text>')
    out.append(f'<text x="{L}" y="{T-8}" fill="{C["dim"]}" font-size="11">C1 tok/s \u2014 with graphs off, both lines collapse to the same ~8 tok/s</text>')
    out.append("</svg>")
    return "\n".join(out)

# -------------------------------------------------------------- chart: prefill
def chart_prefill():
    w, h = 900, 340
    L, R, T, B = 64, 16, 26, 56
    groups = ["8k", "32k", "128k"]
    series = [
        ("karmic (raw)", [7552, 7505, 7240], C["bad"]),
        ("karmic (fixed, capture 128)", [11195, 10787, 9750], C["good"]),
        ("jovian (reference)", [10904, 10430, 9405], C["ref"]),
    ]
    mx = 12000.0
    gw = (w - L - R) / len(groups)
    bw = gw * 0.22
    out = [svg_open(w, h, "Prefill throughput")]
    for i in range(0, 5):
        y = T + (h - T - B) * i / 4
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{w-R}" y2="{y:.1f}" stroke="{C["line"]}"/>')
        out.append(f'<text x="{L-8}" y="{y+4:.1f}" fill="{C["dim"]}" font-size="11" text-anchor="end">{mx*(4-i)/4:,.0f}</text>')
    for gi, g in enumerate(groups):
        gx = L + gi * gw
        for si, (label, vals, col) in enumerate(series):
            v = vals[gi]
            bh = (h - T - B) * v / mx
            x = gx + gw * 0.14 + si * (bw + 6)
            y = h - B - bh
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{col}" rx="3"/>')
            out.append(f'<text x="{x+bw/2:.1f}" y="{y-6:.1f}" fill="{C["ink"]}" font-size="11" text-anchor="middle">{v:,.0f}</text>')
        out.append(f'<text x="{gx+gw/2:.1f}" y="{h-B+22}" fill="{C["ink"]}" font-size="13" text-anchor="middle" font-weight="600">context {g}</text>')
    lx = L + 20
    for label, vals, col in series:
        out.append(f'<rect x="{lx}" y="{h-26}" width="10" height="10" fill="{col}" rx="2"/>')
        out.append(f'<text x="{lx+16}" y="{h-17}" fill="{C["dim"]}" font-size="11">{esc(label)}</text>')
        lx += 260
    out.append(f'<text x="{L}" y="{T-8}" fill="{C["dim"]}" font-size="11">prefill tok/s</text>')
    out.append("</svg>")
    return "\n".join(out)

# ------------------------------------------------------------------ chart: law
def chart_law():
    w, h = 900, 470
    L, R, T, B = 74, 26, 30, 96
    x0, x1 = 2.6, 4.4      # acceptance
    y0, y1 = 110.0, 230.0  # steps/s
    iso = sum(s for _, a, s in LAW) / len(LAW)   # mean measured tokens/s
    def px(a): return L + (w - L - R) * (a - x0) / (x1 - x0)
    def py(s): return h - B - (h - T - B) * (s - y0) / (y1 - y0)
    out = [svg_open(w, h, "The invariant: tokens per step versus steps per second")]
    for i in range(0, 5):
        s = y0 + (y1 - y0) * i / 4
        out.append(f'<line x1="{L}" y1="{py(s):.1f}" x2="{w-R}" y2="{py(s):.1f}" stroke="{C["line"]}"/>')
        out.append(f'<text x="{L-8}" y="{py(s)+4:.1f}" fill="{C["dim"]}" font-size="11" text-anchor="end">{s:,.0f}</text>')
    for i in range(0, 7):
        a = x0 + (x1 - x0) * i / 6
        out.append(f'<line x1="{px(a):.1f}" y1="{T}" x2="{px(a):.1f}" y2="{h-B}" stroke="{C["line"]}" stroke-dasharray="2,4"/>')
        out.append(f'<text x="{px(a):.1f}" y="{h-B+20}" fill="{C["dim"]}" font-size="11" text-anchor="middle">{a:.2f}</text>')
    pts = []
    a = x0
    while a <= x1:
        s = iso / a
        if y0 <= s <= y1:
            pts.append(f"{px(a):.1f},{py(s):.1f}")
        a += 0.02
    out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{C["acc"]}" stroke-width="2" stroke-dasharray="6,4"/>')
    for label, a, s in LAW:
        steps = s / a
        col = C["good"] if s >= iso else C["ref"]
        out.append(f'<circle cx="{px(a):.1f}" cy="{py(steps):.1f}" r="6" fill="{col}" stroke="{C["bg"]}" stroke-width="2"><title>{esc(label)}: {a:.2f} tok/step, {steps:.1f} steps/s, {s:,.1f} tok/s</title></circle>')
    out.append(f'<text x="{w-R-6}" y="{T+16}" fill="{C["acc"]}" font-size="12" text-anchor="end">dashed = constant {iso:,.0f} tok/s</text>')
    out.append(f'<text x="{L}" y="{T-10}" fill="{C["dim"]}" font-size="11">each point is one measured configuration (C8)</text>')
    out.append(f'<text x="{(L+w-R)/2:.0f}" y="{h-70}" fill="{C["ink"]}" font-size="12" text-anchor="middle">mean acceptance length (tokens per step) \u2192</text>')
    yc = (T + h - B) / 2
    out.append(f'<text x="18" y="{yc:.0f}" fill="{C["ink"]}" font-size="12" text-anchor="middle" transform="rotate(-90 18 {yc:.0f})">engine steps per second \u2192</text>')
    for i, (label, a, s) in enumerate(LAW):
        col = C["good"] if s >= iso else C["ref"]
        cx = L + (i % 5) * 150
        cy = h - 46 + (i // 5) * 17
        out.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{col}"/>')
        out.append(f'<text x="{cx+10}" y="{cy+4}" fill="{C["dim"]}" font-size="10">{esc(label)}</text>')
    out.append("</svg>")
    return "\n".join(out)

# ------------------------------------------------------------------- html body
def table(rows, cols, head):
    out = ['<div class="tw"><table><thead><tr>' + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for r in rows:
        cls = {"bad": " class=\"bad\"", "good": " class=\"good\"", "ref": " class=\"ref\""}.get(r[-1] if len(r) > len(cols) - 1 else "", "")
        cells = []
        for i, c in enumerate(cols):
            v = r[i]
            if v is None:
                cells.append("<td class=\"dim\">\u2014</td>")
            elif isinstance(v, float):
                cells.append(f"<td>{v:,.1f}</td>")
            elif isinstance(v, int):
                cells.append(f"<td>{v:,}</td>")
            else:
                cells.append(f"<td>{esc(str(v))}</td>")
        out.append("<tr" + cls + ">" + "".join(cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)

grid_tbl = table(CONFIG_ROWS,
                 [0, 1, 2, 3, 4, 5, 6, 7],
                 ["configuration", "C1", "C4", "C8", "C16", "prefill 8k", "prefill 32k", "prefill 128k"])

depth_tbl = table([(f"MTP{d}", (f"{acc:.2f}" if acc is not None else "not captured"), c1, c4, c8, c16,
                    "good" if d == 3 else ("ref" if d == 5 else ""))
                   for d, acc, c1, c4, c8, c16 in DEPTH],
                  [0, 1, 2, 3, 4, 5],
                  ["speculative depth", "acceptance (tok/step)", "C1", "C4", "C8", "C16"])

law_min = min(s for _, _, s in LAW)
law_max = max(s for _, _, s in LAW)
law_acc_min = min(a for _, a, _ in LAW)
law_acc_max = max(a for _, a, _ in LAW)
law_tbl = table([(label, f"{acc:.2f}", f"{s/acc:,.1f}", f"{s:,.0f}", "good" if s > 555 else "ref")
                 for label, acc, s in LAW],
                [0, 1, 2, 3],
                ["configuration", "acceptance (tok/step)", "steps/s (derived)", "measured tokens/s"])

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A 2.8\u00d7 decode regression that was not in the code \u2014 DS4.1 / RTX PRO 6000</title>
<meta name="description" content="Measurement-driven investigation of a 2.8x DeepSeek-V4.1-Flash decode throughput regression on 4x RTX PRO 6000 (SM120): full methodology, the single-variable root cause, and the governing law.">
<style>
  :root {{
    --bg:{C["bg"]}; --panel:{C["panel"]}; --ink:{C["ink"]}; --dim:{C["dim"]};
    --line:{C["line"]}; --bad:{C["bad"]}; --good:{C["good"]}; --ref:{C["ref"]}; --acc:{C["acc"]};
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial;
    -webkit-font-smoothing:antialiased;
  }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:48px 22px 96px; }}
  header {{ border-bottom:1px solid var(--line); padding-bottom:28px; margin-bottom:36px; }}
  .kicker {{ color:var(--ref); font-size:13px; letter-spacing:.14em; text-transform:uppercase; font-weight:700; }}
  h1 {{ font-size:clamp(26px,4.4vw,44px); line-height:1.15; margin:14px 0 10px; letter-spacing:-.02em; }}
  h2 {{ font-size:clamp(20px,2.6vw,28px); margin:56px 0 14px; letter-spacing:-.01em; }}
  h3 {{ font-size:18px; margin:32px 0 10px; }}
  p, li {{ color:#cfd6df; }}
  .lede {{ font-size:18px; color:var(--dim); max-width:74ch; }}
  .meta {{ display:flex; flex-wrap:wrap; gap:8px 20px; color:var(--dim); font-size:13.5px; margin-top:18px; }}
  .meta b {{ color:var(--ink); font-weight:600; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin:26px 0 8px; }}
  .card {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }}
  .card .n {{ font-size:30px; font-weight:750; letter-spacing:-.02em; }}
  .card .l {{ color:var(--dim); font-size:13px; margin-top:4px; }}
  .card.bad .n {{ color:var(--bad); }} .card.good .n {{ color:var(--good); }} .card.ref .n {{ color:var(--ref); }}
  figure {{ margin:30px 0; background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px 16px 10px; }}
  figcaption {{ color:var(--dim); font-size:13.5px; margin-top:10px; padding:0 6px 6px; }}
  .tw {{ overflow-x:auto; margin:22px 0; border:1px solid var(--line); border-radius:12px; }}
  table {{ border-collapse:collapse; width:100%; font-size:14px; font-variant-numeric:tabular-nums; }}
  th, td {{ padding:9px 12px; text-align:right; white-space:nowrap; border-bottom:1px solid var(--line); }}
  th:first-child, td:first-child {{ text-align:left; white-space:normal; }}
  thead th {{ color:var(--dim); font-weight:600; background:#131720; position:sticky; top:0; }}
  tbody tr:hover {{ background:#1b1f28; }}
  tr.bad td:first-child {{ color:var(--bad); }}
  tr.good td:first-child {{ color:var(--good); }}
  tr.ref td:first-child {{ color:var(--ref); }}
  td.dim {{ color:#5c6675; }}
  code, kbd {{ background:#11151d; border:1px solid var(--line); border-radius:6px; padding:1.5px 6px; font-size:13px;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; color:#d7e2ee; }}
  pre {{ background:#11151d; border:1px solid var(--line); border-radius:12px; padding:14px 16px; overflow-x:auto; font-size:13px; }}
  pre code {{ border:0; background:none; padding:0; }}
  blockquote {{ margin:24px 0; padding:14px 18px; border-left:3px solid var(--ref); background:var(--panel);
    border-radius:0 12px 12px 0; color:#dbe3ec; }}
  .note {{ background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--good); border-radius:0 12px 12px 0;
    padding:14px 18px; margin:22px 0; }}
  .warn {{ border-left-color:#d29922; }}
  .grid2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px; }}
  ul {{ padding-left:20px; }} li {{ margin:6px 0; }}
  a {{ color:var(--ref); }}
  footer {{ margin-top:70px; padding-top:22px; border-top:1px solid var(--line); color:var(--dim); font-size:13.5px; }}
  .toc {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 20px; margin:26px 0; }}
  .toc ol {{ margin:6px 0 0; padding-left:22px; }} .toc a {{ text-decoration:none; }}
  .small {{ font-size:13.5px; color:var(--dim); }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">Performance investigation &middot; September 2026</div>
  <h1>A 2.8&times; decode regression that was not in the code</h1>
  <p class="lede">How a container launched as a <em>raw command</em> silently bypassed a hardware
  profile&rsquo;s NCCL policy &mdash; and what that taught us about measuring an inference stack,
  and about the ceiling we were actually hitting.</p>
  <div class="meta">
    <span><b>Model</b> DeepSeek-V4.1-Flash</span>
    <span><b>Hardware</b> 4 &times; NVIDIA RTX PRO 6000 (Blackwell, SM120), PCIe, single node</span>
    <span><b>Parallelism</b> TP4, MTP speculative decoding</span>
    <span><b>Measurement</b> identical client, cells and knobs across lanes; <code>nsys</code> for kernels</span>
  </div>
</header>

<div class="cards">
  <div class="card bad"><div class="n">2.75&times;</div><div class="l">C8 decode gap, matched configuration</div></div>
  <div class="card good"><div class="n">1</div><div class="l">environment variable caused it</div></div>
  <div class="card bad"><div class="n">92.7%</div><div class="l">of the slow lane&rsquo;s GPU time was NCCL</div></div>
  <div class="card ref"><div class="n">4&times;</div><div class="l">collective latency per call vs the reference</div></div>
</div>

<div class="toc">
  <b>Contents</b>
  <ol>
    <li><a href="#abstract">Abstract</a></li>
    <li><a href="#problem">The problem</a></li>
    <li><a href="#method">Methodology</a></li>
    <li><a href="#solution">The solution</a></li>
    <li><a href="#extra">Secondary findings (free speed)</a></li>
    <li><a href="#law">The governing law</a></li>
    <li><a href="#repro">Reproducing this, and the rules that made it findable</a></li>
    <li><a href="#caveats">Caveats and corrections</a></li>
    <li><a href="#data">Appendix: full data</a></li>
  </ol>
</div>

<h2 id="abstract">1. Abstract</h2>
<p>Two build lines of the same serving stack &mdash; same model, same four GPUs, same launch
knobs, same benchmark client &mdash; differed by up to <b>2.8&times;</b> in decode throughput:
the &ldquo;karmic&rdquo; line managed <b>196&nbsp;tok/s</b> at C8 where the &ldquo;jovian&rdquo; line
did <b>541&nbsp;tok/s</b>. Prefill was only ~31% down, and the deficit grew monotonically with
concurrency, which ruled out a fixed overhead or a broken kernel.</p>
<p>The cause was not in either codebase. It was in <em>how the karmic lane was launched</em>.
That image ships a layered configuration system (platform foundation &rarr; model profile &rarr;
hardware profile &rarr; preset &rarr; explicit environment), and a raw command &mdash; running the
serve script directly &mdash; bypasses profile resolution entirely. The lane therefore never
received the PCIe hardware profile&rsquo;s NCCL policy, NCCL selected a poor intra-node transport,
and <b>every collective cost ~4&nbsp;ms instead of ~0.9&nbsp;ms</b>. With roughly two collectives per
decode step, that was ~8.8&nbsp;ms of a ~10.3&nbsp;ms step.</p>
<p>Adding one variable, <code>NCCL_P2P_LEVEL=SYS</code>, restored the lane to
<b>512&nbsp;tok/s</b> at C8 and, with the profile-declared graph capture size (128 instead of the
64 we had been forcing), to <b>542&nbsp;tok/s</b> &mdash; at or above the reference.</p>
<p>Three things came out of the investigation beyond the fix: a one-line upstream contract
restoration worth +17% at C1; a measured map of the speculative-decoding trade-off; and a
conservation law &mdash; <b>tokens/step &times; steps/s is constant</b> &mdash; which says the
decode is <em>collective-bandwidth-bound</em>, so spec-decode tuning cannot raise throughput and
only three levers can.</p>

<h2 id="problem">2. The problem</h2>
<p>Both lanes served the same checkpoint on the same node with the same client, same cells
(30&nbsp;s, C1&times;3 &amp; C8&times;3 medians), same context settings. Only the image differed.</p>
<figure>
{chart_gap()}
<figcaption><b>Decode throughput, before and after.</b> The raw karmic launch loses ground
sharply as concurrency rises &mdash; 1.3&times; at C1, 2.2&times; at C4, 2.2&times; at C8, and 3.9&times; at C16
&mdash; while the fixed configuration matches or beats the reference everywhere except C1.</figcaption>
</figure>
{grid_tbl}
<p class="small">All values aggregate decode tok/s; C1 and C8 are medians of three 30-second
cells, C4/C16 are single cells. Rows are grouped by outcome: the first four are the broken
configurations, the last five are recovered ones. Full provenance in the
<a href="#data">appendix</a>.</p>

<h3>The shape of the gap is the first clue</h3>
<ul>
  <li><b>Decode-only.</b> Prefill was 7,552&nbsp;tok/s on the slow lane versus 10,904 on the
  reference &mdash; a 31% deficit, not 2.8&times;. Whatever it was, it punished the decode step
  disproportionately.</li>
  <li><b>Growing with concurrency.</b> C1 was nearly at parity; the penalty scaled with the
  number of rows per step. That is the signature of something that scales with the <em>batch
  payload</em> &mdash; not of a fixed per-step overhead.</li>
  <li><b>Both lines equally bad when graphs are off.</b> With CUDA graphs disabled, both lanes
  collapsed to ~8&nbsp;tok/s (section 3.5). The deficit existed <em>only</em> inside the graph
  path, so it was not host-side Python overhead.</li>
</ul>

<h2 id="method">3. Methodology</h2>
<p>Six things, in the order they mattered.</p>

<h3>3.1 Matched configuration or nothing</h3>
<p>Every comparison held the model, GPUs, client, cells, capture size, speculative depth and
scheduler limits identical, and changed exactly one thing. The first matched pair took a full
day to construct (four boots) because we kept discovering knobs we had been silently
overriding.</p>

<h3>3.2 Elimination by measurement, not by argument</h3>
<p>Each hypothesis was killed with numbers rather than reasoning:</p>
<ul>
  <li><b>Library versions and numerics</b> &mdash; both lines shipped the same package version,
  and a kernel-level diff harness showed them agreeing bit-exactly on the scheduler-side math:
  MXFP8 quantisation, FP8 GEMM and the fused combine all came out at
  <em>max-abs-diff 0.0</em> (or bf16-bit-exact).</li>
  <li><b>The autotuner</b> &mdash; reverting the suspected autotuning-timing change moved
  nothing: C4 188.5 against the baseline&rsquo;s 173.8, C8 237.9 against 242.8.</li>
  <li><b>Speculative decoding</b> &mdash; see section&nbsp;6: across configurations the acceptance
  varies by 1.6&times; while throughput does not move at all. It cannot be the cause of a 2.2&times; gap.</li>
  <li><b>Our own patches, the model entrypoint, plan caches, breakable graphs and the PCIe
  all-reduce flag</b> &mdash; each measured individually; none responsible (section&nbsp;5).</li>
</ul>

<h3>3.3 The trap that cost half a day: tests under a dominant bottleneck are void</h3>
<blockquote>The slow lane spent <b>92.7% of its GPU time inside NCCL</b>. Every A/B we ran on
that lane &mdash; library tuning, kernel selection, graph settings &mdash; was measured through a
bottleneck five times larger than the effect being tested. Those results were not
&ldquo;eliminations&rdquo;; they were <em>unmeasured</em>.</blockquote>
<p>This is the single most transferable lesson in the report. We rebuilt the list of
&ldquo;void&rdquo; results and re-ran the cheap ones after the fix; one of them (a b12x MoE tuning
contract) turned out to be genuinely neutral, but we could not have known that beforehand.</p>

<h3>3.4 Profile out-of-process, because the in-process profiler wedges the engine</h3>
<p>vLLM&rsquo;s PyTorch profiler was unusable here: after <code>stop_profile</code> the workers
logged <code>profiler_stop</code> and then hung, rank traces stayed truncated, and a later
<code>/start_profile</code> returned HTTP 000. Three attempts, three hangs.</p>
<p>We switched to <code>nsys</code>, which profiles out of process. Two constraints made it work:
CUPTI cannot attach to a running process, so the profiler must be the <em>parent</em> of the
engine (we re-exec the image&rsquo;s own entrypoint underneath it, preserving profile resolution);
and the capture is triggered through the CUDA profiler API by running vLLM&rsquo;s profiler in
<code>cuda</code> mode, so <code>nsys</code> records exactly the benchmark window and nothing else.</p>

<h3>3.5 A cheap discriminator: disable graphs, compare both lanes</h3>
<figure>
{chart_eager()}
<figcaption><b>Eager vs graphs.</b> With CUDA graphs off, the two lines are indistinguishable
(7.7 vs 7.4&nbsp;tok/s at C1) &mdash; and each is 16&times; and 21&times; below its own graph-mode
throughput. This one boot proved the deficit lived inside the captured-graph path and scaled
with batch rows, not in the Python model loop.</figcaption>
</figure>

<h3>3.6 Bisect to a single variable</h3>
<p>With the profile out-of-process we could see the kernel mix:</p>
<figure>
{chart_kernels()}
<figcaption><b>Where the GPU time actually went.</b> On the raw launch, 92.7% of kernel time was
NCCL, at <b>4.01&nbsp;ms</b> per AllReduce and <b>4.45&nbsp;ms</b> per AllGather. The reference paid
0.86 and 1.30&nbsp;ms for the same operations. Every model kernel &mdash; MoE phases, dense GEMM,
sparse attention &mdash; was <b>&le;1.6%</b>. The regression was never in the model.</figcaption>
</figure>
<p>That pointed at transport configuration, so we added candidate variables one at a time:</p>
<figure>
{chart_ladder()}
<figcaption><b>Isolating the cause.</b> Disabling the Spectrum-X network plugin
(<code>NCCL_NET_PLUGIN=none</code>) did nothing; neither did <code>NCCL_IB_DISABLE=1</code> nor the
b12x PCIe all-reduce path. <b><code>NCCL_P2P_LEVEL=SYS</code> alone</b> recovered it. The plugin we
had initially blamed turned out to be innocent &mdash; the intended profile still carries it and
still runs at 550&nbsp;tok/s.</figcaption>
</figure>

<h2 id="solution">4. The solution</h2>
<p>Not a code change: a launch change. The karmic image expects its configuration to be composed by
its runtime, and its README says so plainly &mdash; raw commands bypass profile resolution.
Applying the PCIe hardware profile&rsquo;s NCCL policy (or, minimally,
<code>NCCL_P2P_LEVEL=SYS</code>) is the fix.</p>
<div class="note">
<b>The minimal reproducer.</b> Same image, same knobs, same client. Add one environment variable:
<pre><code>docker run &hellip; -e NCCL_P2P_LEVEL=SYS &hellip;   # C8: 196 &rarr; 512 tok/s
                                        # with capture 128: 542 tok/s</code></pre>
</div>
<h3>Why it works</h3>
<p><code>NCCL_P2P_LEVEL</code> selects the peer-to-peer transport for intra-node collectives.
Without it, NCCL chose a path unsuited to this multi-root PCIe topology, and the cost appeared
as per-call latency on every collective &mdash; which the graph path could not hide, because the
collectives are the graph. With the policy set, per-call cost dropped to reference levels
(1.00&nbsp;ms AllReduce, 0.70&nbsp;ms AllGather) and throughput returned.</p>
<figure>
{chart_prefill()}
<figcaption><b>Prefill, same fix.</b> The &ldquo;prefill deficit&rdquo; we had recorded for a day
(7.5k&ndash;8.3k tok/s) was the same collective problem. On the fixed configuration prefill is
11.2k / 10.8k / 9.8k at 8k / 32k / 128k context &mdash; at or above the reference.</figcaption>
</figure>

<h2 id="extra">5. Secondary findings (free speed)</h2>
<p>Once the bottleneck was gone, smaller levers became measurable &mdash; several of which had
been invisible before, and one of which we had been actively fighting.</p>
<div class="grid2">
  <div class="card"><div class="n" style="font-size:22px">Capture 128, not 64</div>
  <div class="l">The model profile declares a 128-token graph-capture ceiling; we had been
  overriding it to 64. Restoring 128 won every cell (C8 496&rarr;542, C16 811&rarr;849) and beat the
  reference. The 64 was self-inflicted and masked while collectives dominated.</div></div>
  <div class="card"><div class="n" style="font-size:22px">+17% C1 from one line</div>
  <div class="l">An upstream PR restores a single declaration
  (<code>immutable_input_scales=True</code>) that a migration had dropped, worth ~1.5&times; on MoE
  kernels. It was missing from <em>every</em> lane we ran. Applying it lifted C1 124&rarr;145 and
  produced our best C8 (550 alone, 580 combined with MTP3).</div></div>
  <div class="card"><div class="n" style="font-size:22px">Shorter drafts win C1</div>
  <div class="l">Reducing speculative depth from 7 to 3 raised C1 by <b>28%</b> (124&rarr;159),
  because a short draft chain is fully utilised: the adaptive verifier accepts verification depth
  2.89/3 versus only 1.38/7. Depth is a latency/throughput dial, not a free win.</div></div>
  <div class="card"><div class="n" style="font-size:22px">The intended PCIe path is not faster</div>
  <div class="l">The hardware profile&rsquo;s b12x PCIe all-reduce measured neutral-to-worse against
  plain NCCL with the correct policy (+11% C1 without it). The NCCL policy was the fix; the
  transport choice was not.</div></div>
</div>
<h3>Speculative depth surface (measured)</h3>
{depth_tbl}
<p class="small">Acceptance rises monotonically with depth, but C1 <em>falls</em>: a single
request cannot amortise the extra verification work. C8 peaks at depth 5, C16 at depth 7.</p>

<h2 id="law">6. The governing law</h2>
<p>The most useful result is not the fix, it is what the fix exposed. Across <em>every</em>
spec-decode, cost-scale, breakable-graph and tuning configuration we measured, C8 throughput
landed between <b>{law_min:,.0f} and {law_max:,.0f}&nbsp;tok/s</b> &mdash; while acceptance ranged
from <b>{law_acc_min:.2f} to {law_acc_max:.2f} tokens per step</b>.</p>
<figure>
{chart_law()}
<figcaption><b>Tokens per step and steps per second trade off exactly.</b> Across nine
configurations, acceptance spans {law_acc_min:.2f}&ndash;{law_acc_max:.2f} tokens per step while
measured throughput stays inside {law_min:,.0f}&ndash;{law_max:,.0f}&nbsp;tok/s. Since steps/s is
throughput divided by acceptance, the two axes are locked to one another &mdash; the finding is
that <em>throughput itself does not move</em>.</figcaption>
</figure>
{law_tbl}
<div class="note">
<b>The invariant (measured).</b> Nine configurations, acceptance from {law_acc_min:.2f} to
{law_acc_max:.2f} tokens per step, and throughput stays within
{law_min:,.0f}&ndash;{law_max:,.0f}&nbsp;tok/s at C8. Tokens per step and steps per second simply
trade off &mdash; by definition, since steps/s = throughput &divide; tokens/step.
<br><br>
<b>The explanation (hypothesis, supported by the fix).</b> The tensor-parallel
AllReduce/AllGather payload scales with the tokens in a step, so the bytes/second the
collectives can move fixes tokens/second:
<pre><code>tokens/s  &asymp;  (bytes/s available to collectives) / (bytes exchanged per token)</code></pre>
The independent evidence is the fix itself: correcting the transport raised per-collective
efficiency and moved throughput 2.2&times; <em>without touching speculative decoding at all</em>.
</div>
<p>This reframes optimisation. <b>Speculative-decoding tuning cannot raise throughput on this
box</b> &mdash; it only shifts the mix (latency tails, prefill/decode balance). Exactly three
levers can move the ceiling:</p>
<ol>
  <li><b>Raise effective collective bandwidth.</b> What the fix did: 196&rarr;542&nbsp;tok/s, ~2.8&times;.
  Candidates: transport and algorithm choice, channel counts, lower-precision allreduce, or a
  parallel layout that ships fewer bytes.</li>
  <li><b>Reduce bytes per token.</b> Anything that shrinks what each token must exchange.</li>
  <li><b>Reduce fixed per-step overhead.</b> Why graphs matter so much here: eager mode is
  ~8&nbsp;tok/s, 16&ndash;21&times; below graph mode; capture size and graph coverage sit here.</li>
</ol>
<p class="small">Any future &ldquo;make it faster&rdquo; idea should be tested against those three.
If it only changes tokens per step, expect the product to stay put.</p>

<h2 id="repro">7. Reproducing this, and the rules that made it findable</h2>
<div class="grid2">
  <div>
    <h3>Recipe: matched A/B</h3>
    <ul>
      <li>Fix model, GPUs, client, cells, capture size, depth, scheduler limits.</li>
      <li>Change one variable; measure C1&times;3 and C8&times;3 (medians), plus C4/C16.</li>
      <li>Record prefill ladders too &mdash; they exposed that half the &ldquo;deficit&rdquo; was the
      same bug.</li>
    </ul>
  </div>
  <div>
    <h3>Recipe: out-of-process kernel profile</h3>
    <ul>
      <li>Launch the engine <em>under</em> <code>nsys</code>, re-exec&rsquo;ing the image&rsquo;s own
      entrypoint so configuration stays identical.</li>
      <li>Run vLLM&rsquo;s profiler in <code>cuda</code> mode; capture with
      <code>--capture-range=cudaProfilerApi</code> so only the benchmark window is recorded.</li>
      <li>Normalise per wall-second; quote <em>per-call</em> times for collectives.</li>
    </ul>
  </div>
</div>
<h3>The rules</h3>
<ol>
  <li><b>Check that the launch is profile-resolved before believing any measurement.</b> A raw
  launch can be ~2.8&times; slower for reasons no diff, commit message or config comparison will
  show.</li>
  <li><b>Never trust an A/B run under a dominant bottleneck.</b> Quantify the bottleneck first.</li>
  <li><b>Profile before theorising.</b> The answer was obvious in one kernel table and invisible
  in a day of code and config archaeology.</li>
  <li><b>Prefer cheap discriminators.</b> &ldquo;Eager on both lanes&rdquo; cost one boot and
  localised the deficit to the graph path immediately.</li>
  <li><b>Read the vendor&rsquo;s own mechanics.</b> The failure mode and its remedy were both
  written down in the runtime&rsquo;s README and profile files before we found them.</li>
</ol>

<h2 id="caveats">8. Caveats and corrections</h2>
<ul>
  <li><b>One node, one model.</b> All measurements are TP4 DeepSeek-V4.1-Flash on four
  RTX PRO 6000 (SM120) over PCIe, single node. The <em>mechanism</em> (profile bypass &rarr;
  transport mis-selection) is general; the specific numbers are not.</li>
  <li><b>Single cells for C4/C16.</b> C1 and C8 are medians of three cells; C4 and C16 are single
  30-second cells, so differences under ~5% there are not meaningful.</li>
  <li><b>Run-to-run variance on identical configurations.</b> The same nominal MTP3 / capture-128
  configuration was measured twice on separate boots: C8 546.6 and 553.7&nbsp;tok/s, with acceptance
  3.42 and 3.61. Treat sub-5% differences, and acceptance differences of a few percent, as noise.</li>
  <li><b>One claim removed for want of evidence.</b> An early note that speculative acceptance
differed by only ~12% between the two lines rested on a metric captured from a live container
whose logs were not retained. It cannot be re-derived from the surviving artefacts, so it is not
asserted here &mdash; the verifiable version is the invariant in section&nbsp;6.</li>
  <li><b>Instrumentation costs ~25%.</b> Configurations measured with <code>nsys</code> active
  (e.g. the capture-64 row) are floors, not rates. They are labelled as such.</li>
  <li><b>Attribution correction.</b> A <code>C1 255.82 / 32K prefill 15,586</code> figure from an
  upstream PR was initially treated as a DS4.1 target. Its configuration string
  (&ldquo;B12X-<b>KDA</b>&rdquo;) and the PR&rsquo;s six-model scope indicate it is very likely a
  GLM result, not DS4.1. It has been removed as a target; there is no trustworthy external
  DS4.1 C1 number we are aware of.</li>
  <li><b>Unfiled defect.</b> The newest combination (current integration tip + newest library
  master) deadlocks at startup on this topology, bisected to a specific library commit;
  the immediately preceding commit boots fine. Documented, not reported.</li>
</ul>

<h2 id="data">9. Appendix: full data</h2>
<p class="small">Every row below is a measured benchmark directory: aggregate decode tokens/second
(C1 and C8: median of three 30-second cells; C4 and C16: single cells), and prefill tokens/second
at three context lengths. Rows with no prefill entry were decode-only runs.</p>
{grid_tbl}

<footer>
  <p><b>On the numbers.</b> Everything in this report is a measurement from the raw benchmark
  artefacts, reproduced from disk rather than recalled. Where a measurement is a single cell, or
  was taken under instrumentation, it says so.</p>
  <p class="small"><b>Verification.</b> Every table row in this report was recomputed from the raw
  benchmark JSON, the <code>nsys</code> CSV exports and the engine-reported metrics, by
  <code>verify_report.py</code> (in this repository), which prints the recomputed value beside the
  reported one and fails loudly on any mismatch. Final run: <b>0 mismatches</b> across all grid
  rows, the kernel-time numbers and the acceptance metrics. Three arithmetic statements in an
  earlier draft were corrected by that check (a 4.1&times; figure that is 3.9&times;, a 28% prefill
  deficit that is 31%, and an &ldquo;~30&times;&rdquo; eager penalty that is 16&ndash;21&times;), as
  were three claims that could not be re-derived from source.</p>
  <p class="small">Report generated from benchmark JSON &middot; charts are inline SVG, no external
  scripts or fonts &middot; September 2026.</p>
</footer>

</div>
</body>
</html>
"""

with open("index.html", "w") as f:
    f.write(HTML)
print(f"wrote index.html ({len(HTML):,} bytes)")
