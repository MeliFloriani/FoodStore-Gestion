/**
 * Unit tests for useDebounce hook.
 *
 * Uses vi.useFakeTimers() to control time without waiting.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebounce } from '../hooks/useDebounce'

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('hello', 300))
    expect(result.current).toBe('hello')
  })

  it('does not update before delay elapses', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'a' } },
    )

    expect(result.current).toBe('a')

    rerender({ value: 'b' })

    // Advance time by less than the delay
    act(() => {
      vi.advanceTimersByTime(299)
    })

    expect(result.current).toBe('a') // still 'a'
  })

  it('updates after delay elapses', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'a' } },
    )

    rerender({ value: 'b' })

    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(result.current).toBe('b')
  })

  it('resets timer on rapid changes (only fires once for final value)', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: '' } },
    )

    // Simulate rapid typing
    rerender({ value: 'p' })
    act(() => { vi.advanceTimersByTime(100) })
    rerender({ value: 'pi' })
    act(() => { vi.advanceTimersByTime(100) })
    rerender({ value: 'piz' })
    act(() => { vi.advanceTimersByTime(100) })

    // Still at initial value — not enough time has passed since last change
    expect(result.current).toBe('')

    // Advance enough to trigger the debounce from the last change
    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(result.current).toBe('piz')
  })

  it('works with non-string types (numbers)', () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 200),
      { initialProps: { value: 0 } },
    )

    rerender({ value: 42 })
    act(() => { vi.advanceTimersByTime(200) })

    expect(result.current).toBe(42)
  })
})
