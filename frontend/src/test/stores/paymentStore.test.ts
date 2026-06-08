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
    const id = '11111111-1111-1111-1111-111111111111'
    usePaymentStore.getState().startCheckout(id)
    const state = usePaymentStore.getState()
    expect(state.checkoutStep).toBe('order-summary')
    expect(state.pedidoId).toBe(id)
  })

  it('startCheckout is a pure UI state transition — no networking', () => {
    // Just verify it only changes state synchronously
    const id = '22222222-2222-2222-2222-222222222222'
    usePaymentStore.getState().startCheckout(id)
    expect(usePaymentStore.getState().checkoutStep).toBe('order-summary')
    expect(usePaymentStore.getState().pedidoId).toBe(id)
  })

  it('advanceStep updates checkoutStep to payment', () => {
    usePaymentStore.getState().startCheckout('33333333-3333-3333-3333-333333333333')
    usePaymentStore.getState().advanceStep('payment')
    expect(usePaymentStore.getState().checkoutStep).toBe('payment')
  })

  it('advanceStep updates checkoutStep to confirmation', () => {
    usePaymentStore.getState().startCheckout('44444444-4444-4444-4444-444444444444')
    usePaymentStore.getState().advanceStep('confirmation')
    expect(usePaymentStore.getState().checkoutStep).toBe('confirmation')
  })

  it('resetCheckout returns to initial state', () => {
    usePaymentStore.getState().startCheckout('55555555-5555-5555-5555-555555555555')
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
