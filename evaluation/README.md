# Timing evaluation

Run `plot.py SAMPLES.csv --out NEW_DIRECTORY` after `tools/measure.py` (see
[measurement instructions](../tools/README.md)). Python 3.8+ and matplotlib are
required for figures; `--tables-only` uses the standard library.

Outputs:

- `stacked.svg` / `stacked.png`: all 15 benchmarks, absolute mean exclusive ROI
  milliseconds on the y axis, benchmark on the x axis, color per measured part;
- `<benchmark>.svg` / `.png`: ranked processing blocks with centered labels,
  independent absolute-time axes and population-standard-deviation whiskers;
- `regions.csv`: n, mean and population std for every measured part, both modes;
- `roi-and-overhead.csv`: per-benchmark ROI means/std and observed instrumented
  change relative to the ROI-only baseline;
- `REPORT.md`: readable results and interpretation limits.

A single linear overview cannot legibly label microsecond segments beside a
second-long kernel. Only labels that fit are placed in that overview; the detail
plots show every positive segment without enlarging its contribution to the
stacked total. No zero-duration segment is drawn as positive time.

The [checked example](example/REPORT.md) includes raw samples, aggregate tables and
source/input/binary provenance from GCC 8.5.0 on an AMD Ryzen Threadripper 9970X.
Regenerate its figures with:

```sh
python3 evaluation/plot.py evaluation/example/samples.csv --out /absolute/path/new-example-plots
```

The recorded git head is the base commit; source SHA-256 entries identify the
instrumented working-tree contents used for the example. Timing artifacts are
machine-specific observations, not performance guarantees.
