# A 2.8× decode regression that was not in the code

A measurement-driven investigation into a **2.8× DeepSeek-V4.1-Flash decode-throughput
regression** on 4 × NVIDIA RTX PRO 6000 (Blackwell, SM120) over PCIe, single node,
TP4 with MTP speculative decoding.

**Read the report:** https://fernandaspets.github.io/ds41-throughput-report/

## Summary

Two build lines of the same serving stack differed by up to 2.8× in decode throughput
(196 vs 541 tok/s at C8). Prefill was only ~28% down, and the deficit grew with
concurrency — so it was not a fixed overhead and not a broken kernel.

The cause was not in either codebase. The slower lane was launched as a **raw command**,
which bypasses the runtime's layered configuration resolution (platform foundation →
model profile → hardware profile → preset → explicit environment). It therefore never
received the PCIe hardware profile's **NCCL policy**, NCCL picked a poor intra-node
transport, and every collective cost **~4 ms instead of ~0.9 ms**. Because the collective
payload scales with the tokens in a step, that capped decode throughput.

Adding a single variable — `NCCL_P2P_LEVEL=SYS` — restored the lane, and using the
profile-declared graph capture size (128, where we had been forcing 64) took it to or
above the reference.

## What is in the report

- **The problem** — the gap, and the shape of it (decode-only, growing with concurrency).
- **Methodology** — matched-configuration A/B, elimination by measurement, out-of-process
  `nsys` profiling (the in-process profiler wedges the engine), an eager-vs-graph
  discriminator, and bisection to a single variable.
- **The public-service warning** — tests run under a dominant bottleneck are void; 92.7% of
  the slow lane's GPU time was NCCL, so every A/B measured through it was unmeasured.
- **Secondary findings** — graph capture size, a one-line upstream contract restoration
  worth +17% at C1, the measured speculative-depth trade-off, and why the intended PCIe
  all-reduce path was *not* faster.
- **The governing law** — across every spec-decode configuration, `tokens/step × steps/s`
  is invariant: decode is **collective-bandwidth-bound**, so spec-decode tuning cannot raise
  throughput, and only three levers can.
- **Caveats** — single node/model, single cells for C4/C16, ~25% instrumentation cost, an
  attribution correction, and one documented-but-unfiled upstream defect.

## Files

| file | what |
|---|---|
| `index.html` | the report (self-contained; inline SVG charts, no external scripts/fonts) |
| `gen_report.py` | generator for `index.html` — every number and chart is produced from the measured data, not typed by hand |

## Reproducing

```bash
python3 gen_report.py   # writes index.html
```

## Verification

`verify_report.py` recomputes every table row from the raw benchmark artefacts (benchmark JSON,
`nsys` CSV exports, and engine-reported metrics), prints the recomputed value beside the reported
one, and counts mismatches. `verification.txt` is the output of the final run: **0 mismatches**
across all grid rows, the kernel-time numbers and the acceptance metrics.

That check corrected three arithmetic statements in an earlier draft (a 4.1x figure that is 3.9x,
a 28% prefill deficit that is 31%, and an "~30x" eager penalty that is 16-21x) and removed three
claims that could not be re-derived from source — including an acceptance comparison whose metric
had only ever been captured from a live container whose logs were not retained. Claims in this
report are restricted to what the preserved artefacts support.
