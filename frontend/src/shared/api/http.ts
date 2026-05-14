import axios, { type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'
import { env } from '@/shared/lib/env'
import { AUTH_REFRESH, AUTH_LOGIN } from '@/shared/api/endpoints'

// Lazily imported to avoid circular deps — only getState() is used
import { useAuthStore } from '@/entities/auth/model/store'

type RefreshResponse = {
  access_token: string
  refresh_token: string
}

type RetryConfig = InternalAxiosRequestConfig & {
  __isRetry?: boolean
}

type QueueEntry = {
  resolve: (token: string) => void
  reject: (reason: unknown) => void
}

let refreshPromise: Promise<string> | null = null
const failedQueue: QueueEntry[] = []

function processQueue(error: unknown, token: string | null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (token) {
      resolve(token)
    } else {
      reject(error)
    }
  })
  failedQueue.length = 0
}

export const http = axios.create({
  baseURL: env.VITE_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach Bearer token if available
http.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    const token = useAuthStore.getState().accessToken
    if (token) {
      config.headers = config.headers ?? {}
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: unknown) => Promise.reject(error),
)

// Response interceptor: handle 401 with refresh queue
http.interceptors.response.use(
  (response: AxiosResponse) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || !error.config) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as RetryConfig
    const status = error.response?.status
    const url = originalRequest.url ?? ''

    // Skip 401 handling for retry requests and auth endpoints
    const isRetry = originalRequest.__isRetry === true
    const isAuthEndpoint =
      url.includes(AUTH_REFRESH) || url.includes(AUTH_LOGIN)

    if (status !== 401 || isRetry || isAuthEndpoint) {
      return Promise.reject(error)
    }

    if (refreshPromise) {
      // Another request is already refreshing — queue this one
      return new Promise<AxiosResponse>((resolve, reject) => {
        failedQueue.push({
          resolve: (token: string) => {
            originalRequest.headers = originalRequest.headers ?? {}
            originalRequest.headers.Authorization = `Bearer ${token}`
            originalRequest.__isRetry = true
            resolve(http(originalRequest))
          },
          reject,
        })
      })
    }

    // Acquire refresh lock
    refreshPromise = new Promise<string>((resolve, reject) => {
      const refreshToken = useAuthStore.getState().refreshToken

      http
        .post<RefreshResponse>(AUTH_REFRESH, { refresh_token: refreshToken })
        .then((response) => {
          const { access_token, refresh_token } = response.data

          // 1. Update store with new tokens
          useAuthStore.getState().updateTokens(access_token, refresh_token)

          // 2. Resolve the refresh promise
          resolve(access_token)

          // 3. Dispatch all queued requests with new token
          processQueue(null, access_token)

          // 4. Set refreshPromise to null LAST
          refreshPromise = null
        })
        .catch((refreshError: unknown) => {
          // 1. Logout from store
          useAuthStore.getState().logout()

          // 2. Reject all queued requests
          processQueue(refreshError, null)

          // 3. Dispatch auth:expired event
          window.dispatchEvent(new CustomEvent('auth:expired'))

          // 4. Set refreshPromise to null
          refreshPromise = null

          reject(refreshError)
        })
    })

    return refreshPromise.then((token: string) => {
      originalRequest.headers = originalRequest.headers ?? {}
      originalRequest.headers.Authorization = `Bearer ${token}`
      originalRequest.__isRetry = true
      return http(originalRequest)
    })
  },
)
