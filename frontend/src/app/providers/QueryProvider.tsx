import { QueryClient, QueryClientProvider, isServer } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { isAxiosError } from 'axios'
import type { ReactNode } from 'react'

function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        gcTime: 300_000,
        retry: (failureCount, error) => {
          if (isAxiosError(error) && error.response) {
            const { status } = error.response
            if (
              status >= 400 &&
              status < 500 &&
              status !== 408 &&
              status !== 429
            ) {
              return false
            }
          }
          return failureCount < 2
        },
        refetchOnWindowFocus: !import.meta.env.DEV,
      },
    },
  })
}

// Singleton for server (SSR safety), new instance per request on server
let browserQueryClient: QueryClient | undefined

function getQueryClient(): QueryClient {
  if (isServer) {
    return makeQueryClient()
  }
  if (!browserQueryClient) {
    browserQueryClient = makeQueryClient()
  }
  return browserQueryClient
}

type QueryProviderProps = {
  children: ReactNode
}

export function QueryProvider({ children }: QueryProviderProps) {
  const queryClient = getQueryClient()

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}
