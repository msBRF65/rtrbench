import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from download import FILES, HTTPSOnlyRedirect, download


class DownloadFailures(unittest.TestCase):
    def test_changed_payload_is_not_published(self):
        response = io.BytesIO(b'not the pinned dataset')
        response.url = 'https://example.invalid/sample'
        with tempfile.TemporaryDirectory(prefix='srec-download-') as directory:
            output = Path(directory) / 'inputs'
            with patch('download.urllib.request.build_opener') as opener:
                opener.return_value.open.return_value = response
                with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                    download(output)
            name = next(iter(FILES))
            self.assertFalse((output / name).exists())
            self.assertTrue((output / (name+'.part')).exists())

    def test_http_redirect_rejected(self):
        with self.assertRaisesRegex(ValueError, 'non-HTTPS'):
            HTTPSOnlyRedirect().redirect_request(None, None, 302, '', {}, 'http://example.invalid')


if __name__ == '__main__':
    unittest.main()
