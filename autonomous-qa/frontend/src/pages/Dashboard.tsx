import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useHealingEvents, useRuns } from "../hooks/useApi";
import MetricTile from "../components/MetricTile";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";

export default function Dashboard() {
  const { data: runs = [] } = useRuns();
  const { data: healingEvents = [] } = useHealingEvents();

  const totals = useMemo(() => {
    const executed = runs.reduce((s, r) => s + r.tests_executed, 0);
    const passed = runs.reduce((s, r) => s + r.tests_passed, 0);
    const failed = runs.reduce((s, r) => s + r.tests_failed, 0);
    const healed = runs.reduce((s, r) => s + r.tests_healed, 0);
    const review = runs.reduce((s, r) => s + r.tests_review_required, 0);
    const successRate = executed > 0 ? Math.round(((passed + healed) / executed) * 100) : null;
    const latestQuality = runs.find((r) => r.quality_score !== null)?.quality_score ?? null;
    const riskCounts: Record<string, number> = {};
    return { executed, passed, failed, healed, review, successRate, latestQuality, riskCounts };
  }, [runs]);

  const recentRuns = runs.slice(0, 5);
  const recentFailures = runs.filter((r) => r.tests_failed > 0).slice(0, 5);
  const recentHealing = healingEvents.slice(0, 5);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Dashboard</h1>
        <p className="text-sm text-slate-500">
          A live view of your application quality, generated entirely from executed test data.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <MetricTile label="Total Tests Executed" value={totals.executed} />
        <MetricTile label="Passed" value={totals.passed} />
        <MetricTile label="Failed" value={totals.failed} />
        <MetricTile label="Healed" value={totals.healed} />
        <MetricTile label="Review Required" value={totals.review} />
        <MetricTile
          label="Success Rate"
          value={totals.successRate !== null ? `${totals.successRate}%` : "N/A"}
        />
        <MetricTile
          label="Quality Score"
          value={totals.latestQuality !== null ? `${totals.latestQuality}/100` : "N/A"}
          sublabel="From most recent completed run"
        />
        <MetricTile label="Total Runs" value={runs.length} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Recent Runs" className="lg:col-span-1">
          <ul className="space-y-3">
            {recentRuns.length === 0 && <p className="text-sm text-slate-400">No runs yet.</p>}
            {recentRuns.map((r) => (
              <li key={r.id} className="flex items-center justify-between text-sm">
                <Link to={`/runs/${r.id}`} className="text-brand-600 hover:underline">
                  Run {r.id.slice(0, 8)}
                </Link>
                <StatusBadge status={r.status} />
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Recent Failures" className="lg:col-span-1">
          <ul className="space-y-3">
            {recentFailures.length === 0 && <p className="text-sm text-slate-400">No failures recorded.</p>}
            {recentFailures.map((r) => (
              <li key={r.id} className="text-sm">
                <Link to={`/runs/${r.id}`} className="text-brand-600 hover:underline">
                  Run {r.id.slice(0, 8)}
                </Link>
                <p className="text-slate-500">{r.tests_failed} test(s) failed</p>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Recent Healing Events" className="lg:col-span-1">
          <ul className="space-y-3">
            {recentHealing.length === 0 && <p className="text-sm text-slate-400">No healing events yet.</p>}
            {recentHealing.map((e) => (
              <li key={e.id} className="text-sm">
                <div className="flex items-center justify-between">
                  <StatusBadge status={e.outcome} />
                  <span className="text-xs text-slate-400">{Math.round(e.confidence * 100)}% confidence</span>
                </div>
                <p className="mt-1 text-slate-500">{e.reason}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
