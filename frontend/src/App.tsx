import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "@/components/layout/AppLayout";
import DashboardPage from "@/pages/DashboardPage";
import DataExplorerPage from "@/pages/DataExplorerPage";
import DocumentsPage from "@/pages/DocumentsPage";
import AIQueryPage from "@/pages/AIQueryPage";
import AuditLogsPage from "@/pages/AuditLogsPage";
import KnowledgePage from "@/pages/KnowledgePage";
import NotFoundPage from "@/pages/NotFoundPage";
import ReportGeneratorPage from "@/pages/ReportGeneratorPage";
import ReviewQueuePage from "@/pages/ReviewQueuePage";
import SettingsPage from "@/pages/SettingsPage";
import TopicIntelligencePage from "@/pages/TopicIntelligencePage";
import ValidationPage from "@/pages/ValidationPage";

/** Every sidebar destination is a real, working page — no placeholders. */
export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        {/* Overview */}
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Data */}
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/data-explorer" element={<DataExplorerPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        {/* Intelligence */}
        <Route path="/ai-query" element={<AIQueryPage />} />
        <Route path="/topic-intelligence" element={<TopicIntelligencePage />} />
        <Route path="/report-generator" element={<ReportGeneratorPage />} />
        {/* Quality & governance */}
        <Route path="/validation" element={<ValidationPage />} />
        <Route path="/review-queue" element={<ReviewQueuePage />} />
        <Route path="/audit-logs" element={<AuditLogsPage />} />
        {/* System */}
        <Route path="/settings" element={<SettingsPage />} />
        {/* Unknown routes */}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
