import clsx from "clsx";

const STATUS_STYLES: Record<string, string> = {
  PASSED: "bg-emerald-100 text-emerald-700",
  HEALED: "bg-sky-100 text-sky-700",
  FAILED: "bg-rose-100 text-rose-700",
  ERROR: "bg-rose-100 text-rose-700",
  HEALING_FAILED: "bg-rose-100 text-rose-700",
  REVIEW_REQUIRED: "bg-amber-100 text-amber-700",
  SKIPPED: "bg-slate-100 text-slate-600",
  COMPLETED: "bg-emerald-100 text-emerald-700",
  RUNNING: "bg-sky-100 text-sky-700",
  QUEUED: "bg-slate-100 text-slate-600",
  DISCOVERING: "bg-sky-100 text-sky-700",
  PLANNING: "bg-sky-100 text-sky-700",
  GENERATING: "bg-sky-100 text-sky-700",
  VALIDATING: "bg-sky-100 text-sky-700",
  EXECUTING: "bg-sky-100 text-sky-700",
  ANALYZING: "bg-sky-100 text-sky-700",
  HEALING: "bg-sky-100 text-sky-700",
  RETESTING: "bg-sky-100 text-sky-700",
  CANCELLED: "bg-slate-100 text-slate-600",
  LOW: "bg-emerald-100 text-emerald-700",
  MEDIUM: "bg-amber-100 text-amber-700",
  HIGH: "bg-orange-100 text-orange-700",
  CRITICAL: "bg-rose-100 text-rose-700",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600";
  return (
    <span className={clsx("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium", style)}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
