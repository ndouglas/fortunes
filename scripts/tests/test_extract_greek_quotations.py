import os
import sys
import unittest

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(THIS_DIR)
sys.path.insert(0, SCRIPT_DIR)

import extract_greek_quotations as egq


class TestReadEpubXhtml(unittest.TestCase):
    def test_returns_two_xhtml_strings(self):
        # Use a synthetic EPUB built at test time to avoid hard-coding a user path.
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("OEBPS/html/09_Quotations.xhtml", "<html>main</html>")
            z.writestr("OEBPS/html/10_1.xhtml", "<html>appendix</html>")
        buf.seek(0)

        main, appendix = egq.read_epub_xhtml(buf)
        self.assertIn("main", main)
        self.assertIn("appendix", appendix)


if __name__ == "__main__":
    unittest.main()
