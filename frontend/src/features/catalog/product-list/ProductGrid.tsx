/**
 * ProductGrid — responsive product grid for the public catalog.
 *
 * Renders skeleton cards while loading, or ProductCard for each product.
 * Grid columns: 1 (mobile) → 2 (sm) → 3 (md) → 4 (lg).
 */

import type { ProductoPublicoRead } from '@/entities/products'
import { SkeletonList } from '@/shared/ui/skeleton'
import { ProductCard } from './ProductCard'

interface ProductGridProps {
  products?: ProductoPublicoRead[]
  isLoading?: boolean
}

export function ProductGrid({ products = [], isLoading = false }: ProductGridProps) {
  if (isLoading) {
    return (
      <div aria-busy={true} aria-label="Cargando productos">
        <span role="status" className="sr-only">
          Cargando productos…
        </span>
        <SkeletonList rows={8} />
      </div>
    )
  }

  return (
    <div
      aria-busy={false}
      className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
    >
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  )
}
