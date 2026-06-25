import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#040b16",
          900: "#0A1A2F",
          800: "#0F2340",
          700: "#16314F"
        },
        gold: {
          500: "#C9A24B",
          400: "#D9B872",
          300: "#E8CF91"
        },
        champagne: "#EDE3C8",
        porcelain: "#F7F8FA",
        muted: "#9FB0C3"
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "Arial", "sans-serif"],
        display: ["var(--font-manrope)", "Manrope", "Inter", "sans-serif"]
      },
      boxShadow: {
        glow: "0 24px 80px rgba(201, 162, 75, 0.16)"
      }
    }
  },
  plugins: []
};

export default config;
