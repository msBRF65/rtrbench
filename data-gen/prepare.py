#!/usr/bin/env python3
"""Convert downloaded raw frames, then invoke the repository's real preprocessor."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from convert import convert, GT_NAME

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, default=Path('/inputs'))
    parser.add_argument('--out', type=Path, required=True, help='New output scene directory')
    args = parser.parse_args()
    output = args.out.resolve()
    try:
        convert(args.inputs / 'living_room_traj2_loop_small.raw', args.inputs / GT_NAME, output)
        subprocess.run([sys.executable, str(ROOT / 'perception/03.srec/preprocess.py'),
                        str(output), '--intrinsics', str(output / 'intrinsics.json')],
                       check=True, env=dict(os.environ, MPLBACKEND='Agg'))
        subprocess.run([sys.executable, str(ROOT / 'data-gen/validate.py'),
                        '--raw', str(args.inputs / 'living_room_traj2_loop_small.raw'),
                        '--gt', str(args.inputs / GT_NAME), '--scene', str(output)], check=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Preparation failed: {error}\n')
    (output / 'PREPROCESS_COMPLETE').write_text('Real preprocess.py completed successfully\n')
    print('Prepared scene:', output)


if __name__ == '__main__':
    main()
