#!/usr/bin/env python3
"""Decode the little-endian SLAMBench scene2raw stream into SREC preprocessing input."""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import zlib

WIDTH, HEIGHT = 640, 480
GT_NAME = 'livingRoom2.gt.freiburg'
INTRINSICS = {'width': WIDTH, 'height': HEIGHT,
              'intrinsic_matrix': [481.2, 0, 0, 0, 480.0, 0, 319.5, 239.5, 1]}


def load_indices(path):
    indices = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        values = [float(value) for value in line.split()]
        if len(values) != 8 or not all(math.isfinite(value) for value in values):
            raise ValueError(f'GT line {line_number}: expected eight finite values')
        index = int(values[0])
        if index < 0 or index != values[0] or (indices and index <= indices[-1]):
            raise ValueError('GT timestamps must be strictly increasing nonnegative integer frame IDs')
        if abs(sum(value*value for value in values[4:]) - 1) > .001:
            raise ValueError(f'GT line {line_number}: quaternion must have unit norm')
        indices.append(index)
    if not indices:
        raise ValueError('Empty ground truth')
    return indices


def png(path, pixels, channels, bits):
    """Write lossless PNG using only the standard library, with filter zero per row."""
    stride = WIDTH * channels * (bits // 8)
    scanlines = b''.join(b'\0' + pixels[start:start+stride]
                         for start in range(0, len(pixels), stride))
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    header = struct.pack('>IIBBBBB', WIDTH, HEIGHT, bits, 0 if channels == 1 else 2, 0, 0, 0)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) +
                     chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))


def convert(raw, gt, output):
    indices = load_indices(gt)
    # A new directory is the transaction boundary. Partial output is kept for diagnosis,
    # but only a successful conversion writes the complete manifest.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'depth').mkdir()
    (output / 'rgb').mkdir()
    digest = hashlib.sha256()
    frames = []
    with raw.open('rb') as stream:
        def read(count, description):
            data = stream.read(count)
            digest.update(data)
            if len(data) != count:
                raise ValueError('Truncated raw ' + description)
            return data
        while True:
            header = stream.read(8)
            digest.update(header)
            if not header:
                break
            if len(header) != 8 or struct.unpack('<II', header) != (WIDTH, HEIGHT):
                raise ValueError('Expected little-endian 640x480 depth header')
            if len(frames) >= len(indices):
                raise ValueError('More raw frames than GT poses')
            depth_bytes = read(WIDTH*HEIGHT*2, 'depth payload')
            if struct.unpack('<II', read(8, 'RGB header')) != (WIDTH, HEIGHT):
                raise ValueError('RGB dimensions do not match depth')
            rgb = read(WIDTH*HEIGHT*3, 'RGB payload')
            depth = array('H')
            depth.frombytes(depth_bytes)
            if sys.byteorder != 'little':
                depth.byteswap()
            if max(depth) > 65535//5:
                raise ValueError('Depth exceeds lossless 16-bit PNG range at 5000 units/metre')
            scaled = array('H', (value*5 for value in depth))
            if sys.byteorder == 'little':
                scaled.byteswap()  # PNG samples are big endian.
            index = indices[len(frames)]
            png(output / 'depth' / f'{index}.png', scaled.tobytes(), 1, 16)
            png(output / 'rgb' / f'{index}.png', rgb, 3, 8)
            frames.append({'index': index, 'depth_mm_min': min(depth), 'depth_mm_max': max(depth),
                           'raw_depth_sha256': hashlib.sha256(depth_bytes).hexdigest(),
                           'raw_rgb_sha256': hashlib.sha256(rgb).hexdigest()})
    if len(frames) != len(indices):
        raise ValueError('Raw frame count differs from GT pose count')
    shutil.copyfile(gt, output / GT_NAME)
    (output / 'intrinsics.json').write_text(json.dumps(INTRINSICS, indent=2)+'\n')
    manifest = {'complete': True,
                'format_reference': 'https://github.com/pamela-project/slambench1/blob/master/kfusion/thirdparty/scene2raw.cpp', 'format': 'scene2raw little-endian uint2/u16/uint2/RGB8',
                'raw_sha256': digest.hexdigest(), 'gt_sha256': hashlib.sha256(gt.read_bytes()).hexdigest(),
                'depth_scale': 5000, 'depth_conversion': 'PNG16 = stored Z depth in millimetres * 5',
                'frame_indexing': 'raw frames in order matched to integer GT frame IDs',
                'coordinate_convention': 'positive fy after existing preprocess camera/world Y reflection',
                'frames': frames}
    (output / 'conversion.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--gt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New output directory')
    args = parser.parse_args()
    try:
        result = convert(args.raw, args.gt, args.out)
    except (OSError, ValueError, OverflowError) as error:
        parser.exit(1, f'Conversion failed: {error}\n')
    print(f"Converted {len(result['frames'])} frames into {args.out}")


if __name__ == '__main__':
    main()
