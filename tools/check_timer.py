#!/usr/bin/env python3
"""Check nesting, paused ROI, invalid boundaries and empty-scope timing cost."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import statistics
from measure import ROOT, read_timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New output directory')
    parser.add_argument('--compiler', default='g++')
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for mode, macro in [('baseline', 'RTRBENCH_MEASURE_ROI'),
                        ('instrumented', 'RTRBENCH_MEASURE_LOOPS')]:
        subprocess.run([args.compiler, '-std=c++17', '-O3', '-D' + macro,
                        str(ROOT / 'tools/timer_probe.cpp'), '-o', str(output / mode)], check=True)
    def probe(mode, name, *arguments, check=True):
        env = dict(os.environ, RTRBENCH_TIMING_FILE=str(output / (name + '.csv')))
        return subprocess.run([str(output / mode), *arguments], env=env, check=check,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    probe('instrumented', 'nesting')
    rows = read_timing(output / 'nesting.csv')
    values = {row['region']: int(row['exclusive_ns']) for row in rows}
    # Deliberately loose real-clock bounds tolerate scheduling jitter, while distinguishing
    # exclusive parent (~40ms) from inclusive (~120ms) and excluding the 300ms pause.
    assert 35_000_000 <= values['Parent'] < values['Child']*.9, values
    assert 75_000_000 <= values['Child'] < 180_000_000, values
    assert int(rows[0]['total_roi_ns']) < 250_000_000, values
    assert values['Unattributed ROI'] > 0, values
    assert probe('instrumented', 'invalid', 'invalid', check=False).returncode != 0
    assert not (output / 'invalid.csv').exists()
    overhead = {mode: [] for mode in ('baseline', 'instrumented')}
    for trial in range(7):
        for mode in overhead:
            name = mode + str(trial)
            probe(mode, name, 'overhead')
            overhead[mode].append(int(read_timing(output / (name + '.csv'))[0]['total_roi_ns']))
    report = {'nesting_pause_and_failure_checks': 'PASS', 'empty_scope_iterations': 100000,
              'raw_roi_ns': overhead,
              'median_incremental_ns_per_scope':
                  (statistics.median(overhead['instrumented']) - statistics.median(overhead['baseline'])) / 100000}
    (output / 'checks.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
