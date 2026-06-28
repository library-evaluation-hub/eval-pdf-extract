import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type FixtureDetail, METRIC_IDS } from "../api";

export default function FixtureDetail() {
  const { fixtureId } = useParams<{ fixtureId: string }>();
  const [data, setData] = useState<FixtureDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!fixtureId) return;
    api.getFixture(fixtureId).then((d) => {
      setData(d);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, [fixtureId]);

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;
  if (!data) return <div className="p-6 text-gray-500">Fixture not found.</div>;

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-2 font-mono">{data.id}</h2>
      <div className="flex gap-3 mb-6 text-sm">
        <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">{data.category}</span>
        <span className="text-gray-500">{data.expected_page_count} pages</span>
        {data.difficulty && <span className="text-gray-500">Difficulty: {data.difficulty}</span>}
      </div>

      <h3 className="text-sm font-medium text-gray-700 mb-3">Adapter Results</h3>
      {data.adapter_results.length === 0 ? (
        <div className="text-gray-500 text-sm">No adapter results found for this fixture.</div>
      ) : (
        <div className="space-y-4">
          {data.adapter_results.map((entry) => (
            <div key={`${entry.run_id}-${entry.adapter_id}`} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-blue-600">{entry.adapter_id}</span>
                  <span className="text-xs text-gray-400">from {entry.run_id}</span>
                </div>
                {entry.score && (
                  <div className="flex gap-1">
                    {entry.score.metrics["success"] === true && (
                      <span className="px-2 py-0.5 text-xs rounded-full bg-green-50 text-green-700">success</span>
                    )}
                    {entry.score.metrics["success"] === false && (
                      <span className="px-2 py-0.5 text-xs rounded-full bg-red-50 text-red-700">failed</span>
                    )}
                  </div>
                )}
              </div>
              {entry.score && (
                <div className="grid grid-cols-4 gap-2 text-xs mb-3">
                  {METRIC_IDS.filter((m) => entry.score?.metrics[m] !== undefined && entry.score?.metrics[m] !== null).map((m) => {
                    const val = entry.score!.metrics[m];
                    return (
                    <div key={m} className="flex justify-between border-b border-gray-100 py-0.5">
                      <span className="text-gray-500">{m}</span>
                      <span className="font-mono">
                        {typeof val === "number"
                          ? (val as number).toFixed(4)
                          : String(val)}
                      </span>
                    </div>
                    );
                  })}
                </div>
              )}
              {entry.stderr && (
                <details className="mt-2">
                  <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">stderr.log</summary>
                  <pre className="mt-1 text-xs text-gray-600 bg-gray-50 p-2 rounded overflow-x-auto max-h-40">{entry.stderr}</pre>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
