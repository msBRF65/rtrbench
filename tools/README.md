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

`regions.json` maps 44 actual `for`/`while` sites to source headers and end lines.
Each timing scope starts immediately before the complete loop and closes immediately
after it, including its loop control and calls. Function setup, enclosing decisions,
allocation outside the loop and post-loop cleanup are excluded from that loop's
interval. They remain in Other unless another selected loop covers them. A
straight-line weighted-fusion expression is not a loop and has no invented timer.
`check_loop_boundaries.py` verifies the declared scope/header/end alignment.

The clocks measure main-thread `steady_clock` wall time inside the **existing zsim
ROIs**, including scheduling delays. They are not CPU cycles or instruction counts.
Two distinct values are retained:

- `inclusive_ns`: the complete target-loop interval, including nested selected
  loops and called functions. It is summed over that loop's invocations in the
  process. Nested inclusive intervals overlap and **must not be summed as an ROI
  partition**. This is not a per-iteration average.
- `exclusive_ns`: only intervals where this target is the innermost active selected
  scope. Exclusive values plus `Unattributed ROI` exactly partition each ROI trial.
  Other has no inclusive-loop value; its inclusive field is blank.

A logical clock advances only during active ROI segments, so CEM/BO fake physical
rollout pauses remain excluded even when a loop spans a pause. Input loading,
output serialization, PRM offline graph construction and initial pre-ROI GP training
remain outside the existing compute contract. Helpers such as depth unprojection
can therefore be reached only outside ROI: they are **not measured**, not timed zero.

Numeric loop CSV rows contain only ROI-overlap invocations. `calls` counts those
invocations, not loop iterations. The companion `loops.csv.coverage.csv` records
all reached scope `entries`, `roi_calls`, and `measured`/`outside_roi` status. A scope
never reached has no registration metadata; the static manifest still lists it.
Missing observations must not be filled with fabricated zero durations. Templates
sharing one source callsite are registered once. A loop with zero body iterations
can still have measured initialization/condition-check time.

Default builds compile clocks out. Optional parallel/OpenMP modes remain unsupported
by this main-thread ledger; foreign-thread use aborts rather than double-counts.
Invalid boundaries, unbalanced scopes, accounting errors and file write failures
fail the process.

`run.sh` supports `RTRBENCH_BINARY_ROOT=/absolute/mirrored/binary/tree` for isolated
builds; do not combine it with `--build`. Each kernel receives its own
`RTRBENCH_TIMING_FILE`. Older CSVs without `inclusive_ns` can still be read, but the
missing elapsed metric is explicitly unavailable and is never inferred from exclusive
time. A mixed legacy/new plot labels legacy bars as exclusive-only.

## Precision and overhead

`check_timer.py` checks nested inclusive/exclusive scopes, exclusion of a deliberately
paused interval, function setup outside a loop, ROI-spanning scopes, template
registration, outside-ROI metadata and failure on a mispaired boundary. Seven empty-scope trials
estimate incremental timing cost relative to ROI-only binaries. This cost is
machine/compiler dependent and should be rerun on a different environment.

Report raw instrumented timings alongside the paired ROI-only baseline, their
means and **population** standard deviations. The observed ratio includes timer
cost, code-layout changes and run noise; it is not an overhead correction or a
speedup result. Tiny kernels/parts may be dominated by instrumentation. A recorded
zero is below clock resolution, not proof of no work. The overview uses one ordinary
compute-ROI bar per benchmark. Each benchmark has one PNG with measured processing
names on the x axis and inclusive loop elapsed on the y axis, including an exclusive Other bar for
ROI time outside named regions. Region bars share a time axis within each chart.

## Root runner integration

The root `run.sh` now defaults to a single timed process per selected benchmark and
automatic local PNG/report generation. Use `--no-evaluation` for the original
benchmark-only mode. This paired-repeat driver explicitly passes that flag for
its internal invocations, so it does not recursively trigger extra plots or builds.
The root runner's ordinary automatic path does not run this repeated experiment.
