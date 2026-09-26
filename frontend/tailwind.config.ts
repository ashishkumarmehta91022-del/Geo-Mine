import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4fb",
          100: "#d9e6f6",
          200: "#b3cdea",
          300: "#84adda",
          400: "#558dc9",
          500: "#2f6db4",
          600: "#225795",
          700: "#1a4476",
          800: "#123257",
          900: "#0b213a",
        },
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
