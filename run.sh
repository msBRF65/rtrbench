#!/usr/bin/env bash
# Run one representative workload for each of RTRBench's 16 kernels.
set -u

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
KERNELS=(01.pfl 02.ekfslam 03.srec 04.pp2d 05.pp3d 06.movtar
         07.prm 08.rrt 09.rrtstar 10.rrtpp 11.sym-blkw 12.sym-fext
         13.dmp 14.mpc 15.cem 16.bo)
SELECTED=()
SKIPPED=()
BUILD=false
DRY_RUN=false
JOBS=2
ARM_SAMPLES=1000
SCENE_FRAMES=10
SCENE_DIR="$ROOT/perception/03.srec/living-room"
CAMERA="$ROOT/perception/03.srec/camera1.json"
OUTPUT=""
declare -A BUILD_STATUS=()

usage() {
    cat <<'EOF'
Usage: ./run.sh [options]
Run all 16 kernels sequentially, once each, using the bundled example inputs.

  --build               Build selected kernels before running (once per directory)
  --jobs N              Parallel make jobs per build directory (default: 2)
  --kernel NAME         Run only NAME; repeat to select several kernels
  --skip NAME           Explicitly skip NAME; repeat to skip several kernels
  --scene-dir DIR       Preprocessed scene for 03.srec (not bundled upstream)
  --camera FILE         Scene camera intrinsics (default: camera1.json)
  --scene-frames N       Scene frames 1..N (default: 10, downsample factor 10)
  --arm-samples N        Samples for robot-arm planners (default: 1000)
  --output-dir DIR      New directory for all logs/results (default: results/TIMESTAMP-PID)
  --dry-run             Print commands without building, running or creating files
  --list                List kernel names
  -h, --help            Show this help
EOF
}

fail_usage() {
    printf 'Error: %s\n' "$1" >&2
    usage >&2
    exit 2
}

while (($#)); do
    case "$1" in
        --build) BUILD=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --list) printf '%s\n' "${KERNELS[@]}"; exit 0 ;;
        -h|--help) usage; exit 0 ;;
        --jobs|--kernel|--skip|--scene-dir|--camera|--scene-frames|--arm-samples|--output-dir)
            (($# >= 2)) && [[ -n "$2" ]] || fail_usage "$1 requires a value"
            case "$1" in
                --jobs) JOBS=$2 ;;
                --kernel) SELECTED+=("$2") ;;
                --skip) SKIPPED+=("$2") ;;
                --scene-dir) SCENE_DIR=$2 ;;
                --camera) CAMERA=$2 ;;
                --scene-frames) SCENE_FRAMES=$2 ;;
                --arm-samples) ARM_SAMPLES=$2 ;;
                --output-dir) OUTPUT=$2 ;;
            esac
            shift 2 ;;
        *) fail_usage "unknown option: $1" ;;
    esac
done

for value in "$JOBS" "$SCENE_FRAMES" "$ARM_SAMPLES"; do
    [[ "$value" =~ ^[1-9][0-9]*$ ]] || fail_usage "jobs, frames and samples must be positive integers"
