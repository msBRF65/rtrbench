#!/usr/bin/env python3
"""Build isolated ROI-only and loop-instrumented binaries, then measure 15 kernels."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = [
    'perception/01.pfl', 'perception/02.ekfslam', 'planning/04.pp2d',
    'planning/05.pp3d', 'planning/06.movtar', 'planning/07-10.robot-arm',
    'planning/11-12.sym-planner', 'control/13.dmp', 'control/14.mpc',
    'control/15.cem', 'control/16.bo',
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log, env=None):
    with log.open('w') as stream:
        subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def build(output, mode, compiler, jobs):
    binary_root = output / 'build' / mode
    macro = {'baseline': 'RTRBENCH_MEASURE_ROI', 'instrumented': 'RTRBENCH_MEASURE_LOOPS', 'default': None}[mode]
    for directory in DIRECTORIES:
        target = binary_root / directory
        target.mkdir(parents=True)
        command = ['make', '-C', str(ROOT / directory), '-j', str(jobs),
                   'CXX=' + compiler + (' -D' + macro if macro else ''),
                   'BIN_DIR=' + str(target), 'OBJ_DIR=' + str(target / 'obj')]
        print('Build', mode, directory, flush=True)
        run(command, target / 'build.log')
    return binary_root


def read_timing(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('Empty timing file: ' + str(path))
    totals = {int(row['total_roi_ns']) for row in rows}
    if len(totals) != 1 or sum(int(row['exclusive_ns']) for row in rows) != next(iter(totals)):
        raise ValueError('Exclusive accounting failed: ' + str(path))
    if next(iter(totals)) <= 0:
        raise ValueError('No measurable ROI: ' + str(path))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New output directory')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--warmups', type=int, default=1)
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--compiler', default='g++')
    args = parser.parse_args()
    if args.repeats < 2 or args.warmups < 0 or args.jobs < 1:
        parser.error('Need repeats >=2, warmups >=0, jobs >=1')
    output = args.out.resolve()
    if any(char.isspace() for char in str(output)) or any(char.isspace() for char in str(ROOT)):
        parser.error('GNU make build paths must not contain whitespace')
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        'platform': platform.platform(), 'python': platform.python_version(),
        'compiler': subprocess.check_output([args.compiler, '--version'], text=True),
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'repeats': args.repeats, 'warmups': args.warmups,
        'clock': 'steady_clock main-thread wall nanoseconds inside existing zsim ROIs',
        'flags': '-std=c++17 -O3 plus kernel Makefile flags; opt-in macro only',
        'source_sha256': {}, 'input_sha256': {}, 'binary_sha256': {},
        'results': [],
    }
    for path in sorted(ROOT.rglob('*')):
        if path.is_file() and (path.suffix in ('.cpp', '.h', '.hpp', '.py', '.json') or path.name in ('Makefile', 'makefile.rules', 'run.sh')):
            manifest['source_sha256'][str(path.relative_to(ROOT))] = sha256(path)
    binaries = {mode: build(output, mode, args.compiler, args.jobs)
                for mode in ('baseline', 'instrumented')}
    for mode, binary_root in binaries.items():
        for path in binary_root.rglob('*.out'):
            manifest['binary_sha256'][str(path.relative_to(output))] = sha256(path)
    samples = []
    # Interleave the two builds to limit systematic warmup/temperature ordering bias.
    for trial in range(-args.warmups, args.repeats):
        order = ('baseline', 'instrumented') if trial % 2 == 0 else ('instrumented', 'baseline')
        results = {}
        for mode in order:
            destination = output / (f'warmup{-trial}' if trial < 0 else f'trial{trial}') / mode
            destination.parent.mkdir(exist_ok=True)
            env = dict(os.environ, RTRBENCH_BINARY_ROOT=str(binaries[mode]))
            start = time.monotonic()
            print('Run', trial, mode, flush=True)
            run(['bash', str(ROOT / 'run.sh'), '--no-evaluation', '--skip', '03.srec', '--output-dir', str(destination)],
                destination.parent / (mode + '.log'), env)
            manifest['results'].append({'trial': trial, 'mode': mode,
                                        'suite_process_wall_s': time.monotonic()-start})
            with (destination / 'summary.tsv').open() as stream:
                summary = list(csv.DictReader(stream, delimiter='\t'))
            if sum(row['status'] == 'PASS' for row in summary) != 15:
                raise ValueError('Expected exactly 15 successful kernels')
            results[mode] = {}
            for row in summary:
                if row['status'] != 'PASS':
                    continue
                kernel = row['kernel']
                directory = destination / kernel
                results[mode][kernel] = sha256(directory / 'result.txt')
                for link in directory.glob('input-*'):
                    manifest['input_sha256'][kernel + '/' + link.name] = sha256(link)
                for timing in read_timing(directory / 'loops.csv'):
                    if trial >= 0:
                        samples.append(dict(kernel=kernel, mode=mode, trial=trial, **timing))
            if mode == order[-1] and results['baseline'] != results['instrumented']:
                raise ValueError('Baseline/instrumented result bytes differ')
        manifest['results'][-1]['paired_result_bytes_equal'] = True
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with (output / 'samples.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(samples[0]))
        writer.writeheader()
        writer.writerows(samples)
    print('Verified 15 kernels per run; exact paired output bytes; samples:', output / 'samples.csv')


if __name__ == '__main__':
    main()
