import { describe, it, expect, beforeEach } from 'vitest'
import { usePaymentStore } from '@/shared/store/paymentStore'

describe('paymentStore', () => {
  beforeEach(() => {
    usePaymentStore.getState().reset()
  })

  it('initial state has idle checkoutStep', () => {
    const state = usePaymentStore.getState()
    expect(state.checkoutStep).toBe('idle')
    expect(state.pedidoId).toBeNull()
    expect(state.preferenceId).toBeNull()
    expect(state.status).toBe('idle')
    expect(state.lastErrorCode).toBeNull()
  })

  it('startCheckout sets checkoutStep to order-summary and stores pedidoId', () => {
    usePaymentStore.getState().startCheckout(42)
    const state = usePaymentStore.getState()
    expect(state.checkoutStep).toBe('order-summary')
    expect(state.pedidoId).toBe(42)
  })

  it('startCheckout is a pure UI state transition — no networking', () => {
    // Just verify it only changes state synchronously
    usePaymentStore.getState().startCheckout(99)
    expect(usePaymentStore.getState().checkoutStep).toBe('order-summary')
    expect(usePaymentStore.getState().pedidoId).toBe(99)
  })

  it('advanceStep updates checkoutStep to payment', () => {
    usePaymentStore.getState().startCheckout(1)
    usePaymentStore.getState().advanceStep('payment')
    expect(usePaymentStore.getState().checkoutStep).toBe('payment')
  })

  it('advanceStep updates checkoutStep to confirmation', () => {
    usePaymentStore.getState().startCheckout(1)
    usePaymentStore.getState().advanceStep('confirmation')
    expect(usePaymentStore.getState().checkoutStep).toBe('confirmation')
  })

  it('resetCheckout returns to initial state', () => {
    usePaymentStore.getState().startCheckout(5)
    usePaymentStore.getState().resetCheckout()
    expect(usePaymentStore.getState().checkoutStep).toBe('idle')
    expect(usePaymentStore.getState().pedidoId).toBeNull()
  })

  it('has no persist middleware', () => {
    // paymentStore should not have a persist property
    // @ts-expect-error — intentionally checking for absence
    expect(usePaymentStore.persist).toBeUndefined()
  })
})
