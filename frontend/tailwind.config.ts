import type { Config } from "tailwindcss";

/**
 * Palette strategy: every semantic palette resolves to CSS variables
 * (`--c-*`, RGB channel triplets) declared in src/index.css. Light values
 * live on :root; .dark overrides them with role-mapped dark values — so
 * every existing `bg-white`, `text-gray-600`, badge tint, etc. adapts to
 * dark mode automatically without per-component hardcoding. Opacity
 * modifiers (e.g. bg-slate-100/80) keep working via `<alpha-value>`.
 *
 * `navy` stays literal: the sidebar is intentionally dark in BOTH themes.
 */
const ch = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

const scale = (name: string, shades: number[]) =>
  Object.fromEntries(shades.map((s) => [s, ch(`${name}-${s}`)]));

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        /** Theme-aware card/top-bar surface (white in light, elevated slate in dark). */
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        navy: {
          50: "#f0f4fa",
          100: "#d9e2f0",
          200: "#b3c5df",
          300: "#84a2c8",
          400: "#5580ac",
          500: "#34628e",
          600: "#264d73",
          700: "#1c3a58",
          800: "#142a41",
          900: "#0d1c2c",
          950: "#081220",
        },
        brand: scale("brand", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        gray: scale("gray", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        slate: scale("slate", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        emerald: scale("emerald", [50, 200, 300, 500, 600, 700, 800, 900]),
        amber: scale("amber", [50, 200, 300, 500, 600, 700, 800, 900]),
        red: scale("red", [50, 200, 300, 500, 600, 700, 800, 900]),
        violet: scale("violet", [50, 200, 300, 500, 600, 700, 800, 900]),
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
} satisfies Config;
