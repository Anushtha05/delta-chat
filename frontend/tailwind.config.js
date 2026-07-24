/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        surface: {
          900: '#0f1419',
          800: '#1a2332',
          700: '#243040',
          600: '#2d3d52',
          500: '#3d5068',
        },
        accent: {
          DEFAULT: '#0891b2',
          light: '#06b6d4',
          dark: '#0e7490',
          muted: '#164e63',
        },
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
};
