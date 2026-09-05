import { useState } from "react";
import { useApplications, useRunDiscovery } from "../hooks/useApi";
import Card from "../components/Card";

export default function Discovery() {
  const { data: applications = [] } = useApplications();
  const runDiscovery = useRunDiscovery();
  const [applicationId, setApplicationId] = useState("");
  const [url, setUrl] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!applicationId || !url) return;
    runDiscovery.mutate({ application_id: applicationId, url });
  }

  const result = runDiscovery.data as
    | { snapshot_id: string; application_model: { pages: unknown[]; elements: unknown[]; forms: unknown[]; workflows: { name: string; business_intent: string }[] }; element_count: number; page_count: number }
    | undefined;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Discovery</h1>
        <p className="text-sm text-slate-500">
          Crawl an application and build its semantic ApplicationModel (pages, elements, forms, workflows).
        </p>
      </div>

      <Card title="Run discovery">
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">Application</label>
            <select
              className="w-56 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={applicationId}
              onChange={(e) => {
                setApplicationId(e.target.value);
                const app = applications.find((a) => a.id === e.target.value);
                if (app) setUrl(app.base_url);
              }}
            >
              <option value="">Select an application</option>
              {applications.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">URL</label>
            <input
              className="w-72 rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={runDiscovery.isPending}
            className="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600 disabled:opacity-50"
          >
            {runDiscovery.isPending ? "Discovering..." : "Run Discovery"}
          </button>
        </form>
        {runDiscovery.isError && (
          <p className="mt-3 text-sm text-rose-600">
            Discovery failed. Check that the URL is reachable and allowed by the security policy.
          </p>
        )}
      </Card>

      {result && (
        <Card title="ApplicationModel">
          <div className="grid grid-cols-4 gap-4 text-center">
            <div>
              <p className="text-2xl font-semibold">{result.page_count}</p>
              <p className="text-xs text-slate-500">Pages</p>
            </div>
            <div>
              <p className="text-2xl font-semibold">{result.element_count}</p>
              <p className="text-xs text-slate-500">Elements</p>
            </div>
            <div>
              <p className="text-2xl font-semibold">{result.application_model.forms.length}</p>
              <p className="text-xs text-slate-500">Forms</p>
            </div>
            <div>
              <p className="text-2xl font-semibold">{result.application_model.workflows.length}</p>
              <p className="text-xs text-slate-500">Workflows</p>
            </div>
          </div>
          {result.application_model.workflows.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase text-slate-500">Detected Workflows</p>
              <ul className="flex flex-wrap gap-2">
                {result.application_model.workflows.map((w, i) => (
                  <li key={i} className="rounded-full bg-brand-50 px-3 py-1 text-xs text-brand-700">
                    {w.business_intent}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
