import { useHealingEvents } from "../hooks/useApi";
import Card from "../components/Card";
import StatusBadge from "../components/StatusBadge";

export default function HealingHistory() {
  const { data: events = [] } = useHealingEvents();

  const healed = events.filter((e) => e.outcome === "HEALED").length;
  const reviewRequired = events.filter((e) => e.outcome === "REVIEW_REQUIRED").length;
  const failed = events.filter((e) => e.outcome === "HEALING_FAILED").length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Healing History</h1>
        <p className="text-sm text-slate-500">
          Every self-healing attempt the platform has made, with full evidence.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card>
          <p className="text-2xl font-semibold text-sky-600">{healed}</p>
          <p className="text-xs text-slate-500">Healed</p>
        </Card>
        <Card>
          <p className="text-2xl font-semibold text-amber-600">{reviewRequired}</p>
          <p className="text-xs text-slate-500">Review Required</p>
        </Card>
        <Card>
          <p className="text-2xl font-semibold text-rose-600">{failed}</p>
          <p className="text-xs text-slate-500">Healing Failed</p>
        </Card>
      </div>

      <Card>
        <ul className="divide-y divide-slate-100">
          {events.map((e) => (
            <li key={e.id} className="py-4 text-sm">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <StatusBadge status={e.outcome} />
                  <span className="text-xs text-slate-400">{e.method}</span>
                </div>
                <span className="text-xs text-slate-400">
                  {Math.round(e.confidence * 100)}% confidence
                </span>
              </div>
              <p className="mt-2 text-slate-600">{e.reason}</p>
              <p className="mt-1 text-xs text-slate-400">
                {e.created_at ? new Date(e.created_at).toLocaleString() : ""}
              </p>
            </li>
          ))}
          {events.length === 0 && <p className="py-4 text-sm text-slate-400">No healing events recorded yet.</p>}
        </ul>
      </Card>
    </div>
  );
}
