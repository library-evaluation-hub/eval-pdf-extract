#!/usr/bin/env node
/**
 * Mozilla pdf.js adapter for eval-pdf-extract.
 *
 * CLI entry point implementing the adapter protocol (contract/adapter-protocol.md).
 * Uses pdfjs-dist directly — the official Node build of Mozilla's pdf.js.
 *
 * Known gaps:
 * - timeout: accepted but not enforced; orchestrator's hard timeout is the backstop.
 * - config: accepted but ignored; all pages are always extracted without OCR.
 * - blocks: text items are flattened to page-level text; blocks are not populated.
 * - tables: not extracted by pdf.js; tables array is empty.
 */

const fs = require("fs");
const path = require("path");

function getLibVersion() {
  try {
    const resolved = require.resolve("pdfjs-dist/legacy/build/pdf.mjs");
    let dir = path.dirname(resolved);
    while (dir !== path.dirname(dir)) {
      const pkgPath = path.join(dir, "package.json");
      if (fs.existsSync(pkgPath)) {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
        if (pkg.name === "pdfjs-dist") return pkg.version;
      }
      dir = path.dirname(dir);
    }
  } catch {}
  return "unknown";
}

function parseArgs(argv) {
  const args = { cmd: null, input: null, outputDir: null, config: "{}", timeout: 60 };
  const rest = argv.slice(2);

  if (rest[0] === "--help" || rest[0] === "-h") {
    process.stderr.write("nodejs-pdfjs — Mozilla pdf.js adapter for eval-pdf-extract\n\n");
    process.stderr.write("usage: nodejs-pdfjs extract --input <pdf> --output-dir <dir> [--config <json>] [--timeout <int>]\n");
    process.exit(0);
  }

  if (rest.length === 0) {
    process.stderr.write("usage: nodejs-pdfjs extract --input <pdf> --output-dir <dir> [--config <json>] [--timeout <int>]\n");
    process.exit(2);
  }

  args.cmd = rest[0];
  if (args.cmd !== "extract") {
    process.stderr.write(`unknown subcommand: ${args.cmd}\n`);
    process.exit(2);
  }

  for (let i = 1; i < rest.length; i++) {
    const flag = rest[i];
    const val = rest[i + 1];
    switch (flag) {
      case "--input":
        args.input = val; i++; break;
      case "--output-dir":
        args.outputDir = val; i++; break;
      case "--config":
        args.config = val; i++; break;
      case "--timeout":
        args.timeout = parseInt(val, 10); i++; break;
      default:
        process.stderr.write(`unknown argument: ${flag}\n`);
        process.exit(2);
    }
  }

  if (!args.input || !args.outputDir) {
    process.stderr.write("--input and --output-dir are required\n");
    process.exit(2);
  }

  return args;
}

async function extract(inputPath, outputDir) {
  if (!fs.existsSync(inputPath)) {
    process.stderr.write(`input not found: ${inputPath}\n`);
    return 64;
  }

  const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
  const dataBuffer = fs.readFileSync(inputPath);
  const data = new Uint8Array(dataBuffer);

  const t0 = Date.now();

  let doc;
  try {
    doc = await pdfjs.getDocument({
      data,
      useSystemFonts: true,
      isEvalSupported: false,
    }).promise;
  } catch (err) {
    process.stderr.write(`parse error: ${err.message}\n`);
    return 65;
  }

  const numPages = doc.numPages;
  const info = await doc.getMetadata().catch(() => ({ info: {} }));
  const docInfo = (info && info.info) || {};

  const pages = [];
  for (let i = 1; i <= numPages; i++) {
    const page = await doc.getPage(i);
    const viewport = page.getViewport({ scale: 1 });
    const textContent = await page.getTextContent();

    // Reconstruct text from text items, inserting newlines based on y-position changes
    const items = textContent.items;
    let text = "";
    let prevY = null;
    for (const item of items) {
      const y = item.transform[5];
      if (prevY !== null && Math.abs(y - prevY) > 2) {
        text += "\n";
      }
      text += item.str;
      if (item.hasEOL) {
        text += "\n";
        prevY = y;
      } else {
        prevY = y;
      }
    }

    pages.push({
      page_number: i,
      width: viewport.width != null ? viewport.width : undefined,
      height: viewport.height != null ? viewport.height : undefined,
      text: text.trim(),
      blocks: [],
      tables: [],
    });
  }

  const wallMsSelf = Date.now() - t0;

  const result = {
    schema_version: "1.0.0",
    metadata: {
      title: docInfo.Title || null,
      author: docInfo.Author || null,
      subject: docInfo.Subject || null,
      keywords: null,
      creator: docInfo.Creator || null,
      producer: docInfo.Producer || null,
      page_count: numPages,
      ocr_used: false,
    },
    pages,
  };

  const resultPath = path.join(outputDir, "result.json");
  fs.writeFileSync(resultPath, JSON.stringify(result, null, 2) + "\n", "utf-8");

  const metaOut = {
    library: {
      name: "pdfjs-dist",
      version: getLibVersion(),
      language: "javascript",
    },
    execution: {
      ocr_used: false,
      ocr_engine: null,
      wall_time_ms_self: wallMsSelf,
      peak_memory_mb_self: null,
    },
    warnings: [],
  };
  fs.writeFileSync(path.join(outputDir, "meta.json"), JSON.stringify(metaOut, null, 2) + "\n", "utf-8");

  try {
    doc.destroy();
  } catch {}

  return 0;
}

async function main() {
  const args = parseArgs(process.argv);

  if (args.cmd === "extract") {
    fs.mkdirSync(args.outputDir, { recursive: true });
    try {
      JSON.parse(args.config);
    } catch {
      process.stderr.write("invalid --config JSON\n");
      process.exit(2);
    }
    try {
      const code = await extract(args.input, args.outputDir);
      process.exit(code);
    } catch (err) {
      process.stderr.write(`extract failed: ${err.constructor.name}: ${err.message}\n`);
      process.exit(65);
    }
  }
  process.exit(2);
}

main();
