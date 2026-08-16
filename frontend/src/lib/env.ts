const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim()

// In local Vite development, an empty value uses the same-origin `/api` proxy.
// Deployment environments provide their public API URL explicitly.
export const apiBaseUrl = (
  configuredApiBaseUrl ?? (import.meta.env.DEV ? '' : 'http://localhost:8000')
).replace(/\/$/, '')
