import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "@/components/layout/AppLayout";
import { NAV_ITEMS } from "@/components/layout/navigation";
import DashboardPage from "@/pages/DashboardPage";
import PlaceholderPage from "@/pages/PlaceholderPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        {/* Live page (Step 1) */}
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Placeholder pages for modules implemented in later steps */}
        {NAV_ITEMS.filter((item) => item.path !== "/dashboard").map((item) => (
          <Route key={item.path} path={item.path} element={<PlaceholderPage />} />
        ))}
        <Route path="*" element={<PlaceholderPage />} />
      </Route>
    </Routes>
  );
}
