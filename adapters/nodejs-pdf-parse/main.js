#!/usr/bin/env node
/**
 * pdf-parse adapter for eval-pdf-extract.
 *
 * CLI entry point implementing the adapter protocol (contract/adapter-protocol.md).
 * Uses pdf-parse v2 (mehmet-kozan) PDFParse class API.
 *
 * Known gaps:
 * - timeout: accepted but not enforced; orchestrator's hard timeout is the backstop.
 * - config: accepted but ignored; all pages are always extracted without OCR.
 * - blocks: pdf-parse v2 getText() returns page-level text; blocks are not populated.
 */

const fs = require("fs");
const path = require("path");

function getLibVersion() {
  try {
    const resolved = require.resolve("pdf-parse");
    let dir = path.dirname(resolved);
    while (dir !== path.dirname(dir)) {
      const pkgPath = path.join(dir, "package.json");
      if (fs.existsSync(pkgPath)) {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf-8"));
        if (pkg.name === "pdf-parse") return pkg.version;
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
    process.stderr.write("nodejs-pdf-parse — pdf-parse adapter for eval-pdf-extract\n\n");
    process.stderr.write("usage: nodejs-pdf-parse extract --input <pdf> --output-dir <dir> [--config <json>] [--timeout <int>]\n");
    process.exit(0);
  }

  if (rest.length === 0) {
    process.stderr.write("usage: nodejs-pdf-parse extract --input <pdf> --output-dir <dir> [--config <json>] [--timeout <int>]\n");
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

  const { PDFParse } = require("pdf-parse");
  const dataBuffer = fs.readFileSync(inputPath);

  const t0 = Date.now();

  const parser = new PDFParse({ data: dataBuffer });

  let infoResult, textResult, tableResult;
  try {
    infoResult = await parser.getInfo({ parsePageInfo: true });
    textResult = await parser.getText();
    tableResult = await parser.getTable();
  } catch (err) {
    await parser.destroy().catch(() => {});
    process.stderr.write(`parse error: ${err.message}\n`);
    return 65;
  }

  const numPages = infoResult.total || 0;
  const info = infoResult.infoData || {};
  const pageInfo = infoResult.pages || [];

  // textResult.text is concatenated text; split by form feed for per-page
  const rawText = (textResult && textResult.text) || "";
  const pageTexts = rawText.split("\f");
  while (pageTexts.length < numPages) {
    pageTexts.push("");
  }
  pageTexts.length = numPages;

  const pages = pageTexts.map((text, i) => {
    const pi = pageInfo[i] || {};
    return {
      page_number: i + 1,
      width: pi.width != null ? pi.width : undefined,
      height: pi.height != null ? pi.height : undefined,
      text: (text || "").trim(),
      blocks: [],
      tables: [],
    };
  });

  // Populate tables from tableResult if available
  if (tableResult && Array.isArray(tableResult.tables)) {
    for (const tbl of tableResult.tables) {
      if (tbl.page && tbl.page >= 1 && tbl.page <= pages.length) {
        const page = pages[tbl.page - 1];
        page.tables.push({
          id: tbl.id || `p${tbl.page}-t${page.tables.length}`,
          bbox: tbl.bbox || [0, 0, 0, 0],
          rows: (tbl.rows || []).map((r) => r.map((c) => (c != null ? String(c) : ""))),
          headers: tbl.headers || undefined,
        });
      }
    }
  }

  const wallMsSelf = Date.now() - t0;

  const result = {
    schema_version: "1.0.0",
    metadata: {
      title: info.Title || null,
      author: info.Author || null,
      subject: info.Subject || null,
      keywords: null,
      creator: info.Creator || null,
      producer: info.Producer || null,
      page_count: numPages,
      ocr_used: false,
    },
    pages,
  };

  const resultPath = path.join(outputDir, "result.json");
  fs.writeFileSync(resultPath, JSON.stringify(result, null, 2) + "\n", "utf-8");

  const meta = {
    library: {
      name: "pdf-parse",
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
  fs.writeFileSync(path.join(outputDir, "meta.json"), JSON.stringify(meta, null, 2) + "\n", "utf-8");

  await parser.destroy().catch(() => {});

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
