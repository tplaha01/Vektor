import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#090b0f",
        foreground: "#e8edf5",
        card: "#11151c",
        "card-foreground": "#e8edf5",
        muted: "#1b202a",
        "muted-foreground": "#8b95a8",
        border: "rgba(255,255,255,0.09)",
        input: "rgba(255,255,255,0.12)",
        primary: "#b8f09a",
        "primary-foreground": "#090b0f",
        secondary: "#f5c842",
        "secondary-foreground": "#111318",
        destructive: "#ff5f5f",
        "destructive-foreground": "#fff5f5",
        accent: "#7ee8c0",
        "accent-foreground": "#090b0f",
      },
      fontFamily: {
        sans: ["var(--font-syne)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "SFMono-Regular"],
      },
      boxShadow: {
        "black-soft": "0 18px 60px rgba(0,0,0,0.32)",
      },
    },
  },
  plugins: [],
};

export default config;
