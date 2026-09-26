import { NavLink } from "react-router-dom";
import { Icon } from "@/components/ui/Icon";
import { NAV_ITEMS } from "@/components/layout/navigation";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Primary navigation sidebar. Fixed on desktop; a slide-over drawer on
 * smaller screens (controlled by the header's menu button).
 */
export default function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-gray-900/50 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-200 bg-white transition-transform duration-200 lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
        aria-label="Primary navigation"
      >
        {/* Brand block */}
        <div className="flex h-16 items-center gap-3 border-b border-gray-200 px-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand-700 text-sm font-bold text-white">
            CR
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-gray-900">CMPDI Reporting</p>
            <p className="truncate text-xs text-gray-500">SIH 2026 · SIH26023</p>
          </div>
          <button
            type="button"
            className="ml-auto rounded-md p-1.5 text-gray-500 hover:bg-gray-100 lg:hidden"
            onClick={onClose}
            aria-label="Close navigation"
          >
            <Icon name="close" className="h-5 w-5" />
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`
              }
            >
              <Icon name={item.icon} className="h-5 w-5 shrink-0" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Footer meta */}
        <div className="border-t border-gray-200 px-5 py-3">
          <p className="text-xs text-gray-400">Step 1 · Foundation build</p>
        </div>
      </aside>
    </>
  );
}
