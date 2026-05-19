/**
 * Generic debounce hook.
 *
 * Returns the debounced value of `value` — only updates after `delayMs`
 * milliseconds of no change. Useful for search inputs to avoid firing
 * a query on every keystroke.
 *
 * Usage:
 *   const debouncedQ = useDebounce(rawQ, 300)
 */

import { useState, useEffect } from 'react'

export function useDebounce<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value)

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(value)
    }, delayMs)

    return () => {
      clearTimeout(timer)
    }
  }, [value, delayMs])

  return debounced
}
