import axios from "axios";
import type {
  Application,
  HealingEvent,
  Project,
  TestCase,
  TestCaseDetail,
  TestResult,
  TestRun,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL: API_BASE_URL });

export const projectsApi = {
  list: () => api.get<Project[]>("/api/projects").then((r) => r.data),
  create: (data: { name: string; description?: string }) =>
    api.post<Project>("/api/projects", data).then((r) => r.data),
  get: (id: string) => api.get<Project>(`/api/projects/${id}`).then((r) => r.data),
};

export const applicationsApi = {
  list: (projectId?: string) =>
    api
      .get<Application[]>("/api/applications", { params: projectId ? { project_id: projectId } : {} })
      .then((r) => r.data),
  create: (data: { project_id: string; name: string; base_url: string; browser_engine?: string }) =>
    api.post<Application>("/api/applications", data).then((r) => r.data),
  get: (id: string) => api.get<Application>(`/api/applications/${id}`).then((r) => r.data),
};

export const discoveryApi = {
  run: (data: { application_id: string; url: string; max_pages?: number }) =>
    api.post("/api/discovery", data).then((r) => r.data),
};

export const testCasesApi = {
  list: (applicationId: string) =>
    api.get<TestCase[]>("/api/tests", { params: { application_id: applicationId } }).then((r) => r.data),
  get: (id: string) => api.get<TestCaseDetail>(`/api/tests/${id}`).then((r) => r.data),
  run: (id: string) => api.post<TestRun>(`/api/tests/${id}/run`).then((r) => r.data),
};

export const runsApi = {
  list: (applicationId?: string) =>
    api
      .get<TestRun[]>("/api/runs", { params: applicationId ? { application_id: applicationId } : {} })
      .then((r) => r.data),
  create: (data: {
    application_id: string;
    run_discovery?: boolean;
    run_generation?: boolean;
    max_tests?: number;
    trigger?: string;
  }) => api.post<TestRun>("/api/runs", data).then((r) => r.data),
  get: (id: string) => api.get<TestRun>(`/api/runs/${id}`).then((r) => r.data),
  cancel: (id: string) => api.post<TestRun>(`/api/runs/${id}/cancel`).then((r) => r.data),
  rerun: (id: string) => api.post<TestRun>(`/api/runs/${id}/rerun`).then((r) => r.data),
  results: (id: string) => api.get<TestResult[]>(`/api/runs/${id}/results`).then((r) => r.data),
};

export const healingApi = {
  list: (params?: { run_id?: string; test_case_id?: string }) =>
    api.get<HealingEvent[]>("/api/healing-events", { params }).then((r) => r.data),
};
