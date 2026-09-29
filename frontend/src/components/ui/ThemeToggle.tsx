import { useTheme } from "@/hooks/useTheme";

/** Sun/moon theme toggle for the top bar (persisted, FOUC-free). */
export default function ThemeToggle() {
  const { isDark, toggle } = useTheme();

  return (
    <button
      type="button"
      onClick={toggle}
      className="btn-ghost !px-2"
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? (
        // Sun icon (currently dark → offer light)
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
          strokeLinecap="round" strokeLinejoin="round" className="h-4.5 w-4.5 h-5 w-5" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2" />
          <path d="M12 20v2" />
          <path d="m4.93 4.93 1.41 1.41" />
          <path d="m17.66 17.66 1.41 1.41" />
          <path d="M2 12h2" />
          <path d="M20 12h2" />
          <path d="m6.34 17.66-1.41 1.41" />
          <path d="m19.07 4.93-1.41 1.41" />
        </svg>
      ) : (
        // Moon icon (currently light → offer dark)
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
          strokeLinecap="round" strokeLinejoin="round" className="h-4.5 w-4.5 h-5 w-5" aria-hidden="true">
          <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z" />
        </svg>
      )}
    </button>
  );
}
