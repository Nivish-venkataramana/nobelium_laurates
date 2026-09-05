import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  applicationsApi,
  discoveryApi,
  healingApi,
  projectsApi,
  runsApi,
  testCasesApi,
} from "../services/api";

export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: projectsApi.list });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: projectsApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useApplications(projectId?: string) {
  return useQuery({
    queryKey: ["applications", projectId],
    queryFn: () => applicationsApi.list(projectId),
  });
}

export function useCreateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: applicationsApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["applications"] }),
  });
}

export function useRunDiscovery() {
  return useMutation({ mutationFn: discoveryApi.run });
}

export function useTestCases(applicationId?: string) {
  return useQuery({
    queryKey: ["tests", applicationId],
    queryFn: () => testCasesApi.list(applicationId as string),
    enabled: !!applicationId,
  });
}

export function useTestCaseDetail(id?: string) {
  return useQuery({
    queryKey: ["test", id],
    queryFn: () => testCasesApi.get(id as string),
    enabled: !!id,
  });
}

export function useRunSingleTest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: testCasesApi.run,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useRuns(applicationId?: string) {
  return useQuery({
    queryKey: ["runs", applicationId],
    queryFn: () => runsApi.list(applicationId),
    refetchInterval: 4000,
  });
}

export function useRun(id?: string) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => runsApi.get(id as string),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const terminal = status === "COMPLETED" || status === "FAILED" || status === "CANCELLED";
      return terminal ? false : 3000;
    },
  });
}

export function useRunResults(id?: string) {
  return useQuery({
    queryKey: ["runResults", id],
    queryFn: () => runsApi.results(id as string),
    enabled: !!id,
    refetchInterval: 4000,
  });
}

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: runsApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
}

export function useHealingEvents(params?: { run_id?: string; test_case_id?: string }) {
  return useQuery({
    queryKey: ["healingEvents", params],
    queryFn: () => healingApi.list(params),
  });
}
