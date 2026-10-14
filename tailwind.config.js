/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: { 50:'#eef4ff',100:'#dbe7fe',600:'#1d4ed8',700:'#1e40af',800:'#1e3a8a',900:'#172554' },
        ink: { 950:'#080f24', 900:'#0d1630', 800:'#14203f', 700:'#1d2c55' },
      },
      fontFamily: {
        sans: ['Inter','system-ui','-apple-system','Segoe UI','sans-serif'],
        display: ['"Plus Jakarta Sans"','Inter','system-ui','sans-serif'],
      },
      boxShadow: {
        lift: '0 1px 2px rgba(8,15,36,.05), 0 10px 30px -10px rgba(8,15,36,.16)',
        carddark: '0 1px 2px rgba(0,0,0,.3), 0 12px 32px -12px rgba(0,0,0,.5)',
      },
      keyframes: {
        'vg-ecg': { to: { 'stroke-dashoffset': '-480' } },
        'vg-drift': { '0%,100%': { transform: 'translate3d(0,0,0)' }, '50%': { transform: 'translate3d(26px,-16px,0)' } },
      },
      animation: {
        'vg-ecg': 'vg-ecg 6s linear infinite',
        'vg-drift': 'vg-drift 16s ease-in-out infinite',
      },
    }
  },
  plugins: []
}
