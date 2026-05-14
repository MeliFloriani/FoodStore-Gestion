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
  status?: number
  details?: Record<string, unknown>
}

export function normalizeError(error: unknown): AppError {
  if (isAxiosError(error)) {
    const status = error.response?.status

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
      const details: Record<string, unknown> =
        rawDetail !== null && typeof rawDetail === 'object' && !Array.isArray(rawDetail)
          ? (rawDetail as Record<string, unknown>)
          : { raw: rawDetail }

      return {
        code: 'VALIDATION_ERROR',
        message: 'Validation error',
        status,
        details,
      }
    }

    if (status === 429) {
      return {
        code: 'RATE_LIMITED',
        message: error.response?.data?.detail ?? 'Too many requests',
        status,
      }
    }

    if (status !== undefined && status >= 500) {
      return {
        code: 'SERVER_ERROR',
        message: error.response?.data?.detail ?? 'Internal server error',
        status,
      }
    }
  }

  if (error instanceof Error) {
    return {
      code: 'UNKNOWN',
      message: error.message,
    }
  }

  return {
    code: 'UNKNOWN',
    message: 'An unknown error occurred',
  }
}
