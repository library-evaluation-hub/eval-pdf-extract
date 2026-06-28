import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type RunInfo, type LeaderboardEntry, METRIC_IDS, METRIC_CATEGORIES } from "../api";

export default function Dashboard() {
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [selectedRun, setSelectedRun] = useState<string>("");
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listRuns().then((data) => {
      setRuns(data);
      if (data.length > 0 && !selectedRun) {
        setSelectedRun(data[0].run_id);
      }
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (!selectedRun) return;
    setLoading(true);
    api.getRunLeaderboard(selectedRun).then((data) => {
      setLeaderboard(data);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, [selectedRun]);

  if (loading && leaderboard.length === 0) {
    return <div className="p-6 text-gray-500">Loading...</div>;
  }
  if (error) {
    return <div className="p-6 text-red-600">Error: {error}</div>;
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold text-gray-900">Dashboard</h2>
        <select
          value={selectedRun}
          onChange={(e) => setSelectedRun(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white"
        >
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.run_id} ({r.started_at})
            </option>
          ))}
        </select>
      </div>

      {runs.length === 0 ? (
        <div className="text-gray-500 text-sm">No runs found. Run <code className="bg-gray-100 px-1 rounded">make run</code> to generate results.</div>
      ) : leaderboard.length === 0 ? (
        <div className="text-gray-500 text-sm">No scores found for this run.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm border border-gray-200">
            <thead>
              <tr className="bg-gray-100 border-b border-gray-200">
                <th className="text-left px-3 py-2 font-medium text-gray-700">Adapter</th>
                {METRIC_IDS.map((m) => (
                  <th key={m} className="text-right px-3 py-2 font-medium text-gray-700 whitespace-nowrap">
                    <span title={METRIC_CATEGORIES[m]} className="inline-block w-2 h-2 rounded-full mr-1 align-middle"
                      style={{
                        backgroundColor:
                          METRIC_CATEGORIES[m] === "text" ? "#3b82f6" :
                          METRIC_CATEGORIES[m] === "structure" ? "#10b981" :
                          METRIC_CATEGORIES[m] === "performance" ? "#f59e0b" :
                          "#ef4444"
                      }}
                    />
                    {m}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((entry) => (
                <tr key={entry.adapter_id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-3 py-2 font-mono text-xs text-blue-600">
                    <Link to={`/adapter/${entry.adapter_id}`} className="hover:underline">{entry.adapter_id}</Link>
                  </td>
                  {METRIC_IDS.map((m) => {
                    const val = entry[m];
                    return (
                      <td key={m} className="text-right px-3 py-2 font-mono text-xs">
                        {val === null || val === undefined ? (
                          <span className="text-gray-300">—</span>
                        ) : typeof val === "number" ? (
                          <span className={m === "text_cer" || m === "text_wer" ? (val < 0.1 ? "text-green-600" : val < 0.3 ? "text-yellow-600" : "text-red-600") : ""}>
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
