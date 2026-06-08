import type { ToastItem } from './toast.types'

interface ToastProps {
  item: ToastItem
  onDismiss: (id: string) => void
}

const VARIANT_CLASSES: Record<string, string> = {
  success: 'border-l-4 border-success-500 bg-card text-foreground',
  error: 'border-l-4 border-danger-500 bg-card text-foreground',
  warning: 'border-l-4 border-warning-500 bg-card text-foreground',
  info: 'border-l-4 border-info-500 bg-card text-foreground',
}

const VARIANT_ICONS: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
}

export function Toast({ item, onDismiss }: ToastProps) {
  return (
    <div
      role="status"
      className={`flex items-start gap-3 rounded-md p-4 shadow-md animate-in fade-in slide-in-from-bottom-2 duration-250 ${VARIANT_CLASSES[item.variant] ?? 'bg-card text-foreground border border-border'}`}
      style={{ minWidth: '280px', maxWidth: '420px' }}
    >
      <span aria-hidden="true" className="mt-0.5 text-sm font-bold shrink-0">
        {VARIANT_ICONS[item.variant]}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">{item.title}</p>
        {item.description && (
          <p className="mt-0.5 text-xs text-muted-foreground">{item.description}</p>
        )}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(item.id)}
        aria-label="Cerrar notificación"
        className="shrink-0 ml-1 text-muted-foreground hover:text-foreground transition-colors"
      >
        ×
      </button>
    </div>
  )
}
