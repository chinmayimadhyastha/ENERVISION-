export const ENV = {
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL || '').trim(),
  demoLatency: Number(import.meta.env.VITE_DEMO_LATENCY ?? 350),
  debug: String(import.meta.env.VITE_DEBUG || 'false') === 'true',
}

export const isLiveBackend = () => ENV.apiBaseUrl.length > 0
