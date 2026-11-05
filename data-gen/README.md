# Recover the SREC sample from SLAMBench raw data

This prepares the two-frame public `living_room_traj2_loop_small.raw` sample and
its matching `livingRoom2.gt.freiburg` for the **existing**
`perception/03.srec/preprocess.py`. The supplied sample contains exactly two
640×480 frames (IDs 1 and 2); it is not the full living-room trajectory.

From the repository root:

```sh
docker build -f data-gen/Dockerfile -t rtrbench-srec-data .
mkdir -p /absolute/path/srec-output
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v /absolute/path/srec-output:/output rtrbench-srec-data
```

`/absolute/path/srec-output/scene` must not already exist. The Docker build installs
the pinned direct preprocessing dependencies and downloads **both** inputs over
HTTPS with pinned SHA-256 verification. A changed download or failed request fails
the build; it does not proceed with an HTML error page. No dataset is committed to
the repository. On hosts where the buildx client cannot create its lock, the same
build can use `DOCKER_BUILDKIT=0` without changing Docker credentials/configuration.

The container streams the raw conversion, invokes the real repository preprocessor,
and independently checks every depth/RGB sample, all normal-map dimensions/finite
values, calibration and the initial ground-truth pose. Only successful completion
writes `scene/PREPROCESS_COMPLETE`. `conversion.json` records input hashes, frame
IDs, depth ranges and format provenance; `validation.json` records the checks.
Partial failures retain their output for diagnosis. Retry into a **new** directory;
existing files are never silently replaced.

For an existing environment (Python 3.8+ for conversion; the pinned requirements
use Python 3.11), the steps are explicit:

```sh
python3 data-gen/download.py --out /absolute/path/new-inputs
python3 data-gen/prepare.py --inputs /absolute/path/new-inputs --out /absolute/path/new-scene
# Or conversion alone, without third-party Python packages:
python3 data-gen/convert.py \
  --raw /absolute/path/new-inputs/living_room_traj2_loop_small.raw \
  --gt /absolute/path/new-inputs/livingRoom2.gt.freiburg --out /absolute/path/another-new-scene
# Then, with preprocessing dependencies installed:
python3 perception/03.srec/preprocess.py /absolute/path/another-new-scene \
  --intrinsics /absolute/path/another-new-scene/intrinsics.json
python3 data-gen/validate.py \
  --raw /absolute/path/new-inputs/living_room_traj2_loop_small.raw \
  --gt /absolute/path/new-inputs/livingRoom2.gt.freiburg --scene /absolute/path/another-new-scene
```

Run the scene through the root runner with its generated calibration and **two**
frames, rather than the runner's ten-frame default:

```sh
./run.sh --build --kernel 03.srec \
  --scene-dir /absolute/path/srec-output/scene \
  --camera /absolute/path/srec-output/scene/intrinsics.json --scene-frames 2
```

GCC 8 may need the documented `MAKEFLAGS='LDFLAGS=-lstdc++fs'` linker override.
The existing C++ kernel's 8-bit image-loading path reduces 16-bit depth precision;
this converter preserves the stored raw depth exactly for Python preprocessing,
not a claim of lossless end-to-end C++ reconstruction or reconstruction accuracy.

## Format and coordinate conventions

The format reference is PAMELA/SLAMBench's MIT-licensed
[scene2raw.cpp](https://github.com/pamela-project/slambench1/blob/master/kfusion/thirdparty/scene2raw.cpp)
(blob `c5ce84fec8de242a94ef6ed6cc1c61ac77c39aa7`; copyright 2014 Universities of
Edinburgh, Imperial College and Manchester). This is an independent decoder of
that format, not a copy of its implementation. Original dataset terms remain
with [ICL-NUIM](https://www.doc.ic.ac.uk/~ahanda/VaFRIC/iclnuim.html) and the source
archive; the source-code license does not relicense the downloaded data.

For this x86-generated sample, each frame is:

1. Little-endian unsigned 32-bit width and height (640, 480).
2. 640×480 little-endian uint16 **Z depth in millimetres**.
3. Another little-endian uint32 width/height pair (640, 480).
4. 640×480 packed RGB uint8 triples, row-major, with no alpha or row padding.

There is no global header, timestamp or frame count. The native-endian producer
has no endianness marker; this decoder explicitly supports the supplied
little-endian 640×480 layout and rejects other dimensions/byte orders. Both frame
headers, payload lengths, final remainder and raw/GT frame counts are checked.

`scene2raw` computes Z from radial depth and truncates it to integer millimetres.
That floating-point information is **irrecoverable**. The decoder does not apply
the radial-to-Z transform a second time: it writes `PNG16 = stored_Z_mm × 5`, so
`preprocess.py`'s division by 5000 recovers stored Z in metres exactly. Zero stays
zero. Values above 13107 mm are rejected instead of overflowing/clipping PNG16.
RGB channels are preserved byte-for-byte.

Raw frames are paired, in order, with strictly increasing integer GT frame IDs;
this sample's first raw frame becomes `depth/1.png` and `rgb/1.png`. Fractional TUM
timestamps are rejected rather than silently truncated into duplicate filenames.
The original GT bytes and xyzw quaternion order are retained. Preprocessing
continues to convert xyzw to wxyz and applies its existing camera/world Y reflection
`F T F`, `F=diag(1,-1,1,1)`. Consequently the generated calibration has fx=481.2,
**positive** fy=480, cx=319.5, cy=239.5 and size640×480. Existing camera1.json is
untouched. The preprocessor now accepts explicit `--intrinsics` and scalar H×W
depth images returned by modern Open3D, while retaining H×W×1 support.

## Sources and checks

Both source URLs share:
`https://cknowledge.org/repo/web.php?template=cknowledge&action=pull&common_func=yes&cid=8a7141c59cd335f5:c28d813042b30dea&filename=`

| Filename | Bytes | SHA-256 |
|---|---:|---|
| living_room_traj2_loop_small.raw | 3072032 | 2ac6e54e53e19debf6129c6d304a51f7d990af3ed7abce68dce53c6b00336c82 |
| livingRoom2.gt.freiburg | 93 | 8da0020de904afe386b6743ecee8a8644adfb293c159f880feab36ec6ec3e2f4 |

```sh
python3 -m unittest discover -s data-gen -p 'test_*.py' -v
```

These fixture checks cover malformed/truncated headers and payloads, frame-count
mismatches, out-of-range depth, invalid GT and existing-output preservation. They
supplement the real two-frame pipeline and all-pixel validation; they do not
substitute synthetic data for the downloaded sample. Docker's direct dependency
versions are pinned; record the built image ID and `pip freeze` for the resolved
transitive environment when reproducing results.
