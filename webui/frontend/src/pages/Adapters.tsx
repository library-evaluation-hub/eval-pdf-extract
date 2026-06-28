import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type AdapterInfo } from "../api";

export default function Adapters() {
  const [adapters, setAdapters] = useState<AdapterInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listAdapters().then((data) => {
      setAdapters(data);
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
      <h2 className="text-xl font-bold text-gray-900 mb-4">Adapters</h2>
      {adapters.length === 0 ? (
        <div className="text-gray-500 text-sm">No adapters registered.</div>
      ) : (
        <table className="min-w-full text-sm border border-gray-200">
          <thead>
            <tr className="bg-gray-100 border-b border-gray-200">
              <th className="text-left px-3 py-2 font-medium text-gray-700">ID</th>
              <th className="text-left px-3 py-2 font-medium text-gray-700">Language</th>
              <th className="text-left px-3 py-2 font-medium text-gray-700">Command</th>
              <th className="text-right px-3 py-2 font-medium text-gray-700">Timeout</th>
              <th className="text-center px-3 py-2 font-medium text-gray-700">OCR</th>
              <th className="text-center px-3 py-2 font-medium text-gray-700">Disabled</th>
            </tr>
          </thead>
          <tbody>
            {adapters.map((a) => (
              <tr key={a.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-3 py-2 font-mono text-xs">
                  <Link to={`/adapter/${a.id}`} className="text-blue-600 hover:underline">{a.id}</Link>
                </td>
                <td className="px-3 py-2 text-gray-600">{a.language}</td>
                <td className="px-3 py-2 font-mono text-xs text-gray-600">{a.command}</td>
                <td className="text-right px-3 py-2 font-mono">{a.timeout_seconds}s</td>
                <td className="text-center px-3 py-2">{a.supports_ocr ? "✓" : "—"}</td>
                <td className="text-center px-3 py-2">{a.disabled ? "✓" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
