import { create } from 'zustand'

type CheckoutStep = 'idle' | 'order-summary' | 'payment' | 'confirmation'
type PaymentStatus = 'idle' | 'pending' | 'approved' | 'rejected' | 'error'

type PaymentState = {
  checkoutStep: CheckoutStep
  pedidoId: number | null
  preferenceId: string | null
  status: PaymentStatus
  lastErrorCode: string | null
}

type PaymentActions = {
  startCheckout: (pedidoId: number) => void
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
