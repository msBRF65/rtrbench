#!/usr/bin/env python3
"""Turn this run.sh invocation's successful timing files into local evaluation outputs."""
import argparse
import csv
from pathlib import Path
import sys
from plot import evaluate

FIELDS = ['kernel', 'mode', 'trial', 'region', 'file', 'line', 'calls', 'exclusive_ns', 'total_roi_ns']


def preflight():
    if sys.version_info < (3, 7):
        raise ValueError('Automatic evaluation needs Python 3.7 or newer')
    try:
        import matplotlib
        if tuple(int(part) for part in matplotlib.__version__.split('.')[:2]) < (3, 5):
            raise ValueError('Automatic evaluation needs matplotlib 3.5 or newer')
        matplotlib.use('Agg')
        import matplotlib.pyplot
    except ImportError as error:
        raise ValueError('Automatic evaluation needs matplotlib. Select its Python with --python PATH, '
                         'or use --no-evaluation for benchmark-only execution.') from error


def read_timing(path):
    with path.open() as stream:
        reader = csv.DictReader(stream)
        expected = {'region', 'file', 'line', 'calls', 'exclusive_ns', 'total_roi_ns'}
        if set(reader.fieldnames or []) != expected:
            raise ValueError('Unexpected timing CSV columns')
        rows = list(reader)
    if not rows:
        raise ValueError('Empty timing file')
    if any(set(row) != expected or any(value is None for value in row.values()) for row in rows):
        raise ValueError('Malformed timing CSV row')
    regions = [row['region'] for row in rows]
    if len(set(regions)) != len(regions) or regions.count('Unattributed ROI') != 1:
        raise ValueError('Expected distinct named regions and exactly one unattributed ROI')
    totals = {int(row['total_roi_ns']) for row in rows}
    elapsed = [int(row['exclusive_ns']) for row in rows]
    if len(totals) != 1 or next(iter(totals)) <= 0 or any(value < 0 for value in elapsed):
        raise ValueError('Expected nonnegative parts and one positive ROI total')
    if sum(elapsed) != next(iter(totals)):
        raise ValueError('Exclusive region sum differs from ROI total')
    for row in rows:
        if int(row['calls']) < 0 or int(row['line']) < 0:
            raise ValueError('Negative call count or source line')
    return rows


def collect(results):
    output = results / 'evaluation'
    output.mkdir(exist_ok=False)
    with (results / 'summary.tsv').open() as stream:
        statuses = list(csv.DictReader(stream, delimiter='\t'))
    samples, errors, status_lines = [], [], []
    for status in statuses:
        kernel = status['kernel']
        if status['status'] != 'PASS':
            status_lines.append(f"| {kernel} | {status['status']} | Excluded; no timing inferred |")
            continue
        try:
            rows = read_timing(results / kernel / 'loops.csv')
            samples.extend(dict(kernel=kernel, mode='instrumented', trial=0, **row) for row in rows)
            detail = 'ROI only; no named loop regions' if len(rows) == 1 else 'Named regions plus Other'
            status_lines.append(f'| {kernel} | PASS | {detail}; n=1 |')
        except (OSError, ValueError, KeyError, csv.Error) as error:
            errors.append(kernel + ': ' + str(error))
            status_lines.append(f'| {kernel} | PASS | Timing ERROR; excluded |')
    with (output / 'samples.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(samples)
    if samples:
        try:
            evaluate(samples, output)
        except Exception as error:
            errors.append('Plot/report generation: ' + str(error))
    report = output / 'REPORT.md'
    if not report.exists():
        report.write_text('# Run evaluation\n\nNo successful, valid timed benchmarks to plot.\n')
    with report.open('a') as stream:
        stream.write('\n## This invocation\n\nOne process per selected benchmark; no warmups or baseline runs.\n'
                     'Failed/skipped benchmarks and invalid timing files are excluded from figures, not assigned zero time.\n\n'
                     '| Benchmark | Execution | Evaluation |\n|---|---|---|\n' + '\n'.join(status_lines) + '\n')
        if errors:
            stream.write('\n## Evaluation errors\n\n' + '\n'.join('- ' + error for error in errors) + '\n')
    for error in errors:
        print('Evaluation error:', error, file=sys.stderr)
    print('Evaluation:', output)
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path, nargs='?')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    try:
        preflight()
        if args.preflight:
            return 0
        if args.results is None:
            parser.error('results directory is required')
        return collect(args.results.resolve())
    except (OSError, ValueError, KeyError, csv.Error) as error:
        print('Evaluation failed:', error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
