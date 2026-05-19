/**
 * EmptyState — shown when the catalog returns 0 products.
 */

interface EmptyStateProps {
  onReset: () => void
}

export function EmptyState({ onReset }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="text-5xl" aria-hidden="true">🔍</div>
      <p className="text-base text-muted-foreground">
        No encontramos productos con los filtros seleccionados.
      </p>
      <button
        type="button"
        onClick={onReset}
        className="rounded-md border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
      >
        Limpiar filtros
      </button>
    </div>
  )
}
