/**
 * AllergenosExclusion — multi-select toggle grid for allergen exclusion.
 *
 * Uses useCatalogAlergenos() from entities/products/ (public endpoint).
 * Serializes selected allergen IDs to comma-separated string for the
 * excluir_alergenos filter param.
 *
 * IMPORTANT: Uses the public GET /api/v1/catalog/ingredientes-alergenos endpoint,
 * NOT the admin-only GET /api/v1/ingredientes endpoint.
 */

import { useCatalogAlergenos } from '@/entities/products'

const ALLERGEN_LABEL_ID = 'alergenos-exclusion-label'

interface AllergenosExclusionProps {
  value: string | null | undefined
  onChange: (value: string | null) => void
}

export function AllergenosExclusion({ value, onChange }: AllergenosExclusionProps) {
  const { data, isPending } = useCatalogAlergenos()

  // Parse current selected IDs from comma-separated string
  const selectedIds = new Set(
    value ? value.split(',').filter(Boolean) : [],
  )

  function toggle(id: string) {
    const next = new Set(selectedIds)
    if (next.has(id)) {
      next.delete(id)
    } else {
      next.add(id)
    }
    const serialized = Array.from(next).join(',')
    onChange(serialized || null)
  }

  if (isPending) {
    return (
      <div className="flex flex-col gap-2">
        <span
          id={ALLERGEN_LABEL_ID}
          className="text-sm font-medium text-foreground"
        >
          Excluir alérgenos
        </span>
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-8 w-20 animate-pulse rounded-full bg-muted" />
          ))}
        </div>
      </div>
    )
  }

  if (!data || data.items.length === 0) return null

  return (
    <div
      role="group"
      aria-labelledby={ALLERGEN_LABEL_ID}
      className="flex flex-col gap-2"
    >
      <span
        id={ALLERGEN_LABEL_ID}
        className="text-sm font-medium text-foreground"
      >
        Excluir alérgenos
      </span>
      <div className="flex flex-wrap gap-2">
        {data.items.map((item) => {
          const isSelected = selectedIds.has(item.ingrediente_id)
          return (
            <button
              key={item.ingrediente_id}
              type="button"
              onClick={() => toggle(item.ingrediente_id)}
              aria-pressed={isSelected}
              className={[
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                isSelected
                  ? 'border-destructive bg-destructive text-destructive-foreground'
                  : 'border-border bg-background text-foreground hover:bg-accent hover:text-accent-foreground',
              ].join(' ')}
            >
              {item.nombre}
            </button>
          )
        })}
      </div>
    </div>
  )
}
