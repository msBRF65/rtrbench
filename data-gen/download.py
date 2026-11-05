#!/usr/bin/env python3
"""Download the two specified public SLAMBench inputs with pinned SHA-256 checks."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

BASE = ('https://cknowledge.org/repo/web.php?template=cknowledge&action=pull&common_func=yes'
        '&cid=8a7141c59cd335f5:c28d813042b30dea&filename=')
FILES = {
    'livingRoom2.gt.freiburg': '8da0020de904afe386b6743ecee8a8644adfb293c159f880feab36ec6ec3e2f4',
    'living_room_traj2_loop_small.raw': '2ac6e54e53e19debf6129c6d304a51f7d990af3ed7abce68dce53c6b00336c82',
}


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        if not new_url.startswith("https://"):
            raise ValueError("Refusing non-HTTPS redirect")
        return super().redirect_request(request, response, code, message, headers, new_url)


def download(output):
    output.mkdir(parents=True, exist_ok=False)
    opener = urllib.request.build_opener(HTTPSOnlyRedirect())
    for name, expected in FILES.items():
        digest = hashlib.sha256()
        partial = output / (name + '.part')
        with opener.open(BASE + name, timeout=60) as response, partial.open('xb') as stream:
            if not response.url.startswith('https://'):
                raise ValueError('Download redirected outside HTTPS')
            while True:
                data = response.read(1024*1024)
                if not data:
                    break
                digest.update(data)
                stream.write(data)
        if digest.hexdigest() != expected:
            raise ValueError('SHA-256 mismatch: ' + name)
        partial.rename(output / name)
        print('Verified', name, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New download directory')
    args = parser.parse_args()
    try:
        download(args.out)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Download failed: {error}\n')
