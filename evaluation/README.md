# Timing evaluation

Run `plot.py SAMPLES.csv --out NEW_DIRECTORY` after `tools/measure.py` (see
[measurement instructions](../tools/README.md)). Python 3.8+ and matplotlib are
required for figures; `--tables-only` uses the standard library.

Outputs:

- `benchmark-times.png`: one ordinary bar per benchmark, mean compute-ROI wall
  time on the y axis and benchmark name on the x axis;
- `<benchmark>.png`: one chart per benchmark, measured processing names on the
  x axis and exclusive time on a shared y axis, with population-standard-deviation
  whiskers and an `Other` bar for ROI time outside the named regions;
- `regions.csv`: n, mean and population std for every measured part, both modes;
- `roi-and-overhead.csv`: per-benchmark ROI means/std and observed instrumented
  change relative to the ROI-only baseline;
- `REPORT.md`: readable results and interpretation limits.

Figures are PNG only: 15 benchmark charts and one overview. Region values are
written above their bars in milliseconds. `Other` is the recorded `Unattributed
ROI` category; named exclusive regions plus Other account for the entire ROI.
Each benchmark uses a single linear time axis, preserving relative durations.
The overview measures compute ROI, not input loading, build time or full-process
elapsed time. No zero-duration bar is enlarged into positive time.

Generated result CSVs and Markdown reports stay local and are not versioned.
Generate your own samples with `tools/measure.py`, then produce figures and
tables with:

```sh
python3 evaluation/plot.py /absolute/path/new-measurement/samples.csv --out /absolute/path/new-plots
```

The [checked provenance](example/manifest.json) records GCC 8.5.0 on an AMD Ryzen
Threadripper 9970X. Its recorded git head is the base commit; source SHA-256
entries identify the instrumented working-tree contents. Hashes are validation
records used to identify matching code, inputs and binaries; they are not timing
measurements. They may remain in a measurement work directory while a delivery
folder contains just the PNGs, result tables and readable report. Timing artifacts
are machine-specific observations, not performance guarantees.
