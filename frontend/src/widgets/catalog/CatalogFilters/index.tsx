/**
 * CatalogFilters widget — assembles SearchInput, CategoriaSelect, and AllergenosExclusion.
 *
 * Consumes useCatalogFilters from features/catalog/filters/.
 * Renders a "Limpiar filtros" button that calls resetFilters().
 */

import { useCatalogFilters } from '@/features/catalog/filters/useCatalogFilters'
import { SearchInput } from './SearchInput'
import { CategoriaSelect } from './CategoriaSelect'
import { AllergenosExclusion } from './AllergenosExclusion'

export function CatalogFilters() {
  const { rawQ, setRawQ, filters, setFilter, resetFilters } = useCatalogFilters()

  return (
    <aside
      aria-label="Filtros del catálogo"
      className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4"
    >
      <SearchInput
        value={rawQ}
        onChange={(val) => {
          setRawQ(val)
          setFilter('q', val)
        }}
      />

      <CategoriaSelect
        value={filters.categoria_id}
        onChange={(val) => setFilter('categoria_id', val)}
      />

      <AllergenosExclusion
        value={filters.excluir_alergenos}
        onChange={(val) => setFilter('excluir_alergenos', val)}
      />

      <button
        type="button"
        onClick={resetFilters}
        className="mt-2 w-full rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
      >
        Limpiar filtros
      </button>
    </aside>
  )
}
