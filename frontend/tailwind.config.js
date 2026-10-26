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
        /* Deep graphite / charcoal foundation — the control-room surface scale. */
        graphite: {
          950: '#05080c',
          900: '#0a0f15',
          880: '#0c1219',
          850: '#0f161e',
          800: '#121b24',
          750: '#16212c',
          700: '#1c2934',
          650: '#22303c',
          600: '#2b3a47',
          500: '#3d4f5e',
          400: '#5c7080',
          300: '#8496a5',
          200: '#b4c1cc',
          100: '#dbe2e9',
        },
        /* Primary energy accent — teal. */
        brand: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488',
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
          950: '#042f2e',
        },
        /* Solar accent — amber/yellow. */
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
        /* Wind accent — cyan. */
        wind: {
          50: '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
          700: '#0e7490',
          800: '#155e75',
          900: '#164e63',
        },
      },
      boxShadow: {
        panel:
          'inset 0 1px 0 0 rgba(255,255,255,0.03), 0 10px 30px -18px rgba(0,0,0,0.9)',
        'panel-lg':
          'inset 0 1px 0 0 rgba(255,255,255,0.045), 0 30px 70px -30px rgba(0,0,0,0.95)',
        'glow-brand': '0 0 0 1px rgba(45,212,191,0.22), 0 0 28px -6px rgba(20,184,166,0.5)',
        'glow-solar': '0 0 0 1px rgba(251,191,36,0.28), 0 0 26px -6px rgba(245,158,11,0.55)',
        'glow-wind': '0 0 0 1px rgba(34,211,238,0.28), 0 0 26px -6px rgba(6,182,212,0.55)',
        hairline: 'inset 0 0 0 1px rgba(148,163,184,0.10)',
      },
      backgroundImage: {
        'signal-brand':
          'linear-gradient(135deg, rgba(45,212,191,0.16) 0%, rgba(45,212,191,0) 60%)',
        'signal-solar':
          'linear-gradient(135deg, rgba(251,191,36,0.16) 0%, rgba(251,191,36,0) 60%)',
        'signal-wind':
          'linear-gradient(135deg, rgba(34,211,238,0.16) 0%, rgba(34,211,238,0) 60%)',
        'panel-sheen':
          'linear-gradient(180deg, rgba(255,255,255,0.035) 0%, rgba(255,255,255,0) 40%)',
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
        scanline: {
          '0%': { transform: 'translateY(-120%)', opacity: '0' },
          '10%': { opacity: '0.9' },
          '90%': { opacity: '0.9' },
          '100%': { transform: 'translateY(520%)', opacity: '0' },
        },
        sweep: {
          to: { transform: 'rotate(360deg)' },
        },
        'rise-bar': {
          '0%': { transform: 'scaleY(0.02)' },
          '100%': { transform: 'scaleY(1)' },
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
        scanline: 'scanline 5.5s linear infinite',
        sweep: 'sweep 9s linear infinite',
      },
      transitionTimingFunction: {
        smooth: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
}
