/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d7fd',
          300: '#a5bbfb',
          400: '#8195f7',
          500: '#6470f1',
          600: '#5355e5',
          700: '#4542ca',
          800: '#3939a3',
          900: '#333681',
        },
        surface: {
          950: '#07070f',
          900: '#0d0e1c',
          800: '#13142b',
          700: '#1a1c37',
          600: '#232546',
        },
      },
      animation: {
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
        'slide-up':   'slide-up 0.4s ease-out',
        'fade-in':    'fade-in 0.3s ease-out',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 8px 2px rgba(100,112,241,0.4)' },
          '50%':       { boxShadow: '0 0 20px 6px rgba(100,112,241,0.7)' },
        },
        'slide-up': {
          from: { opacity: 0, transform: 'translateY(16px)' },
          to:   { opacity: 1, transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: 0 },
          to:   { opacity: 1 },
        },
      },
    },
  },
  plugins: [],
}
