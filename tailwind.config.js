// Same configuration the page used with the Tailwind CDN, now compiled ahead
// of time. Rebuild with `npm run build` after adding new classes.
module.exports = {
  content: ['./index.html', './assets/app.js'],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'sans-serif'] },
      colors: {
        brand: { 50: '#ecfeff', 400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2', 800: '#155e75' },
        surface: {
          50: '#f8fafc',
          100: '#f1f5f9',
          800: '#1e293b',
          850: '#172032',
          900: '#0f172a',
          950: '#020617',
        },
      },
    },
  },
};
