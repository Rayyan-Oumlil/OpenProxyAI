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
          foreground: "#ffffff",
        },
        destructive: {
          DEFAULT: "var(--accent-rose)",
          foreground: "#ffffff",
        },
        success: {
          DEFAULT: "var(--accent-teal)",
          foreground: "#ffffff",
        },
        warning: {
          DEFAULT: "var(--accent-amber)",
          foreground: "#ffffff",
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
          DEFAULT: "#f0ece0",
          foreground: "var(--text)",
        },
        accent: {
          DEFAULT: "#efe9d8",
          foreground: "var(--text)",
        },
        input: "var(--line)",
        ring: "var(--accent-sky)",
      },
      borderRadius: {
        lg: "14px",
        md: "10px",
        sm: "8px",
        xl: "18px",
        "2xl": "22px",
      },
      fontFamily: {
        sans: ["Space Grotesk", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      boxShadow: {
        card: "0 10px 30px rgba(34, 36, 40, 0.08)",
        sm: "0 2px 8px rgba(34, 36, 40, 0.06)",
      },
    },
  },
  plugins: [],
};
