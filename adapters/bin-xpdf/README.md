# bin-xpdf adapter

[Xpdf pdftotext](https://www.xpdfreader.com/) adapter for eval-pdf-extract.

pdftotext is a standalone binary tool from the Xpdf project that converts PDF to
plain text. This adapter wraps the binary with a Python script to implement the
adapter protocol.

## Version

- pdftotext: 4.06
- Binary: `pdftotext.exe` (Windows) shipped in this directory

## Install

```bash
cd adapters/bin-xpdf
uv pip install -e .
# Verify command is on PATH
bin-xpdf --help
```

## How it works

1. Wrapper script receives `extract --input <pdf> --output-dir <dir>`
2. Calls `pdftotext -enc UTF-8 -eol unix <pdf> -` (stdout mode)
3. Splits output by form-feed (`\f`) into pages
4. Constructs `result.json` (page text only, no blocks/tables/metadata)
5. Writes `meta.json` with version info from `pdftotext -v`

## Known limitations

- **No block structure**: `blocks` is empty; only `text` is populated per page.
- **No table extraction**: `tables` is empty.
- **No metadata**: pdftotext does not provide document metadata.
- **No page dimensions**: width/height not available from pdftotext output.
- **No OCR**: `supports_ocr` is `false`.
- **Binary platform**: ships Windows `.exe`; on Linux/macOS, `pdftotext` must be on PATH.
