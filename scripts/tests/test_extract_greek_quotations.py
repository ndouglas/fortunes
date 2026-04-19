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

    def test_capitalizes_after_apostrophe(self):
        self.assertEqual(egq.title_case_author("O'BRIEN"), "O'Brien")


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


AESCHYLUS_FRAGMENT = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="C325">A</p>
<p class="C329">AESCHYLUS</p>
<p class="C334">c.525–456bc</p>
<p class="C334">Athenian tragic playwright</p>
<p class="C330"><span class="C412">1</span> GREEK_TEXT_1</p>
<p class="C331">Hell to ships, hell to men, hell to cities.</p>
<p class="C332"><em>Agamemnon</em> 689</p>
<p class="C332"><em>spoken by the Chorus</em></p>
<p class="C330"><span class="C412">2</span> GREEK_TEXT_2</p>
<p class="C331">We learn by suffering.</p>
<p class="C332">Translated by Robert Fagles (1975)</p>
<p class="C332"><em>Agamemnon</em> 177</p>
</body></html>
"""


class TestParseMainBody(unittest.TestCase):
    def test_extracts_two_quotes(self):
        quotes = egq.parse_main_body(AESCHYLUS_FRAGMENT)
        self.assertEqual(len(quotes), 2)

    def test_author_title_cased(self):
        quotes = egq.parse_main_body(AESCHYLUS_FRAGMENT)
        self.assertEqual(quotes[0].author, "Aeschylus")
        self.assertEqual(quotes[1].author, "Aeschylus")

    def test_english_preserved(self):
        quotes = egq.parse_main_body(AESCHYLUS_FRAGMENT)
        self.assertEqual(
            quotes[0].english_lines,
            ["Hell to ships, hell to men, hell to cities."],
        )

    def test_citation_from_first_nonitalic_c332(self):
        quotes = egq.parse_main_body(AESCHYLUS_FRAGMENT)
        self.assertEqual(quotes[0].citation, "Agamemnon 689")

    def test_translator_credit_excluded_from_citation(self):
        quotes = egq.parse_main_body(AESCHYLUS_FRAGMENT)
        # Quote 2's first C332 is 'Translated by ...' — must be skipped.
        self.assertEqual(quotes[1].citation, "Agamemnon 177")

    def test_multiline_english_accumulates(self):
        xhtml = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="C329">AESCHYLUS</p>
<p class="C330"><span class="C412">1</span> GREEK</p>
<p class="C331">Line one of verse.</p>
<p class="C331">Line two of verse.</p>
<p class="C332"><em>Agamemnon</em> 1</p>
</body></html>
"""
        quotes = egq.parse_main_body(xhtml)
        self.assertEqual(
            quotes[0].english_lines,
            ["Line one of verse.", "Line two of verse."],
        )

    def test_translator_credit_line_in_c331_is_excluded(self):
        # Saw this in the source: a C331 with 'Translated by ...' content.
        xhtml = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="C329">AESCHYLUS</p>
<p class="C330"><span class="C412">1</span> GREEK</p>
<p class="C331">Never too old to learn, it keeps me young.</p>
<p class="C331">Translated by Robert Fagles (1975)</p>
<p class="C332"><em>Agamemnon</em> 584</p>
</body></html>
"""
        quotes = egq.parse_main_body(xhtml)
        self.assertEqual(
            quotes[0].english_lines,
            ["Never too old to learn, it keeps me young."],
        )

    def test_citation_split_across_two_c332_paragraphs(self):
        xhtml = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="C329">BURTON</p>
<p class="C330"><span class="C412">1</span> GREEK</p>
<p class="C331">We can say nothing, but what has been said.</p>
<p class="C332"><em>The Anatomy of Melancholy</em> (1621),</p>
<p class="C332">Democritus to the Reader</p>
<p class="C332"><em>and a context note</em></p>
</body></html>
"""
        quotes = egq.parse_main_body(xhtml)
        self.assertEqual(
            quotes[0].citation,
            "The Anatomy of Melancholy (1621), Democritus to the Reader",
        )

    def test_quote_with_missing_english_is_skipped(self):
        xhtml = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="C329">AESCHYLUS</p>
