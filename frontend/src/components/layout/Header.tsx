import { Icon } from "@/components/ui/Icon";
import { useHealth } from "@/hooks/useHealth";

interface HeaderProps {
  onMenuClick: () => void;
}

/** Top navigation bar with page title, connection status and actions. */
export default function Header({ onMenuClick }: HeaderProps) {
  const { health, isLoading, isError, refetch } = useHealth();

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-gray-200 bg-white px-4 lg:px-6">
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
          AI-Powered Geological &amp; Mining Reporting Platform
        </h1>
        <p className="hidden truncate text-xs text-gray-500 sm:block">
          CMPDI · Coal India Limited subsidiaries
        </p>
      </div>

      {/* Backend connection indicator */}
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
          <span className="flex items-center gap-2 text-xs font-medium text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
            API online
            {health && (
              <>
                <span className="mx-1 text-gray-300">·</span>
                <span
                  className={`h-2 w-2 rounded-full ${
                    health.database.connected ? "bg-emerald-500" : "bg-amber-500"
                  }`}
                  title={
                    health.database.connected
                      ? "Database connected"
                      : `Database ${health.database.detail}`
                  }
                />
                <span className={health.database.connected ? "text-emerald-700" : "text-amber-600"}>
                  {health.database.connected ? "DB connected" : "DB offline"}
                </span>
              </>
            )}
          </span>
        )}
        <button
          type="button"
          className="btn-secondary !px-2.5"
          onClick={() => refetch()}
          aria-label="Re-check API status"
        >
          <Icon name="refresh" className="h-4 w-4" />
        </button>
      </div>

      <div className="flex items-center gap-2 border-l border-gray-200 pl-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
          GU
        </div>
        <span className="hidden text-sm text-gray-700 md:block">Guest User</span>
      </div>
    </header>
  );
}
