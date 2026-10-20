import type { Config } from "tailwindcss";

// Drafting-table palette: cool paper, survey ink, and brass reserved for orientation
// (North, centre, grid) so the accent always means "direction".
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./features/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F1F4F3",
        ink: { DEFAULT: "#16283A", soft: "#2C4156" },
        slate: "#5A6B7B",
        hairline: "#D3DADF",
        brass: { DEFAULT: "#9C6B1C", light: "#F3E7D0" },
        positive: { DEFAULT: "#2F7355", light: "#E3F0E9" },
        warning: { DEFAULT: "#B0731A", light: "#F8ECD8" },
        major: { DEFAULT: "#A8322F", light: "#F6E1E0" },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        display: ['"Newsreader"', "Georgia", "Cambria", "serif"],
      },
      borderRadius: { sm: "3px", DEFAULT: "5px", lg: "8px" },
    },
  },
  plugins: [],
} satisfies Config;
