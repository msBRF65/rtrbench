#!/usr/bin/env python3
"""Check nesting, paused ROI, invalid boundaries and empty-scope timing cost."""
import argparse
import csv
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
    inclusive = {row['region']: int(row['inclusive_ns']) for row in rows
                 if row.get('inclusive_ns')}
    assert inclusive['Parent'] == values['Parent'] + values['Child'], (values, inclusive)
    assert inclusive['Parent'] >= inclusive['Child'] == values['Child']
    assert inclusive['Parent'] + values['Unattributed ROI'] == int(rows[0]['total_roi_ns'])
    assert 'Off-ROI helper' not in values
    with (output / 'nesting.csv.coverage.csv').open() as stream:
        coverage = {row['region']: row for row in csv.DictReader(stream)}
    assert coverage['Off-ROI helper']['status'] == 'outside_roi'
    assert coverage['Off-ROI helper']['entries'] == '2' and coverage['Off-ROI helper']['roi_calls'] == '0'
    probe('instrumented', 'boundary', 'boundary')
    boundary = {row['region']: row for row in read_timing(output / 'boundary.csv')}
    loop = int(boundary['Only the loop']['inclusive_ns'])
    assert 9_000_000 <= loop < 30_000_000, boundary
    assert int(boundary['Unattributed ROI']['exclusive_ns']) > loop*2, boundary
    probe('instrumented', 'bridge', 'bridge')
    bridge = next(row for row in read_timing(output / 'bridge.csv') if row['region'] == 'ROI bridge')
    assert 4_000_000 <= int(bridge['inclusive_ns']) < 20_000_000 and bridge['calls'] == '1', bridge
    probe('instrumented', 'template', 'template')
    template = [row for row in read_timing(output / 'template.csv') if row['region'] == 'Template callsite']
    assert len(template) == 1 and template[0]['calls'] == '2', template
    assert probe('instrumented', 'invalid', 'invalid', check=False).returncode != 0
    assert not (output / 'invalid.csv').exists()
    overhead = {mode: [] for mode in ('baseline', 'instrumented')}
    for trial in range(7):
        for mode in overhead:
            name = mode + str(trial)
            probe(mode, name, 'overhead')
            overhead[mode].append(int(read_timing(output / (name + '.csv'))[0]['total_roi_ns']))
    report = {'nesting_pause_and_failure_checks': 'PASS',
              'inclusive_exclusive_boundary_offROI_template_checks': 'PASS',
              'nested_exclusive_ns': values, 'nested_inclusive_ns': inclusive, 'empty_scope_iterations': 100000,
              'raw_roi_ns': overhead,
              'median_incremental_ns_per_scope':
                  (statistics.median(overhead['instrumented']) - statistics.median(overhead['baseline'])) / 100000}
    (output / 'checks.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
