import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useApplications, useCreateApplication, useProjects } from "../hooks/useApi";
import Card from "../components/Card";

export default function ProjectDetail() {
  const { projectId } = useParams();
  const { data: projects = [] } = useProjects();
  const { data: applications = [] } = useApplications(projectId);
  const createApp = useCreateApplication();

  const project = projects.find((p) => p.id === projectId);

  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("http://localhost:5050");
  const [engine, setEngine] = useState("playwright");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !baseUrl.trim() || !projectId) return;
    createApp.mutate(
      { project_id: projectId, name, base_url: baseUrl, browser_engine: engine },
      { onSuccess: () => setName("") }
    );
  }

  const errorMessage = createApp.error
    ? ((createApp.error as any).response?.data?.detail ?? createApp.error.message)
    : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{project?.name ?? "Project"}</h1>
        <p className="text-sm text-slate-500">{project?.description}</p>
      </div>

      <Card title="Add an application">
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">Name</label>
            <input
              className="w-48 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Demo Shop"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">Base URL</label>
            <input
              className="w-64 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">Engine</label>
            <select
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={engine}
              onChange={(e) => setEngine(e.target.value)}
            >
              <option value="playwright">Playwright</option>
              <option value="selenium">Selenium</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={createApp.isPending}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            Add Application
          </button>
        </form>
        {errorMessage && (
          <p className="mt-3 text-sm text-rose-600 font-medium">
            {errorMessage}
          </p>
        )}
      </Card>

      <Card title="Applications">
        {applications.length === 0 && <p className="text-sm text-slate-400">No applications yet.</p>}
        <ul className="divide-y divide-slate-100">
          {applications.map((a) => (
            <li key={a.id} className="flex items-center justify-between py-3">
              <div>
                <Link to={`/applications/${a.id}`} className="font-medium text-brand-600 hover:underline">
                  {a.name}
                </Link>
                <p className="text-sm text-slate-500">{a.base_url}</p>
              </div>
              <span className="text-xs text-slate-400">{a.browser_engine}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
