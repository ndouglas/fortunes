#!/usr/bin/env python3
"""Extract fortune-file content from 'A Dictionary of Classical Greek Quotations'."""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from typing import Iterator, List, Optional

XHTML_NS = "{http://www.w3.org/1999/xhtml}"

MAIN_XHTML_PATH = "OEBPS/html/09_Quotations.xhtml"
APPENDIX_XHTML_PATH = "OEBPS/html/10_1.xhtml"

MAIN_OUTPUT = "classical_greek_quotations"
APPENDIX_OUTPUT = "quotations_on_greeks"


_LOWERCASE_WORDS = {"of", "the", "and", "de", "von", "der", "le", "la"}


_GREEK_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF]")


def _contains_greek(text):
    return bool(_GREEK_RE.search(text))


def _capitalize_with_apostrophes(word):
    """Capitalize the word and the first letter after any apostrophe.

    'o'brien' -> "O'Brien"
    """
    parts = word.split("'")
    return "'".join(p.capitalize() for p in parts)


def title_case_author(raw):
    """Convert the book's ALL CAPS author header to display title case.

    'AESCHINES SOCRATICUS' -> 'Aeschines Socraticus'
    'DIONYSIUS OF HALICARNASSUS' -> 'Dionysius of Halicarnassus'
    "O'BRIEN" -> "O'Brien"
    """
    words = raw.strip().split()
    result = []
    for i, word in enumerate(words):
        lower = word.lower()
        if i > 0 and lower in _LOWERCASE_WORDS:
            result.append(lower)
        else:
            result.append(_capitalize_with_apostrophes(lower))
    return " ".join(result)


def is_italic_only(p_element):
    """True if the paragraph's entire visible content is inside one <em>.

    Used to detect editorial context notes ('spoken by the Chorus', 'cf. Plato 342')
    that should be skipped rather than emitted as citations.
    """
    # No direct text outside tags (only whitespace is OK).
    if p_element.text and p_element.text.strip():
        return False
    children = list(p_element)
    if len(children) != 1:
        return False
    child = children[0]
    if child.tag != f"{XHTML_NS}em":
        return False
    # No tail text after the <em> (only whitespace is OK).
    if child.tail and child.tail.strip():
        return False
    # The <em> must contain something.
    inner = "".join(child.itertext()).strip()
    return bool(inner)


@dataclass
class ParagraphRecord:
    css_class: Optional[str]
    text: str
    italic_only: bool


def walk_paragraphs(xhtml_str) -> Iterator[ParagraphRecord]:
    """Yield a ParagraphRecord for each <p> that is a direct child of <body>.

    Paragraph `text` is the concatenation of all descendant text nodes with
    internal whitespace collapsed to single spaces and leading/trailing
    whitespace stripped.
    """
    root = ET.fromstring(xhtml_str)
    body = root.find(f"{XHTML_NS}body")
    if body is None:
        raise ValueError("no <body> element found in XHTML")

    for p in body.findall(f"{XHTML_NS}p"):
        css_class = p.get("class")
        raw_text = "".join(p.itertext())
        text = re.sub(r"\s+", " ", raw_text).strip()
        yield ParagraphRecord(
            css_class=css_class,
            text=text,
            italic_only=is_italic_only(p),
        )


@dataclass
class Quote:
    author: str
    english_lines: List[str]
    citation: str


# Paragraph class codes used by the main body (09_Quotations.xhtml).
MAIN_CLASS_AUTHOR = "C329"
MAIN_CLASS_QUOTE_START = "C330"       # Greek original; Nth quote begins here
MAIN_CLASS_ENGLISH = "C331"
MAIN_CLASS_CITATION = "C332"

_TRANSLATOR_PREFIXES = ("Translated by", "Translated in")


# Paragraph class codes for Appendix 1 (10_1.xhtml).
APPENDIX_CLASS_AUTHOR = "C362"          # contains <strong>author</strong>
APPENDIX_CLASS_ENGLISH = ("C331", "C364")
APPENDIX_CLASS_CITATION = ("C332", "C365")


