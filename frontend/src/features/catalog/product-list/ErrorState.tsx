/**
 * ErrorState — shown when the catalog query returns an error.
 */

interface ErrorStateProps {
  onRetry: () => void
}

export function ErrorState({ onRetry }: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="text-5xl" aria-hidden="true">⚠️</div>
      <p className="text-base text-muted-foreground">
        Ocurrió un error al cargar los productos. Por favor, intentá de nuevo.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Reintentar
      </button>
    </div>
  )
}
