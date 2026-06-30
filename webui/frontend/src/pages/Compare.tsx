import { useEffect, useState } from "react";
import { api, type RunInfo, type FixtureInfo, type AdapterInfo, type CompareData, type PageData } from "../api";

type DiffMode = "text" | "diff";

export default function Compare() {
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [fixtures, setFixtures] = useState<FixtureInfo[]>([]);
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [selectedRuns, setSelectedRuns] = useState<string[]>([]);
  const [selectedFixtures, setSelectedFixtures] = useState<string[]>([]);
  const [selectedAdapters, setSelectedAdapters] = useState<string[]>([]);
  const [compareData, setCompareData] = useState<CompareData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [diffMode, setDiffMode] = useState<DiffMode>("text");

  useEffect(() => {
    Promise.all([api.listRuns(), api.listFixtures(), api.listAdapters()]).then(
      ([r, f, a]) => {
        setRuns(r);
        setFixtures(f);
        setAdapters(a);
        if (r.length > 0) setSelectedRuns([r[0].run_id]);
      },
    ).catch((e) => {
      setError(e.message);
    });
  }, []);

  const handleCompare = () => {
    if (selectedRuns.length === 0 || selectedFixtures.length === 0 || selectedAdapters.length === 0) return;
    setLoading(true);
    setError("");
    api.getCompare(selectedRuns, selectedFixtures, selectedAdapters).then((data) => {
      setCompareData(data);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  };

  const toggleRun = (id: string) => {
    setSelectedRuns((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id],
    );
  };

  const toggleFixture = (id: string) => {
    setSelectedFixtures((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id],
    );
  };

  const toggleAdapter = (id: string) => {
    setSelectedAdapters((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id],
    );
  };

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Compare</h2>

      {/* Selection panel */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Runs</label>
          <div className="border border-gray-200 rounded-md max-h-40 overflow-y-auto text-sm">
            {runs.map((r) => (
              <label key={r.run_id} className="flex items-center px-2 py-1 hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedRuns.includes(r.run_id)}
                  onChange={() => toggleRun(r.run_id)}
                  className="mr-2"
                />
                <span className="font-mono text-xs">{r.run_id}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Fixtures</label>
          <div className="border border-gray-200 rounded-md max-h-40 overflow-y-auto text-sm">
            {fixtures.map((f) => (
              <label key={f.id} className="flex items-center px-2 py-1 hover:bg-gray-50 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedFixtures.includes(f.id)}
                  onChange={() => toggleFixture(f.id)}
                  className="mr-2"
                />
                <span className="font-mono text-xs">{f.id}</span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Adapters</label>
          <div className="border border-gray-200 rounded-md max-h-40 overflow-y-auto text-sm">
            {[...adapters].sort((a, b) => Number(b.implemented) - Number(a.implemented)).map((a) => (
              <label key={a.id} className={`flex items-center px-2 py-1 hover:bg-gray-50 cursor-pointer ${a.implemented ? "" : "opacity-50"}`}>
                <input
                  type="checkbox"
                  checked={selectedAdapters.includes(a.id)}
                  onChange={() => toggleAdapter(a.id)}
                  className="mr-2"
                />
                <span className={`font-mono text-xs ${a.implemented ? "text-gray-700" : "text-gray-400"}`}>{a.id}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-6 flex items-center gap-3">
        <button
          type="button"
          onClick={handleCompare}
          disabled={selectedRuns.length === 0 || selectedFixtures.length === 0 || selectedAdapters.length === 0}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Compare
        </button>
        {compareData && (
          <div className="flex items-center gap-1 ml-2">
            <span className="text-xs text-gray-500 mr-1">View:</span>
            <button
              type="button"
              onClick={() => setDiffMode("text")}
              className={`px-2.5 py-1 text-xs rounded-md ${diffMode === "text" ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
            >
              Plain text
            </button>
            <button
              type="button"
              onClick={() => setDiffMode("diff")}
              className={`px-2.5 py-1 text-xs rounded-md ${diffMode === "diff" ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
            >
              Diff
            </button>
          </div>
        )}
      </div>

      {loading && <div className="text-gray-500">Loading...</div>}
      {error && <div className="text-red-600">Error: {error}</div>}

      {compareData && (
        <div className="space-y-6">
          {compareData.fixtures.map((fixture) => {
            const resultKeys = Object.keys(fixture.adapter_results);
            return (
            <div key={fixture.fixture_id} className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="bg-gray-100 px-4 py-2 border-b border-gray-200">
                <h3 className="font-mono text-sm font-medium text-gray-900">{fixture.fixture_id}</h3>
              </div>
              <div className="p-4">
                {fixture.expected?.pages.map((page, pageIdx) => (
                  <div key={pageIdx} className="mb-4 last:mb-0">
                    <div className="text-xs font-medium text-gray-500 mb-2">Page {page.page_number}</div>
                    <div className="grid gap-2" style={{ gridTemplateColumns: `repeat(${resultKeys.length + 1}, minmax(0, 1fr))` }}>
                      {/* Expected column */}
                      <div className="border border-gray-200 rounded p-2 bg-gray-50">
                        <div className="text-xs font-medium text-gray-600 mb-1">Expected</div>
                        <PageTextView page={page} mode="text" />
                      </div>
                      {/* Adapter columns (keyed by run_id/adapter_id) */}
                      {resultKeys.map((key) => {
                        const entry = fixture.adapter_results[key];
                        const adapterPage = entry.result?.pages.find((p) => p.page_number === page.page_number);
                        return (
                          <div key={key} className="border border-gray-200 rounded p-2">
                            <div className="text-xs font-medium text-blue-600 mb-1 font-mono">
                              {entry.run_id}/{entry.adapter_id}
                            </div>
                            {adapterPage ? (
                              <PageTextView page={adapterPage} expectedPage={page} mode={diffMode} />
                            ) : (
                              <div className="text-xs text-gray-400 italic">No data</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PageTextView({ page, expectedPage, mode }: { page: PageData; expectedPage?: PageData; mode: DiffMode }) {
  const text = page.text || "";
  if (mode === "text" || !expectedPage) {
    return <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono">{text}</pre>;
  }
  const expectedText = expectedPage.text || "";
  return <DiffView expected={expectedText} actual={text} />;
}

function DiffView({ expected, actual }: { expected: string; actual: string }) {
  const expectedLines = expected.split("\n");
  const actualLines = actual.split("\n");

  // LCS-based line-level diff
  const m = expectedLines.length;
  const n = actualLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (expectedLines[i] === actualLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  type LineEntry = { type: "same" | "added" | "removed"; text: string };
  const lines: LineEntry[] = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (expectedLines[i] === actualLines[j]) {
      lines.push({ type: "same", text: expectedLines[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      lines.push({ type: "removed", text: expectedLines[i] });
      i++;
    } else {
      lines.push({ type: "added", text: actualLines[j] });
      j++;
    }
  }
  while (i < m) {
    lines.push({ type: "removed", text: expectedLines[i] });
    i++;
  }
  while (j < n) {
    lines.push({ type: "added", text: actualLines[j] });
    j++;
  }

  return (
    <div className="text-xs font-mono leading-relaxed">
      {lines.map((line, idx) => {
        const prefix = line.type === "same" ? " " : line.type === "removed" ? "-" : "+";
        if (line.type === "same") {
          return (
            <div key={idx} className="text-gray-400 whitespace-pre-wrap">
              <span className="select-none text-gray-300 mr-1">{prefix}</span>{line.text}
            </div>
          );
        }
        if (line.type === "removed") {
          return (
            <div key={idx} className="text-red-800 bg-red-50 whitespace-pre-wrap border-l-2 border-red-400 pl-1">
              <span className="select-none text-red-400 mr-1">{prefix}</span>{line.text}
            </div>
          );
        }
        return (
          <div key={idx} className="text-green-800 bg-green-50 whitespace-pre-wrap border-l-2 border-green-400 pl-1">
            <span className="select-none text-green-400 mr-1">{prefix}</span>{line.text}
          </div>
        );
      })}
    </div>
  );
}
