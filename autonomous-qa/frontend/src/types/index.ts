export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Application {
  id: string;
  project_id: string;
  name: string;
  base_url: string;
  browser_engine: string;
  created_at: string;
}

export interface TestCase {
  id: string;
  external_code: string;
  name: string;
  business_intent: string;
  category: string;
  priority: string;
  risk: string;
  expected_outcome: string;
  rationale: string;
  is_active: boolean;
}

export interface TestCaseDetail extends TestCase {
  steps: Array<{
    order_index: number;
    action: string;
    target_element_id: string | null;
    locator: Record<string, unknown>;
    value: string | null;
    description: string | null;
  }>;
  assertions: Array<Record<string, unknown>>;
}

export type RunStatus =
  | "CREATED"
  | "QUEUED"
  | "DISCOVERING"
  | "PLANNING"
  | "GENERATING"
  | "VALIDATING"
  | "EXECUTING"
  | "ANALYZING"
  | "HEALING"
  | "RETESTING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED";

export interface TestRun {
  id: string;
  application_id: string;
  status: RunStatus;
  trigger: string;
  started_at: string | null;
  finished_at: string | null;
  tests_generated: number;
  tests_executed: number;
  tests_passed: number;
  tests_failed: number;
  tests_healed: number;
  tests_review_required: number;
  quality_score: number | null;
  quality_score_breakdown: Record<string, unknown> | null;
  ai_explanation: { summary_lines: string[] } | null;
  error_message: string | null;
  created_at: string;
}

export interface TestResult {
  id: string;
  test_run_id: string;
  test_case_id: string;
  status: string;
  engine: string;
  browser: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  step_results: Array<Record<string, unknown>>;
  error_message: string | null;
  screenshot_path: string | null;
  trace_path: string | null;
  risk_score: number | null;
  risk_level: string | null;
  ai_explanation: string | null;
}

export interface HealingEvent {
  id: string;
  test_run_id: string;
  test_case_id: string;
  original_locator: Record<string, unknown>;
  replacement_locator: Record<string, unknown> | null;
  candidates_considered: Array<Record<string, unknown>>;
  confidence: number;
  method: string;
  reason: string;
  outcome: string;
  verification_result: string | null;
  healed_at: string | null;
  created_at: string;
}
