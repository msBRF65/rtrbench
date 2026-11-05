#!/usr/bin/env python3
"""Aggregate exclusive ROI samples and draw absolute-time stacked bars and details."""
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


def plot(summary, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    rows = [row for row in summary if row['mode'] == 'instrumented']
    kernels = sorted({row['kernel'] for row in rows})
    names = sorted({row['region'] for row in rows})
    palette = plt.get_cmap('tab20')
    colors = {name: palette(i % 20) if i < 20 else plt.get_cmap('Set3')(i-20)
              for i, name in enumerate(names)}
    colors['Unattributed ROI'] = '#bbbbbb'
    values = {(row['kernel'], row['region']): row['mean_ms'] for row in rows}
    fig, ax = plt.subplots(figsize=(19, 10))
    bottoms = [0.0]*len(kernels)
    maximum = max(sum(values.get((kernel, name), 0) for name in names) for kernel in kernels)
    for name in names:
        heights = [values.get((kernel, name), 0) for kernel in kernels]
        ax.bar(kernels, heights, bottom=bottoms, label=name, color=colors[name], width=.75)
        for index, height in enumerate(heights):
            # A linear time axis cannot display microseconds next to seconds legibly.
            # Center labels only where they fit; every positive part has its own labeled
            # absolute-time detail panel below, without inflating the overview segments.
            if height > maximum*.035:
                ax.text(index, bottoms[index]+height/2, textwrap.fill(name, 16),
                        ha='center', va='center', fontsize=7)
            bottoms[index] += height
    ax.set_ylabel('Exclusive ROI wall time (ms; mean of measured repetitions)')
    ax.set_xlabel('Benchmark (03.srec excluded)')
    ax.set_title('Measured loop regions — absolute-time stacked overview')
    ax.tick_params(axis='x', rotation=45)
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=8)
    ax.grid(axis='y', alpha=.2)
    fig.tight_layout()
    for extension in ('svg', 'png'):
        fig.savefig(output / ('stacked.' + extension), dpi=180)
    plt.close(fig)
    # Region-specific axes preserve actual time units and give every positive block a
    # centered processing label, including tiny parts invisible on the global axis.
    for kernel in kernels:
        parts = sorted([row for row in rows if row['kernel'] == kernel],
                       key=lambda row: row['mean_ms'], reverse=True)
        fig, axes = plt.subplots(1, len(parts), figsize=(max(8, len(parts)*2.5), 5), squeeze=False)
        for ax, part in zip(axes[0], parts):
            mean, std = part['mean_ms'], part['population_std_ms']
            ax.bar([0], [mean], color=colors[part['region']], width=.75)
            if mean > 0:
                ax.text(0, mean/2, textwrap.fill(part['region'], 17), ha='center', va='center', fontsize=9)
                ax.errorbar([0], [mean], yerr=[std], color='black', capsize=4, fmt='none')
            else:
                ax.text(.5, .5, 'Below clock resolution\n(not proven zero work)',
                        transform=ax.transAxes, ha='center', va='center', fontsize=9)
            ax.set_xlim(-.6, .6)
            ax.set_ylim(0, max((mean+std)*1.2, 1e-6))
            ax.set_xticks([0], [kernel])
            ax.set_ylabel('Exclusive wall time (ms)')
            ax.set_title(f'{mean:.6g} ± {std:.2g} ms', fontsize=9)
            ax.grid(axis='y', alpha=.2)
        fig.suptitle(kernel + ': regions ranked by mean time (independent y scales; ± population std)')
        fig.tight_layout()
        for extension in ('svg', 'png'):
            fig.savefig(output / (kernel + '.' + extension), dpi=160)
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
    lines += ['', 'The linear stacked overview does not enlarge tiny segments. Centered processing labels for every positive measured part appear in the benchmark detail plots, with independent absolute-time axes and standard-deviation whiskers.',
              'regions.csv ranks the measured loop-containing regions. This is curated source instrumentation, not exhaustive automatic detection of every C++ loop. Source file/symbol coverage is in tools/regions.json and the raw samples retain callsites.',
              'Each chart describes these bundled representative inputs, not a general comparison of algorithm performance. Very short regions can be dominated by timing overhead; zero-resolution observations do not prove zero work.']
    (args.out / 'REPORT.md').write_text('\n'.join(lines)+'\n')
    if not args.tables_only:
        plot(summary, args.out)


if __name__ == '__main__':
    main()
