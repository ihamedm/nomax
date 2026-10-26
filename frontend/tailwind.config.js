/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Vazirmatn Variable", "Vazirmatn", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eefdf6",
          100: "#d6f9e8",
          500: "#10a56f",
          600: "#0b8a5c",
          700: "#0a6f4b",
        },
      },
      boxShadow: {
        sheet: "0 -8px 40px -12px rgb(15 23 42 / 0.25)",
      },
      keyframes: {
        "sheet-in": {
          from: { transform: "translateY(100%)" },
          to: { transform: "translateY(0)" },
        },
        "toast-in": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "sheet-in": "sheet-in 220ms cubic-bezier(0.22, 1, 0.36, 1)",
        "toast-in": "toast-in 180ms ease-out",
      },
    },
  },
  plugins: [],
};
