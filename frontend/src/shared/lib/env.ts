/**
 * Single source of truth for all VITE_* environment variables.
 * All modules that need env vars MUST import from this module.
 * Do NOT use import.meta.env outside this file.
 */

function requireEnv(key: string): string {
  const value = import.meta.env[key] as string | undefined
  if (!value) {
    if (import.meta.env.PROD) {
      throw new Error(`Missing required environment variable: ${key}`)
    }
    return ''
  }
  return value
}

export const env = {
  VITE_API_BASE_URL: requireEnv('VITE_API_BASE_URL'),
  VITE_MERCADOPAGO_PUBLIC_KEY: requireEnv('VITE_MERCADOPAGO_PUBLIC_KEY'),
} as const
