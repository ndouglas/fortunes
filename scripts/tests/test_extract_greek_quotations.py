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


class TestTitleCaseAuthor(unittest.TestCase):
    def test_single_name(self):
        self.assertEqual(egq.title_case_author("AESCHYLUS"), "Aeschylus")

    def test_two_names(self):
        self.assertEqual(
            egq.title_case_author("AESCHINES SOCRATICUS"),
            "Aeschines Socraticus",
        )

    def test_keeps_short_words_lowercase(self):
        self.assertEqual(
            egq.title_case_author("DIONYSIUS OF HALICARNASSUS"),
            "Dionysius of Halicarnassus",
        )

    def test_first_word_capitalized_even_if_short(self):
        self.assertEqual(egq.title_case_author("OF COURSE"), "Of Course")

    def test_strips_whitespace(self):
        self.assertEqual(egq.title_case_author("  PLATO  "), "Plato")

    def test_collapses_internal_whitespace(self):
        self.assertEqual(
            egq.title_case_author("ADAMANTIUS    JUDAEUS"),
            "Adamantius Judaeus",
        )


import xml.etree.ElementTree as ET

XHTML_NS = "{http://www.w3.org/1999/xhtml}"


def _p(xml_fragment):
    """Parse a single <p> element in the xhtml namespace."""
    wrapped = f'<p xmlns="http://www.w3.org/1999/xhtml">{xml_fragment}</p>'
    return ET.fromstring(wrapped)


class TestIsItalicOnly(unittest.TestCase):
    def test_italic_text_only(self):
        p = _p("<em>spoken by the Chorus</em>")
        self.assertTrue(egq.is_italic_only(p))

    def test_italic_with_surrounding_whitespace(self):
        p = _p("  <em>of Helen</em>  ")
        self.assertTrue(egq.is_italic_only(p))

    def test_plain_text_is_not_italic_only(self):
        p = _p("Agamemnon 177")
        self.assertFalse(egq.is_italic_only(p))

    def test_mixed_content_is_not_italic_only(self):
        p = _p("<em>Anatomy of Melancholy</em> (1621)")
        self.assertFalse(egq.is_italic_only(p))

    def test_empty_paragraph(self):
        p = _p("")
        self.assertFalse(egq.is_italic_only(p))


if __name__ == "__main__":
    unittest.main()
