# Loop instrumentation

Use Python 3.8+, an existing GCC-compatible C++17 compiler, make, and Bash:

```sh
python3 tools/check_timer.py --out /absolute/path/new-timer-check
python3 tools/measure.py --out /absolute/path/new-measurement --repeats 5 --warmups 1 --jobs 2
python3 evaluation/plot.py /absolute/path/new-measurement/samples.csv --out /absolute/path/new-plots
```

The plotting step needs matplotlib (tested with 3.5.3). `--tables-only` needs only
Python's standard library. Nothing downloads inputs, installs packages, or edits
kernel inputs. Choose fresh output directories outside the checkout. The checkout and measurement
output paths must not contain whitespace because the upstream Makefiles use
space-separated source/object lists. The runner itself still supports spaces. Builds go
under the measurement output, not into the source directories. A failed build or
kernel exits nonzero; build/run logs remain for diagnosis. A fresh command is the
restart procedure, rather than silently mixing partial runs.

`measure.py` uses the root runner's documented representative profiles, excludes
03.srec, and runs the 15 remaining kernels sequentially. Each repetition pairs:

- **baseline:** `RTRBENCH_MEASURE_ROI`, two clock boundaries per ROI, no loop scopes;
- **instrumented:** `RTRBENCH_MEASURE_LOOPS`, the same boundaries plus named scopes.

One warmup pair precedes five measured pairs by default. Mode order alternates.
A new process runs each kernel, preserving the upstream fixed/default RNG seeds.
Every pair must produce **byte-identical `result.txt` files**. Commands, outputs,
raw per-process `loops.csv`, sample CSV, source/input/binary SHA-256 hashes,
compiler/platform settings, warmup count and repetition count are retained.
Warmups are excluded from summary statistics. Process-suite elapsed times include
loading and are provenance only, never the compute bars.

## What is measured

`regions.json` maps each curated loop-containing function or loop region to a
file, symbol, callsite line and processing label. The regions were selected by
reading the compute code (particle/ray loops, matrix updates, graph searches,
configuration interpolation, symbolic actions, basis integration, MPC refinements,
policy samples/fits and Gaussian-process loops). Actual timings rank these regions;
this does not claim exhaustive automatic identification of every C++ loop.

The C++17 `steady_clock` ledger measures **main-thread wall time inside the existing
zsim ROI**, including scheduling delays. It is not CPU time or hardware-counter
sampling. Entering a nested region charges prior time to its parent; subsequent
time belongs only to the child. Every nanosecond is charged once, to the innermost
region or `Unattributed ROI`. The exported sum must equal the ROI total exactly.
This partitions wall time, not a chronological trace of phases.

Existing ROI pauses in CEM/BO exclude their fake physical rollouts, including when
a loop scope spans a pause. Input parsing, output serialization, PRM's existing
pre-ROI graph initialization, and builds remain outside compute ROI. Thus PRM's
bars describe its query, not all offline roadmap preparation. The region call
count includes entries outside the ROI; it is not a timed iteration count.

The default build has all instrumentation compiled out. Optional parallel/OpenMP
modes are not supported by this main-thread ledger; foreign-thread timing use
aborts rather than silently double-counting. Invalid ROI boundaries, unbalanced
scopes, accounting errors and timing-file write failures also fail the run.

`run.sh` supports `RTRBENCH_BINARY_ROOT=/absolute/mirrored/binary/tree` for the
isolated builds; do not combine that setting with `--build`. Each launched kernel
receives `RTRBENCH_TIMING_FILE=<its-result-directory>/loops.csv`. Ordinary binaries
ignore it. No shell-global timing file is shared between kernels.

## Precision and overhead

`check_timer.py` checks nested exclusive scopes, exclusion of a deliberately
paused interval, and failure on a mispaired boundary. Seven empty-scope trials
estimate incremental timing cost relative to ROI-only binaries. This cost is
machine/compiler dependent and should be rerun on a different environment.

Report raw instrumented timings alongside the paired ROI-only baseline, their
means and **population** standard deviations. The observed ratio includes timer
cost, code-layout changes and run noise; it is not an overhead correction or a
speedup result. Tiny kernels/parts may be dominated by instrumentation. A recorded
zero is below clock resolution, not proof of no work. The overview uses one ordinary
compute-ROI bar per benchmark. Each benchmark has one PNG with measured processing
names on the x axis and exclusive time on the y axis, including an Other bar for
ROI time outside named regions. Region bars share a time axis within each chart.
