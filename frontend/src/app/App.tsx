import { ErrorBoundary } from '@/app/providers/ErrorBoundary'
import { ThemeProvider } from '@/app/providers/ThemeProvider'
import { QueryProvider } from '@/app/providers/QueryProvider'
import { RouterProvider } from '@/app/providers/RouterProvider'
import { AuthSync } from '@/app/providers/AuthSync'
import { ToastProvider } from '@/shared/ui/toast'
import { ConfirmDialogProvider } from '@/shared/ui/confirm-dialog'

export function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <QueryProvider>
          {/* Change 19 (Checkout Pro migration): MercadoPagoProvider removed.
              @mercadopago/sdk-react is no longer used — MP hosts the checkout page.
              No VITE_MP_PUBLIC_KEY required in frontend. */}
          <ToastProvider>
            <ConfirmDialogProvider>
              <AuthSync />
              <RouterProvider />
            </ConfirmDialogProvider>
          </ToastProvider>
        </QueryProvider>
      </ThemeProvider>
    </ErrorBoundary>
  )
}
