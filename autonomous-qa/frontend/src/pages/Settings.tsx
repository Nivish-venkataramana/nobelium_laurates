import Card from "../components/Card";

export default function Settings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">
          Platform configuration is managed via environment variables (see .env). This page
          reflects the current runtime configuration surfaced by the API.
        </p>
      </div>

      <Card title="Configuration reference">
        <ul className="space-y-2 text-sm text-slate-600">
          <li>
            <span className="font-mono text-slate-500">HEALING_CONFIDENCE_THRESHOLD</span> — minimum
            deterministic/AI-assisted confidence required before a locator is automatically repaired.
          </li>
          <li>
            <span className="font-mono text-slate-500">MAX_TESTS_PER_RUN</span> — upper bound on how
            many AI-generated tests a single run will execute.
          </li>
          <li>
            <span className="font-mono text-slate-500">ALLOWED_DOMAINS</span> — optional allowlist
            restricting which domains discovery/execution may target.
          </li>
          <li>
            <span className="font-mono text-slate-500">BROWSER_ENGINE_DEFAULT</span> — Playwright
            (default) or Selenium.
          </li>
        </ul>
      </Card>
    </div>
  );
}