done
if ((${#SELECTED[@]} == 0)); then SELECTED=("${KERNELS[@]}"); fi
for name in "${SELECTED[@]}" "${SKIPPED[@]}"; do
    found=false
    for known in "${KERNELS[@]}"; do
        if [[ "$name" == "$known" ]]; then found=true; break; fi
    done
    "$found" || fail_usage "unknown kernel: $name (use --list)"
done

# Resolve user paths against the caller, not a kernel's working directory.
[[ "$SCENE_DIR" == /* ]] || SCENE_DIR="$PWD/$SCENE_DIR"
[[ "$CAMERA" == /* ]] || CAMERA="$PWD/$CAMERA"
[[ -n "$OUTPUT" ]] || OUTPUT="$ROOT/results/$(date +%Y%m%d-%H%M%S)-$$"
[[ "$OUTPUT" == /* ]] || OUTPUT="$PWD/$OUTPUT"

is_skipped() {
    local name=$1 skip_name
    for skip_name in "${SKIPPED[@]}"; do
        if [[ "$name" == "$skip_name" ]]; then return 0; fi
    done
    return 1
}

configure_kernel() {
    local name=$1
    ARGS=()
    REQUIRED=()
    case "$name" in
        01.pfl)
            DIRECTORY=perception/01.pfl; BINARY=pfl.out
            REQUIRED=("$ROOT/$DIRECTORY/input-maps/wean.dat" "$ROOT/$DIRECTORY/input-measurements/log1.txt")
            ARGS=("--map=${REQUIRED[0]}" "--measurements=${REQUIRED[1]}" --particles=100 --subsample=5 --updates=100) ;;
        02.ekfslam)
            DIRECTORY=perception/02.ekfslam; BINARY=ekfslam.out
            REQUIRED=("$ROOT/$DIRECTORY/input-logs/data.txt")
            ARGS=("--log=${REQUIRED[0]}") ;;
        03.srec)
            DIRECTORY=perception/03.srec; BINARY=srec.out
            REQUIRED=("$CAMERA" "$SCENE_DIR/init_transform.txt")
            for ((frame=1; frame<=SCENE_FRAMES; frame++)); do
                REQUIRED+=("$SCENE_DIR/depth/$frame.png" "$SCENE_DIR/rgb/$frame.png")
                for dimension in 1 2 3; do
                    REQUIRED+=("$SCENE_DIR/normal/$frame-dim$dimension.txt")
                done
            done
            ARGS=("--path=$SCENE_DIR" "--camera=$CAMERA" --start_idx=1 "--end_idx=$SCENE_FRAMES" --downsample=10) ;;
        04.pp2d)
            DIRECTORY=planning/04.pp2d; BINARY=pp2d.out
            REQUIRED=("$ROOT/$DIRECTORY/input-maps/Boston_0_1024.map")
            ARGS=("--map=${REQUIRED[0]}" --grid=4 --weight=1 --heuristic=Euclidean --scale-map=1 --scale-robot=1) ;;
        05.pp3d)
            DIRECTORY=planning/05.pp3d; BINARY=pp3d.out
            REQUIRED=("$ROOT/$DIRECTORY/input-maps/freiburg.map")
            ARGS=("--map=${REQUIRED[0]}" --weight=1 --heuristic=Euclidean) ;;
        06.movtar)
            DIRECTORY=planning/06.movtar; BINARY=movtar.out
            REQUIRED=("$ROOT/$DIRECTORY/input-maps/map.txt")
            ARGS=("--map=${REQUIRED[0]}") ;;
        07.prm|08.rrt|09.rrtstar|10.rrtpp)
            DIRECTORY=planning/07-10.robot-arm; BINARY=robot_arm.out
            case "$name" in
                07.prm) planner=PRM ;; 08.rrt) planner=RRT ;;
                09.rrtstar) planner=RRTStar ;; 10.rrtpp) planner=RRTPostProc ;;
            esac
            REQUIRED=("$ROOT/$DIRECTORY/input-maps/Map-C.txt" "$ROOT/$DIRECTORY/input-cfgs/Map-C_cfgs.txt")
            ARGS=("--map=${REQUIRED[0]}" "--config=${REQUIRED[1]}" "--planner=$planner"
                  --epsilon=0.21 --radius=2.1 "--samples=$ARM_SAMPLES" --weight=1 --bias=0.05 --iterations=100) ;;
        11.sym-blkw|12.sym-fext)
            DIRECTORY=planning/11-12.sym-planner; BINARY=sym_planner.out
            if [[ "$name" == 11.sym-blkw ]]; then problem=Blocks; else problem=FireExtinguisher; fi
            REQUIRED=("$ROOT/$DIRECTORY/input-problems/$problem.txt")
            ARGS=("--input=${REQUIRED[0]}" --weight=1) ;;
        13.dmp)
            DIRECTORY=control/13.dmp; BINARY=dmp.out
            REQUIRED=("$ROOT/$DIRECTORY/input-trajs/path1.traj" "$ROOT/$DIRECTORY/input-trajs/path1.weights")
            ARGS=("--trajectory=${REQUIRED[0]}" "--weights=${REQUIRED[1]}" --dt=0.1) ;;
        14.mpc)
            DIRECTORY=control/14.mpc; BINARY=mpc.out
            REQUIRED=("$ROOT/$DIRECTORY/input-spcourses/sp_course1.txt")
            ARGS=("--input=${REQUIRED[0]}" --time=100 --tick=0.2 --dist=1.5 --iters=3 --neighbors=10 --sspeed=0.1389 --tspeed=2.7778) ;;
        15.cem|16.bo)
            if [[ "$name" == 15.cem ]]; then DIRECTORY=control/15.cem; BINARY=cem.out
            else DIRECTORY=control/16.bo; BINARY=bo.out; fi
            REQUIRED=("$ROOT/$DIRECTORY/simulator.txt")
            ARGS=("--simulator=${REQUIRED[0]}" --updates=10 --samples=10 --topn=5) ;;
    esac
    # The kernels' argument parser cannot read path values containing spaces.
    # Relative symlinks keep caller/input/output paths independent of that parser.
    COMMAND=("${RTRBENCH_BINARY_ROOT:-$ROOT}/$DIRECTORY/$BINARY")
    LINK_NAMES=()
    LINK_SOURCES=()
    for argument in "${ARGS[@]}"; do
        value=${argument#*=}
        if [[ "$value" == /* ]]; then
            option=${argument%%=*}
            link_name="input-${option#--}"
            LINK_NAMES+=("$link_name")
            LINK_SOURCES+=("$value")
            COMMAND+=("$option=$link_name")
        else
            COMMAND+=("$argument")
        fi
    done
    COMMAND+=(--output=result.txt)
}

print_command() {
    printf '%q ' "$@"
    printf '\n'
}

run_kernel() {
    local name=$1 input index
    configure_kernel "$name"
    if "$BUILD" && [[ ! ${BUILD_STATUS[$DIRECTORY]+present} ]]; then
        if make -C "$ROOT/$DIRECTORY" -j "$JOBS" > "$OUTPUT/build-${DIRECTORY//\//-}.log" 2>&1; then
            BUILD_STATUS[$DIRECTORY]=0
        else
            BUILD_STATUS[$DIRECTORY]=$?
        fi
    fi
    if "$BUILD" && [[ ${BUILD_STATUS[$DIRECTORY]} != 0 ]]; then
        printf 'Build failed for %s; see build log\n' "$DIRECTORY" >&2
        return "${BUILD_STATUS[$DIRECTORY]}"
    fi
    if [[ ! -x ${COMMAND[0]} ]]; then
        printf 'Missing executable: %s (use --build)\n' "${COMMAND[0]}" >&2
        return 127
    fi
    for input in "${REQUIRED[@]}"; do
        if [[ ! -f "$input" || ! -r "$input" ]]; then
            printf 'Missing readable input: %s\n' "$input" >&2
            if [[ "$name" == 03.srec ]]; then printf 'Supply a preprocessed scene with --scene-dir; see perception/03.srec/README.md\n' >&2; fi
            return 1
        fi
    done
    mkdir -p "$OUTPUT/$name" || return 1
    for index in "${!LINK_NAMES[@]}"; do
        ln -s -- "${LINK_SOURCES[$index]}" "$OUTPUT/$name/${LINK_NAMES[$index]}" || return 1
    done
    print_command "${COMMAND[@]}" > "$OUTPUT/$name/command.txt"
    (cd -- "$OUTPUT/$name" && RTRBENCH_TIMING_FILE="$OUTPUT/$name/loops.csv" "${COMMAND[@]}")
}

if "$DRY_RUN"; then
    for name in "${SELECTED[@]}"; do
        if is_skipped "$name"; then
            printf '%s: SKIP (requested with --skip)\n' "$name"
            continue
        fi
        configure_kernel "$name"
        printf '%s: ' "$name"
        print_command "${COMMAND[@]}"
    done
    exit 0
fi

[[ ! -e "$OUTPUT" ]] || fail_usage "output directory already exists: $OUTPUT"
mkdir -p "$OUTPUT" || exit 1
printf 'kernel\tstatus\texit_code\tconsole_log\n' > "$OUTPUT/summary.tsv"
passed=0
failed=0
skipped=0
for name in "${SELECTED[@]}"; do
    printf '[%d/%d] %s\n' "$((passed + failed + skipped + 1))" "${#SELECTED[@]}" "$name"
    mkdir -p "$OUTPUT/$name" || exit 1
    if is_skipped "$name"; then
        printf 'Explicitly skipped with --skip\n' > "$OUTPUT/$name/console.log"
        printf '%s\tSKIP\t-\t%s\n' "$name" "$OUTPUT/$name/console.log" >> "$OUTPUT/summary.tsv"
        ((skipped+=1))
        printf '  SKIP (requested with --skip)\n'
        continue
    fi
    if run_kernel "$name" > "$OUTPUT/$name/console.log" 2>&1; then
        status=PASS; code=0; ((passed+=1))
    else
        code=$?; status=FAIL; ((failed+=1))
    fi
    printf '%s\t%s\t%s\t%s\n' "$name" "$status" "$code" "$OUTPUT/$name/console.log" >> "$OUTPUT/summary.tsv"
    printf '  %s\n' "$status"
done
printf '%d passed; %d failed; %d skipped. Results: %s\n' "$passed" "$failed" "$skipped" "$OUTPUT"
((failed == 0))
