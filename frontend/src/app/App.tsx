import { ErrorBoundary } from '@/app/providers/ErrorBoundary'
import { ThemeProvider } from '@/app/providers/ThemeProvider'
import { QueryProvider } from '@/app/providers/QueryProvider'
import { RouterProvider } from '@/app/providers/RouterProvider'
import { AuthSync } from '@/app/providers/AuthSync'

export function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <QueryProvider>
          <AuthSync />
          <RouterProvider />
        </QueryProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}
