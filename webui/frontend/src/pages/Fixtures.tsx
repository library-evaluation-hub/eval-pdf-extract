import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type FixtureInfo } from "../api";

export default function Fixtures() {
  const [fixtures, setFixtures] = useState<FixtureInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  useEffect(() => {
    api.listFixtures().then((data) => {
      setFixtures(data);
      setLoading(false);
    }).catch((e) => {
      setError(e.message);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-6 text-gray-500">Loading...</div>;
  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;

  const categories = [...new Set(fixtures.map((f) => f.category))];
  const filtered = categoryFilter
    ? fixtures.filter((f) => f.category === categoryFilter)
    : fixtures;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-gray-900">Fixtures</h2>
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-1.5 text-sm bg-white"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>
      {filtered.length === 0 ? (
        <div className="text-gray-500 text-sm">No fixtures found.</div>
      ) : (
        <table className="min-w-full text-sm border border-gray-200">
          <thead>
            <tr className="bg-gray-100 border-b border-gray-200">
              <th className="text-left px-3 py-2 font-medium text-gray-700">ID</th>
              <th className="text-left px-3 py-2 font-medium text-gray-700">Category</th>
              <th className="text-right px-3 py-2 font-medium text-gray-700">Pages</th>
              <th className="text-left px-3 py-2 font-medium text-gray-700">Difficulty</th>
              <th className="text-left px-3 py-2 font-medium text-gray-700">Tags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f) => (
              <tr key={f.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-3 py-2 font-mono text-xs">
                  <Link to={`/fixture/${f.id}`} className="text-blue-600 hover:underline">{f.id}</Link>
                </td>
                <td className="px-3 py-2">
                  <span className="inline-block px-2 py-0.5 text-xs rounded-full bg-blue-50 text-blue-700">{f.category}</span>
                </td>
                <td className="text-right px-3 py-2 font-mono">{f.expected_page_count}</td>
                <td className="px-3 py-2 text-gray-600">{f.difficulty || "—"}</td>
                <td className="px-3 py-2 text-xs text-gray-500">
                  {f.tags.map((t) => (
                    <span key={t} className="inline-block mr-1 px-1.5 py-0.5 bg-gray-100 rounded">{t}</span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
