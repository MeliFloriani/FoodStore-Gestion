/**
 * API endpoint path constants.
 * Do NOT include base URL — that comes from env.VITE_API_BASE_URL via http.ts.
 */
export const AUTH_LOGIN = '/auth/login' as const
export const AUTH_REFRESH = '/auth/refresh' as const
export const AUTH_ME = '/auth/me' as const
export const AUTH_REGISTER = '/auth/register' as const
export const AUTH_LOGOUT = '/auth/logout' as const

// Catalog — Categories (Change 09)
export const CATEGORIAS = '/api/v1/categorias' as const

// Catalog — Ingredients (Change 10)
export const INGREDIENTES = '/api/v1/ingredientes' as const

// Catalog — Products (Change 11)
export const PRODUCTOS = '/api/v1/productos' as const
