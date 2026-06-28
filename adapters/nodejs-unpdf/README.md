# nodejs-unpdf adapter

[unpdf](https://github.com/unjs/unpdf) (by unjs) adapter for eval-pdf-extract.

unpdf is a modern alternative to `pdf-parse`, built on a serverless build of
Mozilla's pdf.js. It provides higher-level APIs for text extraction, metadata,
links, and structured text items.

## Version

- unpdf: 1.6.2 (npm `unpdf`)
- Node.js: >= 20

## Install

```bash
cd adapters/nodejs-unpdf
npm install
npm link  # makes `nodejs-unpdf` available on PATH
```

## API usage

- `getDocumentProxy(data)` — parse PDF into a reusable proxy
- `getMeta(pdf)` — document metadata (title, author, etc.)
- `extractText(pdf)` — per-page text array (no `mergePages`)
- `pdf.getPage(n).getViewport({ scale: 1 })` — page dimensions

## Known limitations

- **No block-level structure**: `extractText` returns page-level text only.
  `result.json` pages have `text` populated but `blocks` are empty arrays.
- **No table extraction**: unpdf does not provide table extraction;
  `tables` arrays are empty.
- **No OCR support**: `supports_ocr` is `false`.
- **Config ignored**: `--config` is accepted but has no effect.
- **Timeout not self-enforced**: relies on orchestrator's hard timeout.
