import { Link } from "react-router-dom";
import { useRuns } from "../hooks/useApi";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";

export default function TestRuns() {
  const { data: runs = [] } = useRuns();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Test Runs</h1>
        <p className="text-sm text-slate-500">History of all pipeline executions across applications.</p>
      </div>

      <Card>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-400">
              <th className="py-2">Run</th>
              <th>Status</th>
              <th>Generated</th>
              <th>Passed</th>
              <th>Failed</th>
              <th>Healed</th>
              <th>Quality</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className="border-b border-slate-50">
                <td className="py-2">
                  <Link to={`/runs/${r.id}`} className="text-brand-600 hover:underline">
                    {r.id.slice(0, 8)}
                  </Link>
                </td>
                <td>
                  <StatusBadge status={r.status} />
                </td>
                <td>{r.tests_generated}</td>
                <td>{r.tests_passed}</td>
                <td>{r.tests_failed}</td>
                <td>{r.tests_healed}</td>
                <td>{r.quality_score ?? "N/A"}</td>
                <td className="text-slate-400">{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.length === 0 && <p className="py-4 text-sm text-slate-400">No runs yet.</p>}
      </Card>
    </div>
  );
}
