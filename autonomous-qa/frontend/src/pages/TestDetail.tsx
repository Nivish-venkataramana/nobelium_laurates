import { useParams, Link } from "react-router-dom";
import { useHealingEvents, useRunSingleTest, useTestCaseDetail } from "../hooks/useApi";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";

export default function TestDetail() {
  const { testId } = useParams();
  const { data: test } = useTestCaseDetail(testId);
  const { data: healingEvents = [] } = useHealingEvents({ test_case_id: testId });
  const runSingle = useRunSingleTest();

  if (!test) {
    return <p className="text-sm text-slate-400">Loading...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">
            {test.external_code} — {test.name}
          </h1>
          <p className="text-sm text-slate-500">{test.business_intent}</p>
        </div>
        <button
          onClick={() => testId && runSingle.mutate(testId)}
          disabled={runSingle.isPending}
          className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
        >
          Run This Test
        </button>
      </div>
      {runSingle.isSuccess && (
        <p className="text-sm text-emerald-600">
          Queued.{" "}
          <Link to={`/runs/${runSingle.data.id}`} className="underline">
            View progress
          </Link>
        </p>
      )}

      <div className="flex gap-2">
        <StatusBadge status={test.category} />
        <StatusBadge status={test.priority} />
        <StatusBadge status={test.risk} />
      </div>

      <Card title="Rationale">
        <p className="text-sm text-slate-700">{test.rationale}</p>
        <p className="mt-2 text-sm text-slate-500">Expected: {test.expected_outcome}</p>
      </Card>

      <Card title="Steps">
        <ol className="space-y-3">
          {test.steps.map((s) => (
            <li key={s.order_index} className="rounded-lg border border-slate-100 p-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs text-slate-400">#{s.order_index}</span>
                <span className="font-medium">{s.action}</span>
              </div>
              {s.description && <p className="mt-1 text-slate-600">{s.description}</p>}
              {s.value && <p className="mt-1 text-slate-400">value: {s.value}</p>}
              <pre className="mt-2 overflow-x-auto rounded bg-slate-50 p-2 text-xs text-slate-500">
                {JSON.stringify(s.locator, null, 2)}
              </pre>
            </li>
          ))}
        </ol>
      </Card>

      <Card title="Assertions">
        <ul className="space-y-2">
          {test.assertions.map((a, i) => (
            <li key={i} className="rounded-lg border border-slate-100 p-3 text-sm">
              <pre className="overflow-x-auto text-xs text-slate-500">{JSON.stringify(a, null, 2)}</pre>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Healing History">
        {healingEvents.length === 0 && <p className="text-sm text-slate-400">No healing events for this test.</p>}
        <ul className="space-y-3">
          {healingEvents.map((e) => (
            <li key={e.id} className="rounded-lg border border-slate-100 p-3 text-sm">
              <div className="flex items-center justify-between">
                <StatusBadge status={e.outcome} />
                <span className="text-xs text-slate-400">
                  {Math.round(e.confidence * 100)}% confidence · {e.method}
                </span>
              </div>
              <p className="mt-2 text-slate-600">{e.reason}</p>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="font-semibold text-slate-500">Original locator</p>
                  <pre className="overflow-x-auto rounded bg-slate-50 p-2">
                    {JSON.stringify(e.original_locator, null, 2)}
                  </pre>
                </div>
                <div>
                  <p className="font-semibold text-slate-500">Replacement locator</p>
                  <pre className="overflow-x-auto rounded bg-slate-50 p-2">
                    {JSON.stringify(e.replacement_locator, null, 2)}
                  </pre>
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
