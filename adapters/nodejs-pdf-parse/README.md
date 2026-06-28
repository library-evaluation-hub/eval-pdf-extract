# nodejs-pdf-parse adapter

[pdf-parse](https://github.com/mehmet-kozan/pdf-parse) (by mehmet-kozan) adapter for eval-pdf-extract.

## Version

- pdf-parse: 2.4.5 (npm `pdf-parse`)
- Node.js: >= 20 (required by pdf-parse v2)

## Install

```bash
cd adapters/nodejs-pdf-parse
npm install
npm link  # makes `nodejs-pdf-parse` available on PATH
```

## API usage

Uses the v2 `PDFParse` class API:
- `getInfo({ parsePageInfo: true })` — metadata + per-page dimensions
- `getText()` — concatenated page text (split by `\f` for per-page)
- `getTable()` — tabular data extraction

## Known limitations

- **No block-level structure**: `getText()` returns page-level text only.
  `result.json` pages have `text` populated but `blocks` are empty arrays.
- **Table extraction**: uses `getTable()` when available; tables are mapped to
  the `tables` array on the corresponding page.
- **No OCR support**: `supports_ocr` is `false`.
- **Config ignored**: `--config` is accepted but has no effect.
- **Timeout not self-enforced**: relies on orchestrator's hard timeout.

## Page text splitting

pdf-parse v2 `getText()` returns concatenated text. The adapter splits on
form feed (`\f`) to produce per-page `text` fields. Page count comes from
`getInfo().total`.

