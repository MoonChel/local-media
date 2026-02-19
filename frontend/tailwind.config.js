/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        base: '#0d1117',
        panel: '#111827',
        accent: '#f97316',
        muted: '#9ca3af'
      }
    },
  },
  plugins: [],
}
