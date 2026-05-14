import { isAxiosError } from 'axios'

export type AppErrorCode =
  | 'AUTH_EXPIRED'
  | 'FORBIDDEN'
  | 'VALIDATION_ERROR'
  | 'NOT_FOUND'
  | 'RATE_LIMITED'
  | 'SERVER_ERROR'
  | 'UNKNOWN'

export type AppError = {
  code: AppErrorCode
  message: string
  status: number | null
  fieldErrors?: Record<string, string[]>
}

/**
 * Derive the field key from a FastAPI validation error `loc` array using the D-H rule:
 *
 * - If loc[0] === "body" and loc.length === 2  →  key = loc[1]
 * - If loc[0] === "body" and loc.length > 2   →  key = loc.slice(1).join(".")
 * - If loc[0] !== "body"                       →  key = loc.join(".")
 *
 * All `loc` entries are converted to strings to handle numeric indices gracefully.
 */
function deriveFieldKey(loc: unknown[]): string {
  const parts = loc.map(String)
  if (parts.length === 0) return 'unknown'
  if (parts[0] === 'body') {
    if (parts.length === 2) return parts[1]
    return parts.slice(1).join('.')
  }
  return parts.join('.')
}

/**
 * Parse a FastAPI 422 validation error response body into a fieldErrors map.
 *
 * FastAPI returns: { detail: [{ loc: string[], msg: string, type: string }] }
 *
 * Multiple errors for the same field are accumulated into an array.
 * Falls back gracefully if the detail is not an array (flat-string or unknown format).
 */
function parse422Detail(rawDetail: unknown): Record<string, string[]> | undefined {
  if (!Array.isArray(rawDetail)) return undefined

  const fieldErrors: Record<string, string[]> = {}
  let hasEntries = false

  for (const item of rawDetail) {
    if (
      item === null ||
      typeof item !== 'object' ||
      !Array.isArray((item as Record<string, unknown>).loc) ||
      typeof (item as Record<string, unknown>).msg !== 'string'
    ) {
      continue
    }

    const loc = (item as { loc: unknown[] }).loc
    const msg = (item as { msg: string }).msg
    const key = deriveFieldKey(loc)

    if (!fieldErrors[key]) {
      fieldErrors[key] = []
    }
    fieldErrors[key].push(msg)
    hasEntries = true
  }

  return hasEntries ? fieldErrors : undefined
}

export function normalizeError(error: unknown): AppError {
  if (isAxiosError(error)) {
    const status = error.response?.status ?? null

    if (status === 401) {
      return {
        code: 'AUTH_EXPIRED',
        message: error.response?.data?.detail ?? 'Authentication expired',
        status,
      }
    }

    if (status === 403) {
      return {
        code: 'FORBIDDEN',
        message: error.response?.data?.detail ?? 'Access forbidden',
        status,
      }
    }

    if (status === 404) {
      return {
        code: 'NOT_FOUND',
        message: error.response?.data?.detail ?? 'Resource not found',
        status,
      }
    }

    if (status === 422) {
      const rawDetail = error.response?.data?.detail as unknown
      const fieldErrors = parse422Detail(rawDetail)

      return {
        code: 'VALIDATION_ERROR',
        message: 'Validation error',
        status,
        ...(fieldErrors ? { fieldErrors } : {}),
      }
    }

    if (status === 429) {
      return {
        code: 'RATE_LIMITED',
        message: error.response?.data?.detail ?? 'Too many requests',
        status,
      }
    }

    if (status !== null && status >= 500) {
      return {
        code: 'SERVER_ERROR',
        message: error.response?.data?.detail ?? 'Internal server error',
        status,
      }
    }

    // Axios error without a response (network error, timeout, etc.)
    return {
      code: 'UNKNOWN',
      message: error.message,
      status: null,
    }
  }

  if (error instanceof Error) {
    return {
      code: 'UNKNOWN',
      message: error.message,
      status: null,
    }
  }

  return {
    code: 'UNKNOWN',
    message: 'An unknown error occurred',
    status: null,
  }
}
