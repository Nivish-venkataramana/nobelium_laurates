import { ReactNode } from "react";
import clsx from "clsx";

export default function Card({
  children,
  className,
  title,
  actions,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  actions?: ReactNode;
}) {
  return (
    <div className={clsx("rounded-xl border border-slate-200 bg-white p-5 shadow-sm", className)}>
      {(title || actions) && (
        <div className="mb-4 flex items-center justify-between">
          {title && <h3 className="text-sm font-semibold text-slate-700">{title}</h3>}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}
