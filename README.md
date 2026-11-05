# RTRBench

Real-Time Robotics Benchmark (RTRBench) is a collection of 16 robotic kernels.
The kernels span the entire software pipeline of most autonomous robots.
Complete information on the benchmark suite can be found on [this
page](https://cmu-roboarch.github.io/rtrbench/).

## Highlights
- **Performance:** All kernels are implemented with performance as the main
  objective.
- **Easy to Simulate:** All kernels are easy to simulate with
  microarchitectural simulators (no Python runtime, no inter-process
communications, etc). The kernels communicate the regions of interest with the
simulator.
- **No Dependency Hell:** The kernels use few external libraries and all of
  them are included in the repository (no Boost, no Eigen, etc).

## Requirements
RTRBench uses C++17. The following minimum versions are required to build the
benchmarks:
- GCC 8.0
- Clang 5.0
- Visual Studio 15.8

## Build
Every kernel can be built using the following command:
```
$ make
```

### Build for Performance
To build the kernel for the highest performance, use the following command:
```
$ make performance
```

This way, the pieces of the code that are written for the purpose of
verification will be omitted.

### Build for Debug
To build the kernels for debugging them, use the following command:
```
$ make debug
```

### Build & Clean All

Use `build.sh` and `clean.sh` scripts to build and clean *all* of the kernels.

## Run

### Run all 16 kernels

The root runner executes one representative workload per kernel, sequentially:

```bash
./run.sh --build --scene-dir /path/to/preprocessed/living-room
```

It works from any working directory. `--build` builds each shared kernel
directory once with two make jobs; omit it to use existing binaries. Bash 4+
and the build requirements above are needed. GCC 8 additionally needs its
filesystem compatibility library when linking scene reconstruction; use
`MAKEFLAGS='LDFLAGS=-lstdc++fs' ./run.sh --build --scene-dir /path/to/scene`
with that compiler. Make command-line overrides can also be passed through
`MAKEFLAGS`.

Scene reconstruction is the only kernel whose dataset is not included. Follow
[its input documentation](perception/03.srec/README.md), then supply the scene
directory with `--scene-dir`. It must contain `init_transform.txt`, `depth/N.png`,
`rgb/N.png`, and `normal/N-dim1.txt` through `N-dim3.txt` for frames 1 through 10.
Use `--camera FILE` for another camera calibration and `--scene-frames N` to
change the frame range. Missing inputs are reported as failures; the remaining
kernels still run and the overall exit status is nonzero.
If the scene is not available, explicitly run the other 15 kernels with
`./run.sh --build --skip 03.srec`. Its summary row is `SKIP`, not `PASS`.

Useful options:

```bash
./run.sh --list
./run.sh --dry-run                          # Preview all 16 commands; no writes
./run.sh --kernel 07.prm --kernel 08.rrt    # Run selected kernels
./run.sh --skip 03.srec                    # Explicitly omit scene reconstruction
./run.sh --output-dir /path/to/new-results --scene-dir /path/to/scene
./run.sh --help
```

The output directory must be new. By default it is
`results/<timestamp>-<pid>/`. Each kernel gets `command.txt`, `console.log`,
and `result.txt`; build logs and `summary.tsv` are at the output root.
The summary records each process exit code (`-` for an explicit skip). The
runner exits 0 when all non-skipped selected kernels succeed, 1 for any
build/input/process failure, and 2 for an invalid invocation. Inputs are linked
into each result directory under short
relative names because the kernels' argument parser does not support spaces
inside path values. The original input files are not copied or edited.

The representative profile uses the included map/log/problem/trajectory
examples, all four robot-arm planners, and both symbolic planning problems.
It uses 100 particles and 100 updates for PFL, downsampling 10 for scene
reconstruction, 1,000 samples for robot-arm planning (`--arm-samples N` to
change it), 100 seconds of simulated MPC time, and 10 updates/10 samples for
CEM and BO. These are individual kernel runs; use the existing per-kernel
`run_all.sh` scripts below for parameter sweeps.

### Run an individual kernel

To run every kernel, simply issue the following command:
```
$ ./BINARY_NAME ARGS [ARGS]
```

Some of the arguments are required (e.g., input map, etc), and some of them are
optional. To see the description of the arguments, run the following command:
```
$ ./BINARY_NAME --help
```

Alternatively, you can put your desired parameters into the `run_all.sh`
scripts available in the kernels' directories, and simply issue the following
command:
```
$ ./run_all.sh
```

## License
```
Copyright (c) 2022 Carnegie Mellon University

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Compute-loop timing

[tools/README.md](tools/README.md) describes opt-in, exclusive ROI loop measurement
and paired baseline checks for the 15 bundled workloads other than scene
reconstruction. [evaluation/README.md](evaluation/README.md) describes reproducible
PNG timing bar charts, raw statistics, and overhead/precision limits. Normal builds
remain uninstrumented.

### Regenerate scene-reconstruction inputs

[data-gen/README.md](data-gen/README.md) provides a Docker workflow that downloads
the matching small SLAMBench raw/ground-truth pair, converts both real frames into
SREC input, and runs and validates the existing Python preprocessor. Use its
generated calibration and `--scene-frames 2` with the root runner.

### Automatic timing evaluation

`./run.sh --build --skip 03.srec` also produces timing PNGs and a report
**automatically** in `results/YYYYMMDD-HHMMSS-PID/evaluation/`. The selected
benchmarks each run once. `--build` is optional in this evaluation mode: isolated
loop-instrumented binaries/objects are built under that invocation's `build/`
directory, once per shared kernel directory. Ordinary binaries/objects are not
reused or overwritten. Builds and input loading are outside the plotted compute ROI.

Automatic plots need **Python 3.7+ and matplotlib 3.5+** in the same interpreter.
Use `--python /path/to/python` (or `RTRBENCH_PYTHON`) to select that environment.
Dependencies are checked before building or creating output; nothing is installed
automatically. `--dry-run`, `--list`, and `--help` require no plotting dependency.

```sh
./run.sh --skip 03.srec                         # One timed invocation + automatic PNGs/report
./run.sh --kernel 13.dmp --python python3.11     # Selected workload; choose plotting Python
./run.sh --no-evaluation --build --skip 03.srec  # Original C++-only build/run workflow
```

The evaluation folder contains `benchmark-times.png`, one `<benchmark>.png` per
successful timed benchmark (including `Other`), `REPORT.md`, raw `samples.csv` and
statistical CSVs. One run means `n=1`, population std=0 by definition, and no
run-to-run variability measurement. No baseline is run automatically: baseline
and overhead columns show N/A. The separate paired-repeat measurement workflow
remains available in [tools/README.md](tools/README.md).

Failed/skipped kernels are listed and excluded from plots rather than assigned
zero time. Missing/invalid timing on a successful process makes evaluation fail;
other valid results remain visible. The runner continues selected kernels and
exits nonzero for any kernel or evaluation failure. `evaluation.log`, per-kernel
logs and `summary.tsv` remain alongside the evaluation folder.

Use `--output-dir /path/to/new-results` to place the complete run elsewhere.
Existing output is refused. Instrumented GNU make paths cannot contain whitespace;
ordinary `--no-evaluation` runs retain support for output paths with spaces.
All generated default results remain ignored by Git, including CSVs and reports.
To reuse existing **instrumented** binaries, set `RTRBENCH_BINARY_ROOT` to a previous
run's absolute `build/` path without `--build`; ordinary uninstrumented binaries
will fail evaluation because their timing files are missing.

Scene reconstruction still needs its prepared inputs; use `--skip 03.srec` when
unavailable. With a real prepared scene and calibration, its existing ROI is
measured as `Other` only: no named SREC loop regions are claimed. See
[evaluation/README.md](evaluation/README.md) for the generated figures and limits.

To evaluate **all 16 together**, first prepare the two-frame scene with the
[data-generation workflow](data-gen/README.md), then run without `--skip`:

```sh
./run.sh --build --scene-dir /absolute/path/srec-output/scene \
  --camera /absolute/path/srec-output/scene/intrinsics.json --scene-frames 2
```

The same timestamped evaluation directory then contains the overview plus all 16
benchmark PNGs. SREC contributes its measured compute ROI as `Other`, using the
same real raw-derived inputs as its standalone workflow.
