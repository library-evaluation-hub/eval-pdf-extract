# nodejs-pdfjs adapter

[Mozilla pdf.js](https://github.com/mozilla/pdf.js) (via `pdfjs-dist`) adapter
for eval-pdf-extract.

Uses the official Node build of pdf.js directly — no wrapper library. Text is
extracted via `page.getTextContent()` and reconstructed from text items with
newline insertion based on y-position changes.

## Version

- pdfjs-dist: 4.0.379 (npm `pdfjs-dist`)
- Node.js: >= 20

## Install

```bash
cd adapters/nodejs-pdfjs
npm install
npm link  # makes `nodejs-pdfjs` available on PATH
```

## API usage

- `getDocument({ data, useSystemFonts: true })` — parse PDF
- `doc.getMetadata()` — document metadata (title, author, etc.)
- `doc.getPage(n).getTextContent()` — text items with position info
- `page.getViewport({ scale: 1 })` — page dimensions

## Text reconstruction

pdf.js does not provide a high-level "extract text" API. The adapter
reconstructs text from `textContent.items` by:
1. Iterating items in document order
2. Inserting `\n` when y-position changes significantly (>2px)
3. Appending `item.str` for each item
4. Using `item.hasEOL` as an additional line break signal

## Known limitations

- **No block-level structure**: text items are flattened to page-level text.
  `result.json` pages have `text` populated but `blocks` are empty arrays.
- **No table extraction**: pdf.js does not provide table extraction;
  `tables` arrays are empty.
- **No OCR support**: `supports_ocr` is `false`.
- **Config ignored**: `--config` is accepted but has no effect.
- **Timeout not self-enforced**: relies on orchestrator's hard timeout.
- **Text reconstruction is heuristic**: newline insertion based on y-position
  may not perfectly match the original document layout.
