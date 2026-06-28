import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, type AdapterDetail, METRIC_IDS } from "../api";

export default function AdapterDetailPage() {
  const { adapterId } = useParams<{ adapterId: string }>();
  const [data, setData] = useState<AdapterDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!adapterId) return;
    api.getAdapter(adapterId).then((d) => {
      setData(d);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, [adapterId]);

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;
  if (!data) return <div className="p-6 text-gray-500">Adapter not found.</div>;

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-2 font-mono">{data.id}</h2>
      <div className="flex gap-3 mb-6 text-sm text-gray-600">
        <span>Language: {data.language}</span>
        <span>Timeout: {data.timeout_seconds}s</span>
        <span>OCR: {data.supports_ocr ? "yes" : "no"}</span>
      </div>

      <h3 className="text-sm font-medium text-gray-700 mb-3">Fixture Scores</h3>
      {data.fixture_scores.length === 0 ? (
        <div className="text-gray-500 text-sm">No fixture scores found for this adapter.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border border-gray-200">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-200">
                <th className="text-left px-3 py-2 font-medium text-gray-700">Fixture</th>
                <th className="text-left px-3 py-2 font-medium text-gray-700">Run</th>
                {METRIC_IDS.map((m) => (
                  <th key={m} className="text-right px-3 py-2 font-medium text-gray-700 whitespace-nowrap text-xs">
                    {m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.fixture_scores.map((fs, idx) => (
                <tr key={idx} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-xs text-blue-600">
                    <Link to={`/fixture/${fs.fixture_id}`} className="hover:underline">{fs.fixture_id}</Link>
                  </td>
                  <td className="px-3 py-2 text-xs text-gray-400">{fs.run_id}</td>
                  {METRIC_IDS.map((m) => {
                    const val = fs.metrics[m];
                    return (
                      <td key={m} className="text-right px-3 py-2 font-mono text-xs">
                        {val === null || val === undefined ? (
                          <span className="text-gray-300">—</span>
                        ) : typeof val === "number" ? (
                          <span className={
                            m === "text_cer" || m === "text_wer"
                              ? val < 0.1 ? "text-green-600" : val < 0.3 ? "text-yellow-600" : "text-red-600"
                              : ""
                          }>
                            {val.toFixed(4)}
                          </span>
                        ) : (
                          <span>{String(val)}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
