import { useEffect, useState } from "react";
import { api, type RunInfo } from "../api";

export default function Runs() {
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listRuns().then((data) => {
      setRuns(data);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-4">Runs</h2>
      {runs.length === 0 ? (
        <div className="text-gray-500 text-sm">No runs found.</div>
      ) : (
        <table className="min-w-full text-sm border border-gray-200">
          <thead>
            <tr className="bg-gray-100 border-b border-gray-200">
              <th className="text-left px-3 py-2 font-medium text-gray-700">Run ID</th>
              <th className="text-left px-3 py-2 font-medium text-gray-700">Started</th>
              <th className="text-left px-3 py-2 font-medium text-gray-700">Completed</th>
              <th className="text-right px-3 py-2 font-medium text-gray-700">Pairs</th>
              <th className="text-right px-3 py-2 font-medium text-gray-700">Completed</th>
              <th className="text-right px-3 py-2 font-medium text-gray-700">Failed</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run_id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-3 py-2 font-mono text-xs text-blue-600">{r.run_id}</td>
                <td className="px-3 py-2 text-gray-600">{r.started_at}</td>
                <td className="px-3 py-2 text-gray-600">{r.completed_at}</td>
                <td className="text-right px-3 py-2 font-mono">{r.total_pairs}</td>
                <td className="text-right px-3 py-2 font-mono text-green-600">{r.completed}</td>
                <td className="text-right px-3 py-2 font-mono text-red-600">{r.failed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
