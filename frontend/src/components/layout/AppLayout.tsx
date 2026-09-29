import { useState } from "react";
import { Outlet } from "react-router-dom";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import { ToastProvider } from "@/components/ui/Toast";

/** Application shell: navy sidebar + top header + demo banner + main area. */
export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <ToastProvider>
      <div className="flex h-full min-h-screen bg-slate-100">
        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header onMenuClick={() => setSidebarOpen(true)} />
          {/* Judge-credibility banner: the seeded dataset is synthetic. */}
          <div className="demo-banner" role="note">
            <span aria-hidden="true">◈</span>
            Demo environment · synthetic data — not official CMPDI/CIL figures
            <span aria-hidden="true">◈</span>
          </div>
          <main className="flex-1 px-4 py-6 lg:px-8">
            <Outlet />
          </main>
          <footer className="border-t border-gray-200 bg-surface px-4 py-3 text-center text-[11px] text-gray-400 lg:px-8">
            CMPDI AI Reporting · SIH26023 · From unstructured documents to verified, traceable
            intelligence
          </footer>
        </div>
      </div>
    </ToastProvider>
  );
}
