/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'panel-bg': '#161b22',
        'border-line': '#30363d',
        'text-green': '#3fb950',
        'text-red': '#f85149',
      },
    },
  },
  plugins: [],
}
