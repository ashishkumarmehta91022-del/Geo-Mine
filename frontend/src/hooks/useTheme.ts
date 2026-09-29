import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "cmpdi-theme";

/** Saved user preference → system preference → light default. */
function resolveInitialTheme(): Theme {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // localStorage unavailable (privacy mode) — fall through
  }
  if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

/**
 * Theme controller. Applies the `dark` class to <html> (Tailwind class
 * strategy), persists the choice, and follows the OS preference live while
 * the user has not explicitly chosen.
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const initial = resolveInitialTheme();
    applyTheme(initial);
    return initial;
  });

  useEffect(() => {
    applyTheme(theme);
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // ignore persistence failures
    }
  }, [theme]);

  // Follow live OS changes only while the user hasn't chosen explicitly.
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (event: MediaQueryListEvent) => {
      let hasSaved = false;
      try {
        hasSaved = window.localStorage.getItem(STORAGE_KEY) !== null;
      } catch {
        hasSaved = false;
      }
      if (!hasSaved) setTheme(event.matches ? "dark" : "light");
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    setTheme((current) => (current === "dark" ? "light" : "dark"));
  }, []);

  return { theme, setTheme, toggle, isDark: theme === "dark" };
}

export { STORAGE_KEY as THEME_STORAGE_KEY };
