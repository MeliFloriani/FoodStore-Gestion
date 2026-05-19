/**
 * SearchInput — controlled search input for the catalog filter panel.
 *
 * Bound to rawQ from useCatalogFilters. Debounce happens inside the hook.
 */

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
}

export function SearchInput({ value, onChange }: SearchInputProps) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="catalog-search" className="text-sm font-medium text-foreground">
        Buscar
      </label>
      <input
        id="catalog-search"
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Nombre del producto..."
        aria-label="Buscar productos por nombre"
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      />
    </div>
  )
}
