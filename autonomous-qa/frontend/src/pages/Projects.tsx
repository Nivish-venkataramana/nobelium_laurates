import { useState } from "react";
import { Link } from "react-router-dom";
import { useCreateProject, useProjects } from "../hooks/useApi";
import Card from "../components/Card";

export default function Projects() {
  const { data: projects = [], isLoading } = useProjects();
  const createProject = useCreateProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    createProject.mutate(
      { name, description: description || undefined },
      { onSuccess: () => { setName(""); setDescription(""); } }
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Projects</h1>
        <p className="text-sm text-slate-500">Group applications under a project.</p>
      </div>

      <Card title="Create a project">
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">Name</label>
            <input
              className="w-56 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Demo Shop"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">Description</label>
            <input
              className="w-72 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional"
            />
          </div>
          <button
            type="submit"
            disabled={createProject.isPending}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            Create Project
          </button>
        </form>
      </Card>

      <Card title="All projects">
        {isLoading && <p className="text-sm text-slate-400">Loading...</p>}
        {!isLoading && projects.length === 0 && (
          <p className="text-sm text-slate-400">No projects yet. Create one above.</p>
        )}
        <ul className="divide-y divide-slate-100">
          {projects.map((p) => (
            <li key={p.id} className="flex items-center justify-between py-3">
              <div>
                <Link to={`/projects/${p.id}`} className="font-medium text-brand-600 hover:underline">
                  {p.name}
                </Link>
                {p.description && <p className="text-sm text-slate-500">{p.description}</p>}
              </div>
              <span className="text-xs text-slate-400">
                {new Date(p.created_at).toLocaleDateString()}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
