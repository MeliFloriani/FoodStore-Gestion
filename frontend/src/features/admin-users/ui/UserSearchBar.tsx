/**
 * UserSearchBar — debounced search input for user management.
 *
 * Change 21: admin-users-management.
 *
 * - Debounce: 400ms via useDebounce from shared/hooks.
 * - Only calls onChange if q.length >= 3 or q === "" (prevents short-term queries).
 * - Placeholder: "Buscar por nombre, apellido o email..."
 */

import { useState, useEffect } from 'react'
import { useDebounce } from '@/shared/hooks/useDebounce'

interface UserSearchBarProps {
  onChange: (value: string) => void
  disabled?: boolean
}

export function UserSearchBar({ onChange, disabled = false }: UserSearchBarProps) {
  const [rawValue, setRawValue] = useState('')
  const debouncedValue = useDebounce(rawValue, 400)

  useEffect(() => {
    // Only propagate if q.length >= 3 or q is empty
    if (debouncedValue.length === 0 || debouncedValue.length >= 3) {
      onChange(debouncedValue)
    }
  }, [debouncedValue, onChange])

  return (
    <div className="relative w-full max-w-md">
      <input
        type="search"
        value={rawValue}
        onChange={(e) => setRawValue(e.target.value)}
        placeholder="Buscar por nombre, apellido o email..."
        disabled={disabled}
        aria-label="Buscar usuarios"
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
      />
    </div>
  )
}
