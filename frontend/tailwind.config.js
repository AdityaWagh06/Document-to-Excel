/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      boxShadow: {
        glow: '0 30px 80px rgba(15, 23, 42, 0.20)'
      },
      colors: {
        canvas: '#f5f6fa',
        ink: {
          950: '#06121f',
          900: '#0b1b2f'
        }
      }
    }
  },
  plugins: []
};
