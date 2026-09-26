import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "@/components/layout/AppLayout";
import { NAV_ITEMS } from "@/components/layout/navigation";
import DashboardPage from "@/pages/DashboardPage";
import DocumentsPage from "@/pages/DocumentsPage";
import PlaceholderPage from "@/pages/PlaceholderPage";
import ValidationPage from "@/pages/ValidationPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        {/* Live page (Step 1) */}
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Live pages (Steps 3–6) */}
        <Route path="/documents" element={<DocumentsPage />} />
        <Route path="/validation" element={<ValidationPage />} />
        {/* Placeholder pages for modules implemented in later steps */}
        {NAV_ITEMS.filter(
          (item) => !["/dashboard", "/documents", "/validation"].includes(item.path),
        ).map((item) => (
          <Route key={item.path} path={item.path} element={<PlaceholderPage />} />
        ))}
        <Route path="*" element={<PlaceholderPage />} />
      </Route>
    </Routes>
  );
}
