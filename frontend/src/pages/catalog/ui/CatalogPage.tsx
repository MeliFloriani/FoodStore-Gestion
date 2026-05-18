import { useCategoriesTree } from '@/entities/categories'
import type { CategoriaTreeNode } from '@/entities/categories'

/**
 * Recursive category node renderer.
 * Displays a single category with nested subcategorias indented via ml-4.
 */
function CategoryNode({ node }: { node: CategoriaTreeNode }) {
  return (
    <li>
      <span>{node.nombre}</span>
      {node.subcategorias.length > 0 && (
        <ul className="ml-4">
          {node.subcategorias.map((child) => (
            <CategoryNode key={child.id} node={child} />
          ))}
        </ul>
      )}
    </li>
  )
}

/**
 * CatalogPage — minimal category tree render (Change 09).
 *
 * Displays the full category tree fetched from GET /api/v1/categorias.
 * Shows loading/error states via useCategoriesTree hook.
 * Full catalog UI (search, products, breadcrumbs) is deferred to Changes 10-12.
 */
export default function CatalogPage() {
  const { data: categories, isPending, isError } = useCategoriesTree()

  if (isPending) return <div>Cargando categorías...</div>
  if (isError) return <div>Error al cargar categorías.</div>

  return (
    <ul>
      {categories?.map((root) => (
        <CategoryNode key={root.id} node={root} />
      ))}
    </ul>
  )
}
