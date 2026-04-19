import io
import os
import sys
import unittest
import xml.etree.ElementTree as ET
import zipfile

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(THIS_DIR)
sys.path.insert(0, SCRIPT_DIR)

import extract_greek_quotations as egq


def _p(xml_fragment):
    """Parse a single <p> element in the xhtml namespace."""
    wrapped = f'<p xmlns="http://www.w3.org/1999/xhtml">{xml_fragment}</p>'
    return ET.fromstring(wrapped)


class TestReadEpubXhtml(unittest.TestCase):
    def test_returns_two_xhtml_strings(self):
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


class TestWalkParagraphs(unittest.TestCase):
    MINIMAL_XHTML = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
<p class="C329">AESCHYLUS</p>
<p class="C334">c.525–456bc</p>
<p class="C331">Hell to ships, hell to men, hell to cities.</p>
<p class="C332"><em>Agamemnon</em> 689</p>
<p class="C332"><em>spoken by the Chorus</em></p>
</body>
</html>
"""

    def test_yields_one_record_per_paragraph(self):
        records = list(egq.walk_paragraphs(self.MINIMAL_XHTML))
        self.assertEqual(len(records), 5)

    def test_class_attribute_preserved(self):
        records = list(egq.walk_paragraphs(self.MINIMAL_XHTML))
        self.assertEqual(records[0].css_class, "C329")
        self.assertEqual(records[1].css_class, "C334")

    def test_text_content_extracted(self):
        records = list(egq.walk_paragraphs(self.MINIMAL_XHTML))
        self.assertEqual(records[0].text, "AESCHYLUS")
        self.assertEqual(
            records[2].text,
            "Hell to ships, hell to men, hell to cities.",
        )

    def test_mixed_content_text_joined(self):
        records = list(egq.walk_paragraphs(self.MINIMAL_XHTML))
        # Agamemnon italicized + space + "689"
        self.assertEqual(records[3].text, "Agamemnon 689")

    def test_italic_only_detection(self):
        records = list(egq.walk_paragraphs(self.MINIMAL_XHTML))
        self.assertFalse(records[3].italic_only)  # mixed content
        self.assertTrue(records[4].italic_only)   # italic-only context note

    def test_body_missing_raises(self):
        with self.assertRaises(ValueError):
            list(egq.walk_paragraphs('<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"></html>'))

    def test_paragraph_without_class_has_none(self):
        xhtml = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><p>no class</p></body></html>
"""
        records = list(egq.walk_paragraphs(xhtml))
        self.assertIsNone(records[0].css_class)


if __name__ == "__main__":
    unittest.main()
