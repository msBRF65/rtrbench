import csv
from pathlib import Path
import tempfile
import unittest
from collect import collect, read_timing
from plot import aggregate, evaluate


def sample(mode='instrumented', trial=0, elapsed=2000000):
    return dict(kernel='13.dmp', mode=mode, trial=trial, region='Unattributed ROI',
                file='', line=0, calls=0, exclusive_ns=elapsed, total_roi_ns=elapsed)


class EvaluationChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='run-evaluation-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_single_run_has_no_invented_baseline(self):
        _, roi = aggregate([sample()])
        self.assertEqual(roi[0]['n'], 1)
        self.assertEqual(roi[0]['instrumented_population_std_ms'], 0)
        self.assertIsNone(roi[0]['baseline_mean_ms'])
        self.assertIsNone(roi[0]['observed_change_percent'])
        evaluate([sample()], self.root, tables_only=True)
        report = (self.root / 'REPORT.md').read_text()
        self.assertIn('N/A', report)
        self.assertIn('does not measure run-to-run variability', report)

    def test_paired_population_statistics_preserved(self):
        rows = [sample(mode, trial, elapsed) for mode in ('baseline', 'instrumented')
                for trial, elapsed in enumerate((1000000, 3000000))]
        _, roi = aggregate(rows)
        self.assertEqual(roi[0]['instrumented_mean_ms'], 2)
        self.assertEqual(roi[0]['baseline_population_std_ms'], 1)
        self.assertEqual(roi[0]['instrumented_population_std_ms'], 1)
        self.assertEqual(roi[0]['observed_change_percent'], 0)

    def test_three_trial_inclusive_elapsed_is_not_a_partition(self):
        rows = []
        for trial in range(3):
            parent = dict(sample(trial=trial, elapsed=40000000), region='Parent',
                          inclusive_ns=120000000, total_roi_ns=121000000)
            child = dict(sample(trial=trial, elapsed=80000000), region='Child',
                         inclusive_ns=80000000, total_roi_ns=121000000)
            other = dict(sample(trial=trial, elapsed=1000000), inclusive_ns='', total_roi_ns=121000000)
            rows.extend((parent, child, other))
        summary, roi = aggregate(rows)
        parts = {row['region']: row for row in summary}
        self.assertEqual(parts['Parent']['inclusive_n'], 3)
        self.assertEqual(parts['Parent']['inclusive_mean_ms'], 120)
        self.assertEqual(parts['Parent']['mean_ms'], 40)
        self.assertEqual(parts['Parent']['inclusive_population_std_ms'], 0)
        self.assertGreater(sum(row['inclusive_mean_ms'] or 0 for row in summary),
                           roi[0]['instrumented_mean_ms'])
        self.assertIsNone(parts['Unattributed ROI']['inclusive_mean_ms'])

    def test_missing_inclusive_and_unobserved_trials_are_not_inferred(self):
        rows = [dict(sample(trial=0, elapsed=1000000), region='Loop', inclusive_ns=1000000),
                sample(trial=1, elapsed=1000000), sample(trial=2, elapsed=1000000)]
        summary, roi = aggregate(rows)
        loop = next(row for row in summary if row['region'] == 'Loop')
        self.assertEqual(roi[0]['n'], 3)
        self.assertEqual(loop['n'], 1)
        self.assertEqual(loop['inclusive_n'], 1)
        legacy, _ = aggregate([sample()])
        self.assertIsNone(legacy[0]['inclusive_mean_ms'])
        evaluate(rows, self.root, tables_only=True)
        self.assertIn('| 1/3 | 1 |', (self.root/'REPORT.md').read_text())

    def test_inclusive_smaller_than_exclusive_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Inclusive'):
            aggregate([dict(sample(), region="Loop", inclusive_ns=1)])

    def test_invalid_accounting_rejected(self):
        for rows in ([sample(elapsed=-1)], [dict(sample(), total_roi_ns=3)], [sample(), sample()]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                aggregate(rows)
        with self.assertRaisesRegex(ValueError, 'No instrumented'):
            aggregate([sample(mode='baseline')])

    def test_raw_negative_parts_cannot_cancel(self):
        path = self.root / 'loops.csv'
        rows = [sample(elapsed=-1), dict(sample(elapsed=2000001), region='Other named loop')]
        with path.open('w', newline='') as stream:
            fields = ['region', 'file', 'line', 'calls', 'exclusive_ns', 'total_roi_ns']
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows([{key: (2000000 if key == 'total_roi_ns' else row[key])
                              for key in fields} for row in rows])
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            read_timing(path)

    def test_success_without_csv_fails_evaluation(self):
        (self.root / 'summary.tsv').write_text('kernel\tstatus\texit_code\tconsole_log\n13.dmp\tPASS\t0\tconsole.log\n')
        self.assertEqual(collect(self.root), 1)
        report = (self.root / 'evaluation/REPORT.md').read_text()
        self.assertIn('Timing ERROR', report)
        self.assertFalse(list((self.root / 'evaluation').glob('*.png')))

    def test_skipped_and_failed_are_not_zero_bars(self):
        (self.root / 'summary.tsv').write_text('kernel\tstatus\texit_code\tconsole_log\n03.srec\tSKIP\t-\tlog\n13.dmp\tFAIL\t127\tlog\n')
        self.assertEqual(collect(self.root), 0)
        report = (self.root / 'evaluation/REPORT.md').read_text()
        self.assertIn('No successful, valid timed benchmarks', report)
        self.assertIn('FAIL', report)
        self.assertFalse(list((self.root / 'evaluation').glob('*.png')))
        with self.assertRaises(FileExistsError):
            collect(self.root)


if __name__ == '__main__':
    unittest.main()
