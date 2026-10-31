/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['"Space Grotesk"', '"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        /* Clean public-sector slate / white surface foundation */
        graphite: {
          950: '#f8fafc',
          900: '#ffffff',
          880: '#f8fafc',
          850: '#f1f5f9',
          800: '#e2e8f0',
          750: '#cbd5e1',
          700: '#e2e8f0',
          650: '#cbd5e1',
          600: '#94a3b8',
          500: '#64748b',
          400: '#475569',
          300: '#334155',
          200: '#1e293b',
          100: '#0f172a',
        },
        /* Primary official energy green scale (Emerald / Teal) */
        brand: {
          50: '#ecfdf5',
          100: '#d1fae5',
          200: '#a7f3d0',
          300: '#6ee7b7',
          400: '#10b981',
          500: '#059669',
          600: '#047857',
          700: '#0f766e',
          800: '#065f46',
          900: '#064e3b',
          950: '#022c22',
        },
        /* Solar accent — amber/gold */
        solar: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
        /* Wind accent — sky/cyan */
        wind: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
      },
      boxShadow: {
        panel: '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)',
        'panel-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.07), 0 4px 6px -4px rgba(0, 0, 0, 0.05)',
        'glow-brand': '0 0 0 1px rgba(16, 185, 129, 0.25), 0 0 20px -5px rgba(5, 150, 105, 0.3)',
        'glow-solar': '0 0 0 1px rgba(245, 158, 11, 0.25), 0 0 20px -5px rgba(217, 119, 6, 0.3)',
        'glow-wind': '0 0 0 1px rgba(14, 165, 233, 0.25), 0 0 20px -5px rgba(2, 132, 199, 0.3)',
        hairline: 'inset 0 0 0 1px rgba(148, 163, 184, 0.20)',
      },
      backgroundImage: {
        'signal-brand': 'linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0) 60%)',
        'signal-solar': 'linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(245, 158, 11, 0) 60%)',
        'signal-wind': 'linear-gradient(135deg, rgba(14, 165, 233, 0.12) 0%, rgba(14, 165, 233, 0) 60%)',
        'panel-sheen': 'linear-gradient(180deg, rgba(255, 255, 255, 0.8) 0%, rgba(255, 255, 255, 0) 40%)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateX(-10px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        'ping-ring': {
          '0%': { transform: 'scale(0.7)', opacity: '0.55' },
          '70%': { transform: 'scale(2.1)', opacity: '0' },
          '100%': { transform: 'scale(2.1)', opacity: '0' },
        },
        'node-breathe': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.85' },
          '50%': { transform: 'scale(1.14)', opacity: '1' },
        },
        'dash-flow': {
          to: { strokeDashoffset: '-28' },
        },
        sweep: {
          to: { transform: 'rotate(360deg)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in': 'fade-in 0.45s ease-out both',
        'slide-in': 'slide-in 0.35s cubic-bezier(0.22, 1, 0.36, 1) both',
        'pulse-soft': 'pulse-soft 2.4s ease-in-out infinite',
        'ping-ring': 'ping-ring 2.8s cubic-bezier(0, 0, 0.2, 1) infinite',
        'node-breathe': 'node-breathe 3.2s ease-in-out infinite',
        'dash-flow': 'dash-flow 1.1s linear infinite',
        sweep: 'sweep 9s linear infinite',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
}
