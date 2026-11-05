#!/usr/bin/env python3
"""Independently check every decoded pixel and the real preprocessing outputs."""
import argparse
import json
from pathlib import Path
import struct
import numpy as np
import open3d as o3d
from convert import WIDTH, HEIGHT, load_indices


def validate(raw, gt, scene):
    if not __debug__:
        raise RuntimeError("Validation needs assertions enabled; unset PYTHONOPTIMIZE")
    indices = load_indices(gt)
    assert (scene / 'livingRoom2.gt.freiburg').read_bytes() == gt.read_bytes(), 'GT bytes changed'
    summary = []
    with raw.open('rb') as stream:
        for index in indices:
            assert struct.unpack('<II', stream.read(8)) == (WIDTH, HEIGHT)
            expected_depth = np.frombuffer(stream.read(WIDTH*HEIGHT*2), dtype='<u2').reshape(HEIGHT, WIDTH)
            assert struct.unpack('<II', stream.read(8)) == (WIDTH, HEIGHT)
            expected_rgb = np.frombuffer(stream.read(WIDTH*HEIGHT*3), dtype='u1').reshape(HEIGHT, WIDTH, 3)
            depth = np.asarray(o3d.io.read_image(str(scene / 'depth' / f'{index}.png')))
            rgb = np.asarray(o3d.io.read_image(str(scene / 'rgb' / f'{index}.png')))
            assert depth.dtype == np.uint16 and depth.shape == (HEIGHT, WIDTH)
            assert np.array_equal(depth.astype('u4'), expected_depth.astype('u4')*5), 'Depth pixel mismatch'
            assert np.array_equal(rgb, expected_rgb), 'RGB pixel mismatch'
            normals = np.stack([np.loadtxt(scene / 'normal' / f'{index}-dim{channel}.txt')
                                for channel in (1, 2, 3)], axis=-1)
            assert normals.shape == (HEIGHT, WIDTH, 3) and np.isfinite(normals).all()
            assert np.abs(normals).max() <= 1.01 and np.any(normals != 0), 'Invalid normal map'
            summary.append({'index': index, 'depth_pixels_exact': WIDTH*HEIGHT,
                            'rgb_channels_exact': WIDTH*HEIGHT*3, 'normal_values_finite': normals.size})
        assert stream.read(1) == b'', 'Unexpected raw remainder'
    # Independent xyzw quaternion-to-matrix formula, with the existing camera/world Y reflection.
    first = next(line for line in gt.read_text().splitlines() if line.strip() and not line.startswith('#'))
    values = list(map(float, first.split()))
    x, y, z, w = values[4:]
    norm = x*x+y*y+z*z+w*w
    rotation = np.array([[1-2*(y*y+z*z)/norm, 2*(x*y-z*w)/norm, 2*(x*z+y*w)/norm],
                         [2*(x*y+z*w)/norm, 1-2*(x*x+z*z)/norm, 2*(y*z-x*w)/norm],
                         [2*(x*z-y*w)/norm, 2*(y*z+x*w)/norm, 1-2*(x*x+y*y)/norm]])
    expected = np.eye(4)
    expected[:3, :3] = rotation
    expected[:3, 3] = values[1:4]
    reflection = np.diag([1, -1, 1, 1])
    assert np.allclose(np.loadtxt(scene / 'init_transform.txt'), reflection @ expected @ reflection, atol=1e-12)
    intrinsic = o3d.io.read_pinhole_camera_intrinsic(str(scene / 'intrinsics.json'))
    assert intrinsic.width == WIDTH and intrinsic.height == HEIGHT
    assert np.allclose(intrinsic.intrinsic_matrix, [[481.2, 0, 319.5], [0, 480, 239.5], [0, 0, 1]])
    return {'result': 'PASS', 'frames': summary, 'pose_and_intrinsics': 'PASS',
            'note': 'All stored depth/RGB samples checked; original radial floating-point depths are irrecoverable.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--gt', type=Path, required=True)
    parser.add_argument('--scene', type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.raw, args.gt, args.scene)
    (args.scene / 'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