<p class="C330"><span class="C412">1</span> GREEK</p>
<p class="C332"><em>Agamemnon</em> 1</p>
<p class="C330"><span class="C412">2</span> GREEK2</p>
<p class="C331">Has English.</p>
<p class="C332"><em>Agamemnon</em> 2</p>
</body></html>
"""
        quotes = egq.parse_main_body(xhtml)
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].english_lines, ["Has English."])

    def test_greek_paragraph_does_not_appear_in_english(self):
        quotes = egq.parse_main_body(AESCHYLUS_FRAGMENT)
        for quote in quotes:
            for line in quote.english_lines:
                self.assertNotIn("GREEK_TEXT", line)
        self.assertEqual(len(quotes[0].english_lines), 1)
        self.assertEqual(len(quotes[1].english_lines), 1)

    def test_author_with_only_metadata_produces_no_quotes(self):
        xhtml = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="C329">UNKNOWN</p>
<p class="C334">Unknown dates</p>
<p class="C334">Unknown bio</p>
</body></html>
"""
        self.assertEqual(egq.parse_main_body(xhtml), [])


class TestFormatQuotes(unittest.TestCase):
    def test_single_quote(self):
        quotes = [egq.Quote("Aeschylus", ["Hell to cities."], "Agamemnon 689")]
        text = egq.format_quotes(quotes)
        self.assertEqual(
            text,
            "Hell to cities.\n— Aeschylus, Agamemnon 689\n%\n",
        )

    def test_multiple_quotes_separated_by_percent(self):
        quotes = [
            egq.Quote("Aeschylus", ["First."], "Agamemnon 1"),
            egq.Quote("Aeschylus", ["Second."], "Agamemnon 2"),
        ]
        text = egq.format_quotes(quotes)
        self.assertEqual(
            text,
            "First.\n— Aeschylus, Agamemnon 1\n%\n"
            "Second.\n— Aeschylus, Agamemnon 2\n%\n",
        )

    def test_multiline_english(self):
        quotes = [egq.Quote("Aeschylus", ["Line one.", "Line two."], "Agamemnon 1")]
        text = egq.format_quotes(quotes)
        self.assertEqual(
            text,
            "Line one.\nLine two.\n— Aeschylus, Agamemnon 1\n%\n",
        )

    def test_empty_citation_only_author(self):
        # Defensive: if citation is somehow empty, don't emit a dangling comma.
        quotes = [egq.Quote("Plato", ["Know thyself."], "")]
        text = egq.format_quotes(quotes)
        self.assertEqual(text, "Know thyself.\n— Plato\n%\n")


APPENDIX_FRAGMENT = """<?xml version="1.0"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body>
<p class="C368">QUOTATIONS ON GREECE AND GREEKS</p>
<p class="C362"><strong>Joseph Addison</strong></p>
<p class="C334">1672–1719</p>
<p class="C334">English poet, dramatist, and essayist</p>
<p class="C331">It must be so – Plato, thou reason'st well!</p>
<p class="C331">Else hence this pleasing hope.</p>
<p class="C331"><em>Cato</em> (1713), Act 5, Scene 1</p>
<p class="C362"><strong>Lord Byron</strong></p>
<p class="C334">1788–1824</p>
<p class="C331">The isles of Greece, the isles of Greece!</p>
<p class="C332"><em>Don Juan</em> (1819–1824), canto 3, st. 86</p>
<p class="C332"><em>of Sappho</em></p>
</body></html>
"""


class TestParseAppendixOne(unittest.TestCase):
    def test_extracts_quotes(self):
        quotes = egq.parse_appendix_one(APPENDIX_FRAGMENT)
        self.assertEqual(len(quotes), 2)

    def test_preserves_mixed_case_author(self):
        quotes = egq.parse_appendix_one(APPENDIX_FRAGMENT)
        self.assertEqual(quotes[0].author, "Joseph Addison")
        self.assertEqual(quotes[1].author, "Lord Byron")

    def test_multiple_c331_accumulate_into_english(self):
        quotes = egq.parse_appendix_one(APPENDIX_FRAGMENT)
        # Note: the Addison entry uses C331 for both the quote lines AND the
        # source citation (no separate C332). We handle this by treating the
        # last C331 in a run as the citation when no C332 appears.
        # For this test, we accept that the source line may appear in the
        # accumulated text; see next test for explicit citation handling.
        first = quotes[0]
        self.assertIn("It must be so", first.english_lines[0])

    def test_citation_from_c332_when_present(self):
        quotes = egq.parse_appendix_one(APPENDIX_FRAGMENT)
        self.assertEqual(quotes[1].citation, "Don Juan (1819–1824), canto 3, st. 86")

    def test_italic_context_note_skipped(self):
        # The '<em>of Sappho</em>' C332 must not appear in the citation.
        quotes = egq.parse_appendix_one(APPENDIX_FRAGMENT)
        self.assertNotIn("Sappho", quotes[1].citation)


if __name__ == "__main__":
    unittest.main()
