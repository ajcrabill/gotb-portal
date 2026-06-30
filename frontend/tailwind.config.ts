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
        esb: {
          primary:      "#2596be",
          "primary-dark": "#1a7a9e",
          dark:         "#111111",
          text:         "#444444",
          muted:        "#aaaaaa",
          border:       "#b9b9b9",
          footer:       "#111111",
          section:      "#2d3e6e",
          light:        "#fafafa",
        },
      },
      fontFamily: {
        sans:    ["Open Sans", "system-ui", "sans-serif"],
        heading: ["Raleway", "system-ui", "sans-serif"],
        logo:    ["Poppins", "system-ui", "sans-serif"],
      },
      fontSize: {
        "2xs": "13px",
        xs:    "14px",
        sm:    "15px",
        base:  "15px",
        lg:    "16px",
        xl:    "18px",
        "2xl": "20px",
        "3xl": "24px",
        "4xl": "26px",
        "5xl": "32px",
        "6xl": "34px",
        "7xl": "40px",
      },
      boxShadow: {
        card:   "0px 2px 35px rgba(0, 0, 0, 0.06)",
        hover:  "0 4px 16px rgba(0, 0, 0, 0.1)",
        header: "0px 2px 15px rgba(0, 0, 0, 0.1)",
        dropdown: "0px 0px 30px rgba(127, 137, 161, 0.25)",
      },
      borderRadius: {
        sm:   "4px",
        md:   "5px",
        pill: "50px",
      },
    },
  },
  plugins: [],
};

export default config;
