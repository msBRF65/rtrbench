# Timing evaluation

The root `run.sh` invokes evaluation automatically after its selected benchmarks:

```sh
./run.sh --build --skip 03.srec
```

Open `results/YYYYMMDD-HHMMSS-PID/evaluation/REPORT.md` and `benchmark-times.png`.
Use `--output-dir NEW_DIRECTORY` for another run location, `--python PATH` for the
Python environment, or `--no-evaluation` for the original benchmark-only workflow.
Automatic evaluation needs Python 3.7+ and matplotlib 3.5+, checked before builds.
Dry-run does not import matplotlib or create files.

`collect.py` reads **that invocation's** `summary.tsv` and successful `loops.csv`
files. It checks the schema, nonnegative exclusive durations, unique regions,
unattributed ROI and exact sum to a positive ROI total. Missing/invalid timing
fails evaluation; failed/skipped benchmark processes are excluded explicitly.
The default builds have loop instrumentation enabled in isolated run-local build
folders. The collector never substitutes historical samples or fabricated zeros.

Outputs inside the run's `evaluation/` directory:

- `benchmark-times.png`: one ordinary bar per successful timed benchmark;
- `<benchmark>.png`: measured processing names on the x axis, exclusive time on
  one shared y axis, and `Other` for ROI time outside named regions;
- `samples.csv`: this invocation's raw instrumented rows, trial 0;
- `regions.csv`: n, mean and population std for each processing region;
- `roi-and-overhead.csv`: ROI statistics; baseline/overhead fields are empty when
  no baseline was measured (N/A in the report);
- `REPORT.md`: statistics, execution/evaluation status and limitations.

One process per benchmark means n=1 and population std=0, **not** a variability
estimate. There is no automatic warmup, baseline or repeated campaign. SREC can
use its existing ROI when real inputs are supplied, but its chart is `Other` only;
no named loop details are implied. An all-skipped run produces a status report
and empty sample table, without fake zero-duration figures.

Figures are PNG only, with region values in milliseconds above their bars.
Named exclusive regions plus Other account for the full compute ROI. Build/input
loading/output and paused physical rollouts are outside that ROI. The overview
shows compute time, not full-process latency. No zero-duration bar is enlarged.

## Optional repeated measurements

The existing paired workflow remains available for variability/overhead analysis:

```sh
python3 tools/measure.py --out /absolute/path/new-measurement --repeats 5 --warmups 1
python3 evaluation/plot.py /absolute/path/new-measurement/samples.csv --out /absolute/path/new-plots
```

The measurement driver uses `run.sh --no-evaluation` internally to avoid recursive
plots and preserve its explicit baseline/instrumented repetition plan. Standalone
`plot.py` accepts both paired and instrumented-only sample tables; `--tables-only`
uses Python's standard library. Actual figures require matplotlib.

Generated result CSVs, PNGs and Markdown reports stay local in ignored `results/`;
source READMEs remain versioned. For a custom output location inside the checkout,
ignore it separately or keep it outside the checkout. The historical
[provenance record](example/manifest.json) identifies an earlier paired measurement,
and is never substituted for samples from the current run.

```sh
python3 -m unittest discover -s evaluation -p 'test_*.py' -v
```
