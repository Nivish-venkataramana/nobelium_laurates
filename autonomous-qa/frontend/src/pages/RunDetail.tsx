import { useParams } from "react-router-dom";
import { useRun, useRunResults, useHealingEvents } from "../hooks/useApi";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";
import MetricTile from "../components/MetricTile";

const STATE_ORDER = [
  "CREATED",
  "QUEUED",
  "DISCOVERING",
  "PLANNING",
  "GENERATING",
  "VALIDATING",
  "EXECUTING",
  "ANALYZING",
  "HEALING",
  "RETESTING",
  "COMPLETED",
];

export default function RunDetail() {
  const { runId } = useParams();
  const { data: run } = useRun(runId);
  const { data: results = [] } = useRunResults(runId);
  const { data: healingEvents = [] } = useHealingEvents({ run_id: runId });

  if (!run) return <p className="text-sm text-slate-400">Loading...</p>;

  const currentIndex = STATE_ORDER.indexOf(run.status);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Run {run.id.slice(0, 8)}</h1>
          <p className="text-sm text-slate-500">
            Triggered {run.trigger} · {new Date(run.created_at).toLocaleString()}
          </p>
        </div>
        <StatusBadge status={run.status} />
      </div>

      {run.error_message && (
        <Card className="border-rose-200 bg-rose-50">
          <p className="text-sm text-rose-700">{run.error_message}</p>
        </Card>
      )}

      <Card title="Pipeline Progress">
        <div className="flex flex-wrap gap-2">
          {STATE_ORDER.map((s, i) => (
            <span
              key={s}
              className={`rounded-full px-3 py-1 text-xs font-medium ${
                i < currentIndex
                  ? "bg-emerald-100 text-emerald-700"
                  : i === currentIndex
                  ? "bg-brand-100 text-brand-700"
                  : "bg-slate-100 text-slate-400"
              }`}
            >
              {s}
            </span>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <MetricTile label="Generated" value={run.tests_generated} />
        <MetricTile label="Executed" value={run.tests_executed} />
        <MetricTile label="Passed" value={run.tests_passed} />
        <MetricTile label="Failed" value={run.tests_failed} />
        <MetricTile label="Healed" value={run.tests_healed} />
      </div>

      {run.quality_score !== null && run.quality_score_breakdown && (
        <Card title={`Quality Score: ${run.quality_score}/100`}>
          <ul className="grid grid-cols-2 gap-2 text-sm md:grid-cols-3">
            {Object.entries(run.quality_score_breakdown).map(([k, v]) => (
              <li key={k} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2">
                <span className="text-slate-500">{k.replace(/_/g, " ")}</span>
                <span className="font-medium">{String(v)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {run.ai_explanation && (
        <Card title="AI Explanation">
          <ul className="list-inside list-disc space-y-1 text-sm text-slate-700">
            {run.ai_explanation.summary_lines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="Test Results">
        <ul className="divide-y divide-slate-100">
          {results.map((r) => (
            <li key={r.id} className="py-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-medium">{r.test_case_id.slice(0, 8)}</span>
                <StatusBadge status={r.status} />
              </div>
              {r.error_message && <p className="mt-1 text-rose-600">{r.error_message}</p>}
              {r.ai_explanation && <p className="mt-1 text-slate-500">{r.ai_explanation}</p>}
              <div className="mt-1 flex gap-3 text-xs text-slate-400">
                <span>{r.engine}</span>
                {r.duration_ms !== null && <span>{r.duration_ms}ms</span>}
                {r.risk_level && <StatusBadge status={r.risk_level} />}
              </div>
            </li>
          ))}
          {results.length === 0 && <p className="text-sm text-slate-400">No results yet.</p>}
        </ul>
      </Card>

      <Card title="Healing Events">
        <ul className="space-y-3">
          {healingEvents.map((e) => (
            <li key={e.id} className="rounded-lg border border-slate-100 p-3 text-sm">
              <div className="flex items-center justify-between">
                <StatusBadge status={e.outcome} />
                <span className="text-xs text-slate-400">{Math.round(e.confidence * 100)}% confidence</span>
              </div>
              <p className="mt-2 text-slate-600">{e.reason}</p>
            </li>
          ))}
          {healingEvents.length === 0 && <p className="text-sm text-slate-400">No healing events for this run.</p>}
        </ul>
      </Card>
    </div>
  );
}
