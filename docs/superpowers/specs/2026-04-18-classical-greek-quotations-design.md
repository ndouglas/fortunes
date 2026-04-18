# Classical Greek Quotations — fortune file conversion

## Goal

Convert *A Dictionary of Classical Greek Quotations* (EPUB) into fortune-file format, producing two files that match the conventions already used in this repo.

## Inputs

- **EPUB**: `/Users/nathan/Downloads/quotations_books/A Dictionary of Classical Greek Quotations/A Dictionary of Classical Greek Quotations.epub`
- Two XHTML files inside the EPUB drive the output:
  - `OEBPS/html/09_Quotations.xhtml` (~3.4 MB) — the main body: quotations **by** classical Greek authors, alphabetized.
  - `OEBPS/html/10_1.xhtml` — Appendix 1: quotations **about** Greece by later authors (Byron, Addison, etc.).

## Outputs

Two plain-text fortune files at the repo root (same directory as existing `aristotle`, `bartletts_familiar_quotations`, etc.):

- `classical_greek_quotations` — from the main body.
- `quotations_on_greeks` — from Appendix 1.

Format (matches existing files in this repo):

```
<English quotation text>
— <Author>, <Work> <section/line>
%
```

- UTF-8, Unix line endings.
- Em-dash (`—`) before attribution.
- `%` separator on its own line between entries.
- Greek originals are dropped. Translator credits are dropped. Editorial context notes (italicized, e.g. "spoken by the Chorus", "cf. Plato 342") are dropped.

## Scope (included / excluded)

**Included:**
- Main body (09_Quotations.xhtml) → `classical_greek_quotations`.
- Appendix 1 (10_1.xhtml) → `quotations_on_greeks`.
- Author names title-cased from the book's ALL CAPS headers.
- Work title + section/line reference preserved in attribution.

**Excluded:**
- Appendices 2–6 (abbreviations, translator list, websites, copyright, maps).
- Greek originals.
- Translator credits.
- Italic context/cross-reference notes.
- Deduplication against existing author files (e.g. `aristotle`, `plato`). The user has accepted that overlap will exist.
- `strfile .dat` index generation.

## Tooling

One Python 3 script: `scripts/extract_greek_quotations.py` (creates the `scripts/` directory at the repo root).

- Uses `zipfile` (stdlib) to read the two XHTML entries directly from the EPUB — no need to unzip to disk.
- Uses `beautifulsoup4` + `lxml` (or stdlib `html.parser` as fallback) for XHTML parsing.
- Takes EPUB path as the sole positional argument.
- Writes both output files to the current working directory.
- Idempotent: rerunning overwrites cleanly.
- Prints stats to stdout: quote counts per file, counts of skipped entries with reason codes.
- Fails fast with a clear message if dependencies are missing.

**Invocation:**

```
python3 scripts/extract_greek_quotations.py \
  "/Users/nathan/Downloads/quotations_books/A Dictionary of Classical Greek Quotations/A Dictionary of Classical Greek Quotations.epub"
```

## Parsing logic — main body (09_Quotations.xhtml)

State machine walking `<body>` children in document order, tracking `current_author` and `current_quote` (object holding accumulated English lines + citation).

| Paragraph class | Meaning | Action |
|---|---|---|
| `C325` | Letter heading ("A", "B"…) | Ignore |
| `C329` | Author name (ALL CAPS) | Flush pending quote; title-case → `current_author` |
| `C334` | Dates / bio / "see also" cross-ref | Ignore |
| `C330` containing `<span class="C412">N</span>` | Start of quotation N (Greek text) | Flush pending quote; start new quote (Greek is discarded) |
| `C331` | English translation (may span multiple `<p>`) | Append to `current_quote.english` (unless it begins with "Translated by") |
| `C332` | Citation, translator note, or context note | First non-italic, non-"Translated by" `C332` after `C331` → citation; subsequent non-italic `C332` → continuation of citation; italic-wrapped or "Translated by…" → skip |
| Anything else | | Ignore |

**Flushing a quote** emits to the output file:

```
<joined english lines>
— <current_author>, <citation>
%
```

If `current_quote.english` is empty at flush time, the quote is skipped (counted under `skipped_empty_english`).

## Parsing logic — Appendix 1 (10_1.xhtml)

Same state-machine shape, different class map:

| Class | Meaning |
|---|---|
| `C362` (contains `<strong>`) | Author name (already mixed case — no title-casing) |
| `C334` | Dates / bio | ignore |
| `C331` or `C364` | Quote text |
| `C332` or `C365` | Source citation |
| Italic-wrapped `C332` / `C365` | Context note → skip |

Implementation: the two parsers share a common `emit_quote()` helper and `flush()` semantics, differing only in the class-to-action mapping.

## Known edge cases (handle in implementation)

1. **Multi-line English translations**: consecutive `C331` paragraphs after a `C330` are verse continuations — accumulate them as separate lines of the same quote.
2. **"Translated by X" leaking into C331**: detect prefix `Translated by` and exclude that paragraph from the English accumulation.
3. **Citation split across multiple C332 paragraphs**: join consecutive non-italic C332 lines with spaces until hitting an italic `C332` or a new quote/author.
4. **Italic-only C332** (context notes, "cf." cross-refs): detect by checking whether the paragraph's entire visible content is wrapped in `<em>`. Skip.
5. **Author name casing**: book uses ALL CAPS (e.g. "AESCHINES SOCRATICUS"). Title-case for output ("Aeschines Socraticus"). Keep short words ("of", "the", "and") lowercase except when first. Preserve capitalization after apostrophes.
6. **Missing English translation**: if a quotation has no `C331` between its `C330` and the next quote/author, skip the entry and count under `skipped_empty_english`.
7. **Anomalous paragraphs**: occasional `C334` paragraph contains inline quote+translation (saw at least one instance). Log and skip rather than risk mis-parsing.
8. **Em-dash vs en-dash**: source may use either `–` or `—`. Normalize attribution prefix to `—` (em-dash).
9. **Cross-reference headers** ("see also Aristophanes 82, 85" under an author): appears as a `C334` paragraph beginning with `<em>see also</em>`. Already ignored by the `C334 → ignore` rule; no special handling needed.

## Verification (run after extraction)

1. **Quote count sanity** — count `%` separators; should be in the thousands for the main body. Drastically low counts (<1000) suggest parser failure.
2. **Spot-check 5 random entries** against the EPUB — confirm English text + attribution match.
3. **Leakage grep** — no Greek characters in output (`grep -P '[\x{0370}-\x{03FF}\x{1F00}-\x{1FFF}]'` returns nothing), no "Translated by" strings, no stray HTML tags, no empty attributions (lines matching `^— ,` or `^— $`).
4. **`strfile` compatibility** — run `strfile classical_greek_quotations` if available to confirm valid fortune format (skipped if not installed).
5. **Separator discipline** — every `%` on its own line, no consecutive `%` lines, no trailing whitespace artifacts.

## Commit plan

Single commit containing:

- `scripts/extract_greek_quotations.py`
- `classical_greek_quotations`
- `quotations_on_greeks`

## Out of scope

- Processing the other quotation books in `~/Downloads/quotations_books/` (separate projects if/when the user wants them).
- Deduplication against existing per-author files in this repo.
- Fortune `.dat` index generation.
- Adding a README or test suite for the script (single-purpose, single-input utility; spec serves as its documentation).
