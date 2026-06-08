/**
 * Generic destructive-action confirmation modal.
 *
 * Reused by stock CRUD pages (ingredients, categories, products).
 * Modal stays open while isPending; caller controls open/close via
 * conditional rendering (only mount when open).
 */

interface ConfirmDeleteModalProps {
  title: string
  description: string
  isPending: boolean
  onConfirm: () => void
  onClose: () => void
}

export function ConfirmDeleteModal({
  title,
  description,
  isPending,
  onConfirm,
  onClose,
}: ConfirmDeleteModalProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-delete-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-sm rounded-lg bg-background shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2
            id="confirm-delete-title"
            className="text-lg font-semibold text-destructive"
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Cerrar"
            className="rounded p-1 hover:bg-muted transition-colors disabled:opacity-50"
          >
            ✕
          </button>
        </div>
        <div className="p-4 space-y-4">
          <p className="text-sm text-muted-foreground">{description}</p>
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={isPending}
              className="rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? 'Eliminando…' : 'Eliminar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
