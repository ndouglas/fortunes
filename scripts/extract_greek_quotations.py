#!/usr/bin/env python3
"""Extract fortune-file content from 'A Dictionary of Classical Greek Quotations'."""

import argparse
import sys
import zipfile

MAIN_XHTML_PATH = "OEBPS/html/09_Quotations.xhtml"
APPENDIX_XHTML_PATH = "OEBPS/html/10_1.xhtml"


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
