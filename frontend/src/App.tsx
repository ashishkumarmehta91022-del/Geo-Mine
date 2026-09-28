import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "@/components/layout/AppLayout";
import { NAV_ITEMS } from "@/components/layout/navigation";
import DashboardPage from "@/pages/DashboardPage";
import DataExplorerPage from "@/pages/DataExplorerPage";
import DocumentsPage from "@/pages/DocumentsPage";
import KnowledgePage from "@/pages/KnowledgePage";
import PlaceholderPage from "@/pages/PlaceholderPage";
import ReportGeneratorPage from "@/pages/ReportGeneratorPage";
import ValidationPage from "@/pages/ValidationPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        {/* Live page (Step 1) */}
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Live pages (Steps 3–8) */}
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/data-explorer" element={<DataExplorerPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/validation" element={<ValidationPage />} />
        {/* Live page (Step 12) */}
        <Route path="/report-generator" element={<ReportGeneratorPage />} />
        {/* Placeholder pages for modules implemented in later steps */}
        {NAV_ITEMS.filter(
          (item) => !["/dashboard", "/documents", "/data-explorer", "/knowledge", "/validation", "/report-generator"].includes(item.path),
        ).map((item) => (
          <Route key={item.path} path={item.path} element={<PlaceholderPage />} />
        ))}
        <Route path="*" element={<PlaceholderPage />} />
      </Route>
    </Routes>
  );
}
