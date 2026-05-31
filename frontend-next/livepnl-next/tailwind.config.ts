import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0d0f14",
        foreground: "#edf2f7",
        card: "#141820",
        "card-foreground": "#edf2f7",
        muted: "#202632",
        "muted-foreground": "#8d98aa",
        border: "rgba(255,255,255,0.09)",
        input: "rgba(255,255,255,0.12)",
        primary: "#b8f09a",
        "primary-foreground": "#0d0f14",
        secondary: "#f5c842",
        "secondary-foreground": "#111318",
        destructive: "#ff5f5f",
        "destructive-foreground": "#fff5f5",
        accent: "#7ee8c0",
        "accent-foreground": "#0d0f14",
      },
      fontFamily: {
        sans: ["var(--font-syne)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-jetbrains-mono)", "ui-monospace", "SFMono-Regular"],
      },
      boxShadow: {
        "black-soft": "0 18px 60px rgba(0,0,0,0.28)",
      },
    },
  },
  plugins: [],
};

export default config;
