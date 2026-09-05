import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import ProjectDetail from "./pages/ProjectDetail";
import ApplicationDetail from "./pages/ApplicationDetail";
import Discovery from "./pages/Discovery";
import TestCases from "./pages/TestCases";
import TestDetail from "./pages/TestDetail";
import TestRuns from "./pages/TestRuns";
import RunDetail from "./pages/RunDetail";
import HealingHistory from "./pages/HealingHistory";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:projectId" element={<ProjectDetail />} />
        <Route path="applications/:applicationId" element={<ApplicationDetail />} />
        <Route path="discovery" element={<Discovery />} />
        <Route path="tests" element={<TestCases />} />
        <Route path="tests/:testId" element={<TestDetail />} />
        <Route path="runs" element={<TestRuns />} />
        <Route path="runs/:runId" element={<RunDetail />} />
        <Route path="healing" element={<HealingHistory />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
