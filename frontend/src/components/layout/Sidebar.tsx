import { NavLink } from "react-router-dom";
import { Icon } from "@/components/ui/Icon";
import { NAV_GROUPS } from "@/components/layout/navigation";
import { useHealth } from "@/hooks/useHealth";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Primary navigation sidebar. Deep-navy enterprise surface, grouped nav
 * sections with a live system-health footer. Fixed on desktop; a
 * slide-over drawer on smaller screens (controlled by the header's menu
 * button).
 */
export default function Sidebar({ open, onClose }: SidebarProps) {
  const { health } = useHealth();
  const dbConnected = health?.database.connected === true;

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `nav-item ${
      isActive
        ? "bg-navy-700 text-white"
        : "text-navy-100/80 hover:bg-navy-700/60 hover:text-white"
    }`;

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-navy-950/60 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-navy-800 bg-navy-900 text-white shadow-md transition-transform duration-200 lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Primary navigation"
      >
        {/* Brand block */}
        <div className="flex h-16 items-center gap-3 border-b border-navy-700/60 px-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-500 text-sm font-bold text-white shadow">
            CR
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-white">CMPDI AI Reporting</p>
            <p className="truncate text-[11px] text-navy-200/80">Geological &amp; Mining Intelligence</p>
          </div>
          <button
            type="button"
            className="ml-auto rounded-md p-1.5 text-navy-200 hover:bg-navy-700 lg:hidden"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <Icon name="close" className="h-5 w-5" />
          </button>
        </div>

        {/* Grouped navigation */}
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4" aria-label="Platform sections">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="px-3 pb-1.5 text-[10px] font-bold uppercase tracking-widest text-navy-300/70">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={onClose}
                    className={navClass}
                    title={item.description}
                  >
                    <Icon name={item.icon} className="h-4.5 w-4.5 h-5 w-5 shrink-0 opacity-90" />
                    <span className="truncate">{item.label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer: live database state (truthful, from /api/health) */}
        <div className="border-t border-navy-700/60 px-5 py-3">
          <div className="flex items-center gap-2 text-[11px] text-navy-200">
            <span
              className={`h-2 w-2 rounded-full ${dbConnected ? "bg-emerald-400" : "bg-amber-400"}`}
              aria-hidden="true"
            />
            {health === null
              ? "Checking database…"
              : dbConnected
                ? "PostgreSQL connected"
                : `Database ${health.database.detail}`}
          </div>
          <p className="mt-1 text-[10px] uppercase tracking-wider text-navy-300/60">
            SIH 2026 · SIH26023
          </p>
        </div>
      </aside>
    </>
  );
}
