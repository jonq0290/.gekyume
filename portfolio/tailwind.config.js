// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
    './app/**/*.{js,ts,jsx,tsx}',
    './portfolio/src/**/*.{js,ts,jsx,tsx}',
    './portfolio/app/**/*.{js,ts,jsx,tsx}',
    '../portfolio/src/**/*.{js,ts,jsx,tsx}',
    '../portfolio/app/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'dark-bg': '#0a192f',
        'accent-blue': '#64ffda',
        'accent-green': '#4ade80',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};
