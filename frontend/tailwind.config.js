/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        muted: '#f1f5f9',
        'muted-foreground': '#64748b',
      },
    },
  },
  plugins: [],
}