def parse_main_body(xhtml_str) -> List[Quote]:
    """Parse 09_Quotations.xhtml into a list of Quote objects.

    Walks paragraphs in order. Resets author on C329; starts a new quote on
    C330; accumulates English on C331; captures citation on C332. Quotes
    with no English content are dropped.
    """
    quotes: List[Quote] = []
    current_author: Optional[str] = None
    pending: Optional[Quote] = None

    def flush():
        nonlocal pending
        if pending is not None and pending.english_lines:
            quotes.append(pending)
        pending = None

    for p in walk_paragraphs(xhtml_str):
        cls = p.css_class
        text = p.text

        if cls == MAIN_CLASS_AUTHOR:
            flush()
            current_author = title_case_author(text)
            continue

        if current_author is None:
            # Paragraphs before the first author header (letter headings, etc.).
            continue

        if cls == MAIN_CLASS_QUOTE_START:
            flush()
            pending = Quote(author=current_author, english_lines=[], citation="")
            continue

        if pending is None:
            continue

        if cls == MAIN_CLASS_ENGLISH:
            if _contains_greek(text):
                continue
            if text.startswith(_TRANSLATOR_PREFIXES):
                continue
            pending.english_lines.append(text)
            continue

        if cls == MAIN_CLASS_CITATION:
            if p.italic_only:
                continue
            if text.startswith(_TRANSLATOR_PREFIXES):
                continue
            if pending.citation:
                pending.citation = f"{pending.citation} {text}"
            else:
                pending.citation = text
            continue

        # Any other class (C334 metadata, C325 letter heading, etc.) is ignored.

    flush()
    return quotes


def format_quotes(quotes: List[Quote]) -> str:
    """Render a list of Quote objects into fortune-file text.

    Each quote is:
        <english line 1>
        [<english line 2>
         ...]
        — <Author>[, <Citation>]
        %
    """
    out = []
    for q in quotes:
        for line in q.english_lines:
            out.append(line + "\n")
        if q.citation:
            out.append(f"— {q.author}, {q.citation}\n")
        else:
            out.append(f"— {q.author}\n")
        out.append("%\n")
    return "".join(out)


def parse_appendix_one(xhtml_str) -> List[Quote]:
    """Parse 10_1.xhtml into Quote objects.

    The appendix uses different class codes than the main body and has no
    C330-style 'new quote' marker — each author block may contain multiple
    quotes separated only by successive C331/C364 runs. A new quote starts
    when we see C331/C364 immediately after a citation (C332/C365).
    """
    quotes: List[Quote] = []
    current_author: Optional[str] = None
    pending: Optional[Quote] = None
    last_was_citation = False

    def flush():
        nonlocal pending
        if pending is not None and pending.english_lines:
            quotes.append(pending)
        pending = None

    for p in walk_paragraphs(xhtml_str):
        cls = p.css_class
        text = p.text

        if cls == APPENDIX_CLASS_AUTHOR:
            flush()
            current_author = text
            last_was_citation = False
            continue

        if current_author is None:
            continue

        if cls in APPENDIX_CLASS_ENGLISH:
            if _contains_greek(text):
                continue
            # A new run of English after a citation starts a new quote.
            if pending is None or last_was_citation:
                flush()
                pending = Quote(author=current_author, english_lines=[], citation="")
            pending.english_lines.append(text)
            last_was_citation = False
            continue

        if cls in APPENDIX_CLASS_CITATION:
            if p.italic_only:
                continue
            if pending is None:
                continue
            if pending.citation:
                pending.citation = f"{pending.citation} {text}"
            else:
                pending.citation = text
            last_was_citation = True
            continue

        # Any other class (C334 metadata, C368 section heading, etc.) ignored.

    flush()
    return quotes


def read_epub_xhtml(epub_source):
    """Read the two XHTML files we care about from the EPUB zip.

    `epub_source` is anything ZipFile accepts: a path or a file-like object.
    Returns (main_body_xhtml, appendix_one_xhtml) as str.
    """
    with zipfile.ZipFile(epub_source) as z:
        main = z.read(MAIN_XHTML_PATH).decode("utf-8")
        appendix = z.read(APPENDIX_XHTML_PATH).decode("utf-8")
    return main, appendix


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("epub_path", help="Path to the .epub file")
    args = parser.parse_args(argv)

    main_xhtml, appendix_xhtml = read_epub_xhtml(args.epub_path)

    main_quotes = parse_main_body(main_xhtml)
    appendix_quotes = parse_appendix_one(appendix_xhtml)

    with open(MAIN_OUTPUT, "w", encoding="utf-8") as f:
        f.write(format_quotes(main_quotes))
    with open(APPENDIX_OUTPUT, "w", encoding="utf-8") as f:
        f.write(format_quotes(appendix_quotes))

    print(f"{MAIN_OUTPUT}: {len(main_quotes):,} quotes", file=sys.stderr)
    print(f"{APPENDIX_OUTPUT}: {len(appendix_quotes):,} quotes", file=sys.stderr)


if __name__ == "__main__":
    main()
