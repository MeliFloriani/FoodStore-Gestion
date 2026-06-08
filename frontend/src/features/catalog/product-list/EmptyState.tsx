/**
 * EmptyState — shown when the catalog returns 0 products.
 */

import { EmptyState as SharedEmptyState } from '@/shared/ui/empty-state'

interface EmptyStateProps {
  onReset: () => void
}

export function EmptyState({ onReset }: EmptyStateProps) {
  return (
    <SharedEmptyState
      title="Sin resultados"
      description="No encontramos productos con los filtros seleccionados."
      action={
        <button
          type="button"
          onClick={onReset}
          className="rounded-md border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          Limpiar filtros
        </button>
      }
    />
  )
}
