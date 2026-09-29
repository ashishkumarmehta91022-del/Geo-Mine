import { useLocation } from "react-router-dom";
import { Icon } from "@/components/ui/Icon";
import ThemeToggle from "@/components/ui/ThemeToggle";
import { NAV_ITEMS } from "@/components/layout/navigation";
import { useHealth } from "@/hooks/useHealth";

interface HeaderProps {
  onMenuClick: () => void;
}

/** Top bar: current page identity, live status, project identity. */
export default function Header({ onMenuClick }: HeaderProps) {
  const { pathname } = useLocation();
  const { health, isLoading, isError, refetch } = useHealth();
  const navItem = NAV_ITEMS.find((item) => item.path === pathname);

  const dbConnected = health?.database.connected === true;

  return (
    <header className="sticky top-0 z-20 border-b border-gray-200 bg-surface/95 backdrop-blur">
      <div className="flex h-16 items-center gap-4 px-4 lg:px-8">
        <button
          type="button"
          className="rounded-md p-2 text-gray-600 hover:bg-gray-100 lg:hidden"
          onClick={onMenuClick}
          aria-label="Open navigation"
        >
          <Icon name="menu" />
        </button>

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-base font-semibold text-gray-900">
            {navItem ? navItem.label : "AI-Powered Geological & Mining Reporting Platform"}
          </h1>
          {navItem?.context && (
            <p className="hidden truncate text-xs text-gray-500 md:block">{navItem.context}</p>
          )}
        </div>

        {/* Live status cluster */}
        <div className="flex items-center gap-2">
          {isLoading ? (
            <span className="hidden items-center gap-2 text-xs text-gray-500 sm:flex">
              <span className="h-2 w-2 animate-pulse rounded-full bg-gray-400" />
              Checking API…
            </span>
          ) : isError ? (
            <span className="flex items-center gap-2 text-xs font-medium text-red-600">
              <span className="h-2 w-2 rounded-full bg-red-500" />
              API offline
            </span>
          ) : (
            <div className="flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1">
              <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
                API
              </span>
              <span className="text-gray-300" aria-hidden="true">·</span>
              <span
                className={`flex items-center gap-1.5 text-xs font-medium ${
                  dbConnected ? "text-emerald-700" : "text-amber-600"
                }`}
                title={
                  health
                    ? health.database.connected
                      ? "Database connected"
                      : `Database ${health.database.detail}`
                    : undefined
                }
              >
                <span
                  className={`h-2 w-2 rounded-full ${dbConnected ? "bg-emerald-500" : "bg-amber-500"}`}
                  aria-hidden="true"
                />
                DB
              </span>
            </div>
          )}
          <button
            type="button"
            className="btn-ghost !px-2"
            onClick={() => refetch()}
            aria-label="Re-check API status"
          >
            <Icon name="refresh" className="h-4 w-4" />
          </button>
          <ThemeToggle />
        </div>

        {/* Project identity (no fake user accounts) */}
        <div className="hidden items-center gap-2 border-l border-gray-200 pl-4 md:flex">
          <div className="text-right">
            <p className="text-xs font-semibold text-gray-700">SIH 2026</p>
            <p className="text-[10px] text-gray-400">SIH26023 · CMPDI/CIL</p>
          </div>
        </div>
      </div>
    </header>
  );
}
