import { Route, Routes } from "react-router";

import AppLayout from "./components/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import NewResearchPage from "./pages/NewResearchPage";
import NotFoundPage from "./pages/NotFoundPage";
import ResearchHistoryPage from "./pages/ResearchHistoryPage";
import ResearchTaskPage from "./pages/ResearchTaskPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="research/new" element={<NewResearchPage />} />
        <Route path="research/history" element={<ResearchHistoryPage />} />
        <Route path="research/tasks/:taskId" element={<ResearchTaskPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}