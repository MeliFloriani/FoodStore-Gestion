/**
 * CategoriaSelect — category filter select for the catalog.
 *
 * Populated from useCategoriesTree (entities/categories).
 * Default option: "Todas las categorías".
 */

import { useCategoriesTree } from '@/entities/categories'
import type { CategoriaTreeNode } from '@/entities/categories'

interface CategoriaSelectProps {
  value: string | null | undefined
  onChange: (value: string | null) => void
}

/** Flatten a tree of categories into a flat list for the select options. */
function flattenTree(nodes: CategoriaTreeNode[], depth = 0): { id: string; nombre: string; depth: number }[] {
  return nodes.flatMap((node) => [
    { id: node.id, nombre: node.nombre, depth },
    ...flattenTree(node.subcategorias, depth + 1),
  ])
}

export function CategoriaSelect({ value, onChange }: CategoriaSelectProps) {
  const { data: tree, isPending } = useCategoriesTree()

  const categories = tree ? flattenTree(tree) : []

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="categoria-select" className="text-sm font-medium text-foreground">
        Categoría
      </label>
      <select
        id="categoria-select"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={isPending}
        aria-label="Filtrar por categoría"
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
      >
        <option value="">Todas las categorías</option>
        {categories.map((cat) => (
          <option key={cat.id} value={cat.id}>
            {'\u00A0'.repeat(cat.depth * 2)}{cat.nombre}
          </option>
        ))}
      </select>
    </div>
  )
}
