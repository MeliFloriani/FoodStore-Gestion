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

// Public Catalog (Change 12)
export const CATALOG_PRODUCTOS = '/api/v1/catalog/productos' as const
export const CATALOG_ALERGENOS = '/api/v1/catalog/ingredientes-alergenos' as const

// Profile (Change 13 — customer-profile-management)
export const PROFILE_ME = '/api/v1/profile/me' as const
export const PROFILE_ME_PASSWORD = '/api/v1/profile/me/password' as const
