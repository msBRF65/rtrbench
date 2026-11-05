import struct
import tempfile
import unittest
from pathlib import Path
from convert import convert, WIDTH, HEIGHT


class ConversionFailures(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='srec-converter-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.gt = self.root / 'gt.txt'
        self.gt.write_text('1 0 0 0 0 0 0 1\n')
        self.raw = self.root / 'input.raw'
        self.header = struct.pack('<II', WIDTH, HEIGHT)
        self.frame = self.header + struct.pack('<H', 1000)*(WIDTH*HEIGHT) + self.header + b'\1\2\3'*(WIDTH*HEIGHT)

    def test_structural_errors(self):
        cases = {'truncated_header': b'\x80', 'big_endian_header': struct.pack('>II', WIDTH, HEIGHT),
                 'truncated_payload': self.frame[:-1],
                 'wrong_rgb_size': self.frame[:8+WIDTH*HEIGHT*2] + struct.pack('<II', 1, 1),
                 'extra_frame': self.frame*2, 'no_frames': b''}
        for name, data in cases.items():
            with self.subTest(name=name):
                self.raw.write_bytes(data)
                with self.assertRaises(ValueError):
                    convert(self.raw, self.gt, self.root / name)
                self.assertFalse((self.root / name / 'conversion.json').exists())

    def test_out_of_range_depth_not_clipped(self):
        self.raw.write_bytes(self.header + struct.pack('<H', 13108)*(WIDTH*HEIGHT) +
                             self.header + b'\0'*(WIDTH*HEIGHT*3))
        with self.assertRaisesRegex(ValueError, 'range'):
            convert(self.raw, self.gt, self.root / 'range')

    def test_existing_output_preserved(self):
        self.raw.write_bytes(self.frame)
        output = self.root / 'existing'
        output.mkdir()
        marker = output / 'owned.txt'
        marker.write_text('keep')
        with self.assertRaises(FileExistsError):
            convert(self.raw, self.gt, output)
        self.assertEqual(marker.read_text(), 'keep')

    def test_noninteger_or_invalid_pose_rejected(self):
        for value in ['0.033 0 0 0 0 0 0 1', '1 0 0 0 0 0 0 0', '1 nan 0 0 0 0 0 1']:
            self.gt.write_text(value+'\n')
            with self.assertRaises(ValueError):
                convert(self.raw, self.gt, self.root / 'invalid-gt')


if __name__ == '__main__':
    unittest.main()
