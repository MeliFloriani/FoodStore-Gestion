/**
 * Tests for UserSearchBar component (Change 21).
 *
 * Covers:
 *   - Renders input with correct placeholder.
 *   - Calls onChange only when debounced value is >= 3 chars or empty.
 *   - Does NOT call onChange for values with 1-2 characters (only empty-string fire on mount).
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { UserSearchBar } from '../ui/UserSearchBar'

describe('UserSearchBar', () => {
  it('renders input with correct placeholder', () => {
    render(<UserSearchBar onChange={vi.fn()} />)
    expect(
      screen.getByPlaceholderText('Buscar por nombre, apellido o email...'),
    ).toBeInTheDocument()
  })

  it('calls onChange with 3+ char value after 400ms debounce', async () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<UserSearchBar onChange={onChange} />)
    const input = screen.getByPlaceholderText('Buscar por nombre, apellido o email...')

    onChange.mockClear()
    fireEvent.change(input, { target: { value: 'garcia' } })
    await act(async () => vi.advanceTimersByTime(400))
    expect(onChange).toHaveBeenCalledWith('garcia')
    vi.useRealTimers()
  })

  it('does NOT call onChange for 1-char input after debounce', async () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<UserSearchBar onChange={onChange} />)
    const input = screen.getByPlaceholderText('Buscar por nombre, apellido o email...')

    // Clear the initial-mount empty-string call
    onChange.mockClear()
    fireEvent.change(input, { target: { value: 'a' } })
    await act(async () => vi.advanceTimersByTime(400))
    // Should NOT have been called with 'a' (length < 3)
    expect(onChange).not.toHaveBeenCalledWith('a')
    vi.useRealTimers()
  })

  it('does NOT call onChange for 2-char input after debounce', async () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<UserSearchBar onChange={onChange} />)
    const input = screen.getByPlaceholderText('Buscar por nombre, apellido o email...')

    onChange.mockClear()
    fireEvent.change(input, { target: { value: 'ab' } })
    await act(async () => vi.advanceTimersByTime(400))
    // Should NOT have been called with 'ab' (length < 3)
    expect(onChange).not.toHaveBeenCalledWith('ab')
    vi.useRealTimers()
  })

  it('calls onChange with empty string when cleared', async () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<UserSearchBar onChange={onChange} />)
    const input = screen.getByPlaceholderText('Buscar por nombre, apellido o email...')

    // Type "juan" then clear
    fireEvent.change(input, { target: { value: 'juan' } })
    await act(async () => vi.advanceTimersByTime(400))
    expect(onChange).toHaveBeenCalledWith('juan')

    onChange.mockClear()
    fireEvent.change(input, { target: { value: '' } })
    await act(async () => vi.advanceTimersByTime(400))
    expect(onChange).toHaveBeenCalledWith('')
    vi.useRealTimers()
  })

  it('debounces — fires onChange only once per typing burst', async () => {
    vi.useFakeTimers()
    const onChange = vi.fn()
    render(<UserSearchBar onChange={onChange} />)
    const input = screen.getByPlaceholderText('Buscar por nombre, apellido o email...')

    onChange.mockClear()
    // Simulate fast typing: 'g' → 'ga' → 'gar' → 'garc' — each within debounce window
    fireEvent.change(input, { target: { value: 'g' } })
    await act(async () => vi.advanceTimersByTime(100))
    fireEvent.change(input, { target: { value: 'ga' } })
    await act(async () => vi.advanceTimersByTime(100))
    fireEvent.change(input, { target: { value: 'gar' } })
    await act(async () => vi.advanceTimersByTime(100))
    fireEvent.change(input, { target: { value: 'garc' } })
    // Now settle — 400ms after last change
    await act(async () => vi.advanceTimersByTime(400))

    // Should be called once with final value 'garc'
    const callsWithValue = onChange.mock.calls.filter(([v]) => v.length >= 3)
    expect(callsWithValue).toHaveLength(1)
    expect(callsWithValue[0][0]).toBe('garc')
    vi.useRealTimers()
  })
})
