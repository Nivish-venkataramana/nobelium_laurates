import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  FolderKanban,
  Search,
  ListChecks,
  PlayCircle,
  Wrench,
  Settings,
} from "lucide-react";
import clsx from "clsx";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/discovery", label: "Discovery", icon: Search },
  { to: "/tests", label: "Test Cases", icon: ListChecks },
  { to: "/runs", label: "Test Runs", icon: PlayCircle },
  { to: "/healing", label: "Healing History", icon: Wrench },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-64 shrink-0 border-r border-slate-200 bg-white">
        <div className="px-5 py-5">
          <p className="text-sm font-semibold text-brand-600">Autonomous QA</p>
          <p className="text-xs text-slate-500">AI that adapts QA as fast as software changes.</p>
        </div>
        <nav className="mt-2 flex flex-col gap-1 px-3">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 bg-slate-50 px-8 py-6">
        <Outlet />
      </main>
    </div>
  );
}
