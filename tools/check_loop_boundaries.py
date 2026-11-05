#!/usr/bin/env python3
"""Check that each declared benchmark timer surrounds exactly its recorded loop."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    regions = json.loads((ROOT / 'tools/regions.json').read_text())
    declared = set()
    for region in regions:
        lines = (ROOT / region['file']).read_text().splitlines()
        timer, start, end = (region[key] for key in ('line', 'loop_start_line', 'loop_end_line'))
        assert lines[timer-1].strip() == 'RTRBENCH_LOOP("'+region['label']+'");', region
        assert lines[timer-2].strip() == '{' and start == timer+1, region
        assert re.match(r'(for|while)\s*\(', lines[start-1].strip()), region
        assert lines[end].strip() == '}', region  # Timer scope closes immediately after the loop.
        declared.add((region['file'], timer))
    actual = set()
    for name in {region['file'] for region in regions}:
        for number, line in enumerate((ROOT / name).read_text().splitlines(), 1):
            if re.search(r'\bRTRBENCH_LOOP\(', line):
                actual.add((name, number))
    assert actual == declared, (actual-declared, declared-actual)
    print(f'{len(regions)} actual loop boundaries verified; no function-scope benchmark timers')


if __name__ == '__main__':
    main()
