/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        trace: {
          bg: '#ffffff',
          surface: '#fafafa',
          border: '#e5e7eb',
          text: '#111827',
          subtext: '#6b7280',
          accent: '#16a34a',
          accentHover: '#15803d',
        },
      },
    },
  },
  plugins: [],
}
