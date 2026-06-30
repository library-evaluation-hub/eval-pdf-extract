# python-pdfplumber adapter

[pdfplumber](https://github.com/jsvine/pdfplumber) adapter for eval-pdf-extract.

pdfplumber is built on pdfminer.six and provides detailed text extraction,
table extraction, and page-level object access (chars, lines, rects, etc.).

## Version

- pdfplumber: 0.11.0 (PyPI `pdfplumber`)
- Python: >= 3.10

## Install

```bash
cd adapters/python-pdfplumber
uv pip install -e .
# Verify command is on PATH
python-pdfplumber --help
```

## API usage

- `pdfplumber.open(path)` — open PDF
- `page.extract_text()` — page-level text
- `page.extract_words(use_text_flow=True)` — word-level with positions
- `page.find_tables()` — table detection with bbox
- `table.extract()` — table cell data as list of lists
- `pdf.metadata` — document metadata

## Known limitations

- **Blocks are approximated**: pdfplumber does not provide block-level structure.
  Blocks are reconstructed from `extract_words` grouped by y-position.
- **No OCR support**: `supports_ocr` is `false`.
- **Config ignored**: `--config` is accepted but has no effect.
- **Timeout not self-enforced**: relies on orchestrator's hard timeout.
