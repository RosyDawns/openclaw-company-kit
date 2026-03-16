/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Space Grotesk", "Noto Sans SC", "PingFang SC", "sans-serif"],
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(14, 116, 144, 0.24)" },
          "50%": { boxShadow: "0 0 0 10px rgba(14, 116, 144, 0)" },
        },
        floaty: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-5px)" },
        },
      },
      animation: {
        "fade-up": "fadeUp 420ms ease-out both",
        "pulse-glow": "pulseGlow 1.8s ease-in-out infinite",
        floaty: "floaty 3.2s ease-in-out infinite",
      },
      boxShadow: {
        velvet: "0 24px 46px -24px rgba(15, 23, 42, 0.42)",
      },
    },
  },
  plugins: [],
};
