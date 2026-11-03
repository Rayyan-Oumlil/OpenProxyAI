/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  corePlugins: {
    // Don't reset global styles — existing vanilla CSS handles that
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        background: "var(--bg)",
        surface: "var(--surface)",
        foreground: "var(--text)",
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted)",
        },
        border: "var(--line)",
        primary: {
          DEFAULT: "var(--accent-sky)",
          foreground: "var(--accent-ink)",
        },
        destructive: {
          DEFAULT: "var(--accent-rose)",
          foreground: "var(--accent-ink)",
        },
        success: {
          DEFAULT: "var(--accent-teal)",
          foreground: "var(--accent-ink)",
        },
        warning: {
          DEFAULT: "var(--accent-amber)",
          foreground: "var(--accent-ink)",
        },
        card: {
          DEFAULT: "var(--surface)",
          foreground: "var(--text)",
        },
        popover: {
          DEFAULT: "var(--surface)",
          foreground: "var(--text)",
        },
        secondary: {
          DEFAULT: "var(--bg-sunken)",
          foreground: "var(--text)",
        },
        accent: {
          DEFAULT: "var(--bg-hover)",
          foreground: "var(--text)",
        },
        input: "var(--line)",
        ring: "var(--accent-sky)",
      },
      borderRadius: {
        lg: "10px",
        md: "6px",
        sm: "4px",
        xl: "12px",
        "2xl": "14px",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      boxShadow: {
        card: "none",
        sm: "none",
      },
    },
  },
  plugins: [],
};
