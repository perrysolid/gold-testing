import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brown: {
          DEFAULT: "#5A3A22",
          dark: "#3E2712",
        },
        gold: {
          DEFAULT: "#D4AF37",
          light: "#E8CC6A",
          dark: "#B8931F",
        },
        ivory: "#FBF7EE",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        headline: ["Fraunces", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
