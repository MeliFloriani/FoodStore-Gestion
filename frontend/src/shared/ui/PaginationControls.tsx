/**
 * Accessible pagination controls component.
 *
 * Renders prev/next buttons and numeric page buttons with ellipsis for long ranges.
 * Follows WAI-ARIA pagination pattern.
 *
 * Props:
 *   page          — current page (1-based)
 *   pages         — total number of pages
 *   onPageChange  — callback when a page button is clicked
 *   disabled      — disables all controls (e.g. while loading)
 */

interface PaginationControlsProps {
  page: number
  pages: number
  onPageChange: (newPage: number) => void
  disabled?: boolean
}

/**
 * Build the list of page numbers to render, with null as an ellipsis sentinel.
 * Shows: first page, ellipsis, (current-1, current, current+1), ellipsis, last page.
 * If pages <= 7, shows all pages without ellipsis.
 */
function buildPageRange(page: number, pages: number): (number | null)[] {
  if (pages <= 7) {
    return Array.from({ length: pages }, (_, i) => i + 1)
  }

  const range: (number | null)[] = []

  range.push(1)

  if (page > 3) {
    range.push(null) // left ellipsis
  }

  const start = Math.max(2, page - 1)
  const end = Math.min(pages - 1, page + 1)

  for (let i = start; i <= end; i++) {
    range.push(i)
  }

  if (page < pages - 2) {
    range.push(null) // right ellipsis
  }

  range.push(pages)

  return range
}

export function PaginationControls({
  page,
  pages,
  onPageChange,
  disabled = false,
}: PaginationControlsProps) {
  if (pages === 0) return null

  const pageRange = buildPageRange(page, pages)

  return (
    <nav aria-label="Paginación del catálogo">
      <ul className="flex items-center gap-1">
        {/* Previous button */}
        <li>
          <button
            type="button"
            onClick={() => onPageChange(page - 1)}
            disabled={disabled || page === 1}
            aria-disabled={disabled || page === 1}
            aria-label="Página anterior"
            className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-40"
          >
            ‹
          </button>
        </li>

        {/* Page number buttons */}
        {pageRange.map((p, idx) => {
          if (p === null) {
            return (
              <li key={`ellipsis-${idx}`} aria-hidden="true">
                <span className="flex h-9 w-9 items-center justify-center text-sm text-muted-foreground">
                  …
                </span>
              </li>
            )
          }

          const isActive = p === page

          return (
            <li key={p}>
              <button
                type="button"
                onClick={() => onPageChange(p)}
                disabled={disabled}
                aria-disabled={disabled}
                aria-current={isActive ? 'page' : undefined}
                aria-label={`Página ${p}`}
                className={[
                  'flex h-9 w-9 items-center justify-center rounded-md text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground pointer-events-none'
                    : 'border border-border bg-background hover:bg-accent hover:text-accent-foreground',
                  disabled ? 'pointer-events-none opacity-40' : '',
                ]
                  .filter(Boolean)
                  .join(' ')}
              >
                {p}
              </button>
            </li>
          )
        })}

        {/* Next button */}
        <li>
          <button
            type="button"
            onClick={() => onPageChange(page + 1)}
            disabled={disabled || page === pages}
            aria-disabled={disabled || page === pages}
            aria-label="Página siguiente"
            className="flex h-9 w-9 items-center justify-center rounded-md border border-border bg-background text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-40"
          >
            ›
          </button>
        </li>
      </ul>
    </nav>
  )
}
