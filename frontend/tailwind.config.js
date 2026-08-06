/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        gis: {
          dark: '#0a0d14',
          panel: '#121824',
          border: '#1f293d',
          accent: '#3b82f6',
          cyan: '#06b6d4',
          emerald: '#10b981',
          gold: '#f59e0b'
        }
      }
    },
  },
  plugins: [],
}
