#!/usr/bin/env python3
"""Aggregate exclusive ROI samples and draw PNG time bars for benchmarks and regions."""
import argparse
import collections
import csv
import json
from pathlib import Path
import statistics
import textwrap


def aggregate(samples):
    groups = collections.defaultdict(list)
    totals = {}
    for row in samples:
        key = row['kernel'], row['mode'], row['region']
        groups[key].append(int(row['exclusive_ns']) / 1e6)
        trial = row['kernel'], row['mode'], row['trial']
        value = int(row['total_roi_ns']) / 1e6
        if trial in totals and totals[trial] != value:
            raise ValueError('Inconsistent total per trial')
        totals[trial] = value
    summary = []
    for (kernel, mode, region), values in sorted(groups.items()):
        summary.append(dict(kernel=kernel, mode=mode, region=region, n=len(values),
                            mean_ms=statistics.mean(values), population_std_ms=statistics.pstdev(values)))
    roi = []
    for kernel in sorted({key[0] for key in totals}):
        modes = {mode: [value for (name, m, _), value in totals.items()
                        if name == kernel and m == mode] for mode in ('baseline', 'instrumented')}
        means = {mode: statistics.mean(values) for mode, values in modes.items()}
        roi.append(dict(kernel=kernel, n=len(modes['instrumented']),
                        baseline_mean_ms=means['baseline'],
                        baseline_population_std_ms=statistics.pstdev(modes['baseline']),
                        instrumented_mean_ms=means['instrumented'],
                        instrumented_population_std_ms=statistics.pstdev(modes['instrumented']),
                        observed_change_percent=100*(means['instrumented']/means['baseline']-1)))
    return summary, roi


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(summary, roi, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    rows = [row for row in summary if row['mode'] == 'instrumented']
    kernels = sorted({row['kernel'] for row in rows})
    names = sorted({row['region'] for row in rows})
    colors = {name: plt.get_cmap('tab20')(index % 20)
              for index, name in enumerate(names)}
    colors['Unattributed ROI'] = '#bbbbbb'

    # The overview has one ordinary bar per benchmark, without region stacking.
    totals = {row['kernel']: row for row in roi}
    fig, ax = plt.subplots(figsize=(15, 6))
    means = [totals[kernel]['instrumented_mean_ms'] for kernel in kernels]
    errors = [totals[kernel]['instrumented_population_std_ms'] for kernel in kernels]
    ax.bar(kernels, means, yerr=errors, capsize=3, color='#4477aa')
    ax.set_ylabel('Compute ROI wall time (ms; mean ± population std)')
    ax.set_xlabel('Benchmark (03.srec excluded)')
    ax.set_title('Benchmark execution time inside the compute ROI')
    ax.tick_params(axis='x', rotation=45)
    ax.grid(axis='y', alpha=.2)
    fig.tight_layout()
    fig.savefig(output / 'benchmark-times.png', dpi=180)
    plt.close(fig)

    # One shared time axis and one PNG per benchmark. Other is always shown,
    # including a genuine zero, so the chart accounts for the complete ROI.
    for kernel in kernels:
        parts = sorted([row for row in rows if row['kernel'] == kernel
                        and row['region'] != 'Unattributed ROI'],
                       key=lambda row: row['mean_ms'], reverse=True)
        other = next(row for row in rows if row['kernel'] == kernel
                     and row['region'] == 'Unattributed ROI')
        parts.append(other)
        labels = [textwrap.fill('Other' if row['region'] == 'Unattributed ROI'
                                else row['region'], 22) for row in parts]
        means = [row['mean_ms'] for row in parts]
        errors = [row['population_std_ms'] for row in parts]
        fig, ax = plt.subplots(figsize=(max(8, len(parts)*2.2), 6))
        positions = list(range(len(parts)))
        ax.bar(positions, means, yerr=errors, capsize=4,
               color=[colors[row['region']] for row in parts])
        for index, (mean, std) in enumerate(zip(means, errors)):
            ax.annotate(f'{mean:.6g}', (index, mean+std), xytext=(0, 5),
                        textcoords='offset points', ha='center', fontsize=9)
        ax.set_xticks(positions, labels)
        ax.set_ylim(0, max(max(mean+std for mean, std in zip(means, errors))*1.2, 1e-6))
        ax.set_ylabel('Exclusive compute ROI wall time (ms; mean ± population std)')
        ax.set_xlabel('Measured processing region; Other = ROI outside named regions')
        ax.set_title(kernel + ': time by processing region')
        ax.grid(axis='y', alpha=.2)
        fig.tight_layout()
        fig.savefig(output / (kernel + '.png'), dpi=180)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('samples', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tables-only', action='store_true', help='No matplotlib needed')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    with args.samples.open() as stream:
        samples = list(csv.DictReader(stream))
    summary, roi = aggregate(samples)
    write_csv(args.out / 'regions.csv', summary)
    write_csv(args.out / 'roi-and-overhead.csv', roi)
    lines = ['# Loop timing results', '',
             'Times are main-thread wall time inside existing compute ROIs; paused rollouts, input loading and builds are excluded.',
             'Parts are exclusive: inner regions replace parent time; unattributed ROI is retained. Means and population standard deviations are in milliseconds.',
             'Negative baseline-to-instrumented changes reflect run noise and code-layout effects, not negative timer cost or a speedup.', '',
             '| Benchmark | n | ROI-only baseline mean ± std (ms) | Instrumented mean ± std (ms) | Observed change |',
             '|---|---:|---:|---:|---:|']
    for row in roi:
        lines.append('| {kernel} | {n} | {baseline_mean_ms:.6g} ± {baseline_population_std_ms:.3g} | {instrumented_mean_ms:.6g} ± {instrumented_population_std_ms:.3g} | {observed_change_percent:+.1f}% |'.format(**row))
    lines += ['', 'benchmark-times.png shows one ordinary mean compute-ROI bar per benchmark. Each benchmark PNG shows region names on one shared time axis, with Other for all ROI time outside the named regions. Whiskers show population standard deviation; values above bars are milliseconds. Only PNG figures are produced.',
              'regions.csv ranks the measured loop-containing regions. This is curated source instrumentation, not exhaustive automatic detection of every C++ loop. Source file/symbol coverage is in tools/regions.json and the raw samples retain callsites.',
              'Each chart describes these bundled representative inputs, not a general comparison of algorithm performance. Very short regions can be dominated by timing overhead; zero-resolution observations do not prove zero work.']
    (args.out / 'REPORT.md').write_text('\n'.join(lines)+'\n')
    if not args.tables_only:
        plot(summary, roi, args.out)


if __name__ == '__main__':
    main()
