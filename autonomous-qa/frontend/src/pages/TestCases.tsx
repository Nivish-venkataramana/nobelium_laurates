import { useState } from "react";
import { Link } from "react-router-dom";
import { useApplications, useTestCases } from "../hooks/useApi";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";

export default function TestCases() {
  const { data: applications = [] } = useApplications();
  const [applicationId, setApplicationId] = useState("");
  const { data: tests = [] } = useTestCases(applicationId || undefined);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Test Cases</h1>
        <p className="text-sm text-slate-500">AI-generated and manually curated test cases.</p>
      </div>

      <Card>
        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-slate-500">Application</label>
          <select
            className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm"
            value={applicationId}
            onChange={(e) => setApplicationId(e.target.value)}
          >
            <option value="">Select an application</option>
            {applications.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>
      </Card>

      <Card>
        {!applicationId && <p className="text-sm text-slate-400">Select an application to view its tests.</p>}
        {applicationId && tests.length === 0 && (
          <p className="text-sm text-slate-400">No test cases for this application yet.</p>
        )}
        <ul className="divide-y divide-slate-100">
          {tests.map((t) => (
            <li key={t.id} className="flex items-center justify-between py-3">
              <div>
                <Link to={`/tests/${t.id}`} className="font-medium text-brand-600 hover:underline">
                  {t.external_code} — {t.name}
                </Link>
                <p className="text-sm text-slate-500">{t.rationale}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={t.category} />
                <StatusBadge status={t.priority} />
                <StatusBadge status={t.risk} />
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
