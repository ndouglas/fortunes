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


_LOWERCASE_WORDS = {"of", "the", "and", "de", "von", "der", "le", "la"}


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

_TRANSLATOR_PREFIX = "Translated by"


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
            if text.startswith(_TRANSLATOR_PREFIX):
                continue
            pending.english_lines.append(text)
            continue

        if cls == MAIN_CLASS_CITATION:
            if p.italic_only:
                continue
            if text.startswith(_TRANSLATOR_PREFIX):
                continue
            if pending.citation:
                pending.citation = f"{pending.citation} {text}"
            else:
                pending.citation = text
            continue

        # Any other class (C334 metadata, C325 letter heading, etc.) is ignored.

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
    print(f"read main body: {len(main_xhtml):,} chars", file=sys.stderr)
    print(f"read appendix:  {len(appendix_xhtml):,} chars", file=sys.stderr)


if __name__ == "__main__":
    main()
