import { useParams, Link } from "react-router-dom";
import { useApplications, useCreateRun, useRuns, useTestCases } from "../hooks/useApi";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";

export default function ApplicationDetail() {
  const { applicationId } = useParams();
  const { data: applications = [] } = useApplications();
  const application = applications.find((a) => a.id === applicationId);
  const { data: tests = [] } = useTestCases(applicationId);
  const { data: runs = [] } = useRuns(applicationId);
  const createRun = useCreateRun();

  function startRun(opts: { run_discovery: boolean; run_generation: boolean }) {
    if (!applicationId) return;
    createRun.mutate({ application_id: applicationId, ...opts, trigger: "manual" });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{application?.name ?? "Application"}</h1>
        <p className="text-sm text-slate-500">{application?.base_url}</p>
      </div>

      <Card title="Run controls">
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => startRun({ run_discovery: true, run_generation: true })}
            disabled={createRun.isPending}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            Discover + Generate + Run
          </button>
          <button
            onClick={() => startRun({ run_discovery: true, run_generation: false })}
            disabled={createRun.isPending}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            Discover Only
          </button>
          <button
            onClick={() => startRun({ run_discovery: false, run_generation: false })}
            disabled={createRun.isPending}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            Re-run Existing Tests
          </button>
        </div>
        {createRun.isSuccess && (
          <p className="mt-3 text-sm text-emerald-600">
            Run queued.{" "}
            <Link to={`/runs/${createRun.data.id}`} className="underline">
              View progress
            </Link>
          </p>
        )}
      </Card>

      <Card title={`Test Cases (${tests.length})`}>
        {tests.length === 0 && (
          <p className="text-sm text-slate-400">No test cases yet. Run discovery + generation above.</p>
        )}
        <ul className="divide-y divide-slate-100">
          {tests.map((t) => (
            <li key={t.id} className="flex items-center justify-between py-3">
              <div>
                <Link to={`/tests/${t.id}`} className="font-medium text-brand-600 hover:underline">
                  {t.external_code} — {t.name}
                </Link>
                <p className="text-sm text-slate-500">{t.business_intent}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={t.priority} />
                <StatusBadge status={t.risk} />
              </div>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Run history">
        <ul className="divide-y divide-slate-100">
          {runs.map((r) => (
            <li key={r.id} className="flex items-center justify-between py-3 text-sm">
              <Link to={`/runs/${r.id}`} className="text-brand-600 hover:underline">
                Run {r.id.slice(0, 8)} · {new Date(r.created_at).toLocaleString()}
              </Link>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">
                  {r.tests_passed}✓ {r.tests_failed}✗ {r.tests_healed}⚕
                </span>
                <StatusBadge status={r.status} />
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
