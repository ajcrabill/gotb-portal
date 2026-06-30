import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // ESB brand — map to CSS variables for easy theming
        esb: {
          blue: "var(--esb-blue)",
          "blue-dark": "var(--esb-blue-dark)",
          gold: "var(--esb-gold)",
          slate: "var(--esb-slate)",
          "slate-light": "var(--esb-slate-light)",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
