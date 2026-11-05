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
