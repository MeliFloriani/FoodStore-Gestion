import { create } from 'zustand'

type CheckoutStep = 'idle' | 'order-summary' | 'payment' | 'confirmation'
type PaymentStatus = 'idle' | 'pending' | 'approved' | 'rejected' | 'error'

type PaymentState = {
  checkoutStep: CheckoutStep
  // Change 19: pedidoId is a UUID string (was number in Change 17 placeholder)
  pedidoId: string | null
  preferenceId: string | null
  status: PaymentStatus
  lastErrorCode: string | null
}

type PaymentActions = {
  // Change 19: pedidoId is UUID string (was number)
  startCheckout: (pedidoId: string) => void
  advanceStep: (step: 'payment' | 'confirmation') => void
  resetCheckout: () => void
  setPreferenceId: (preferenceId: string) => void
  setStatus: (status: PaymentStatus) => void
  setLastErrorCode: (code: string | null) => void
  reset: () => void
}

type PaymentStore = PaymentState & PaymentActions

const initialState: PaymentState = {
  checkoutStep: 'idle',
  pedidoId: null,
  preferenceId: null,
  status: 'idle',
  lastErrorCode: null,
}

export const usePaymentStore = create<PaymentStore>()((set) => ({
  ...initialState,

  startCheckout: (pedidoId) =>
    set({ checkoutStep: 'order-summary', pedidoId }),

  advanceStep: (step) => set({ checkoutStep: step }),

  resetCheckout: () => set(initialState),

  setPreferenceId: (preferenceId) => set({ preferenceId }),

  setStatus: (status) => set({ status }),

  setLastErrorCode: (lastErrorCode) => set({ lastErrorCode }),

  reset: () => set(initialState),
}))
