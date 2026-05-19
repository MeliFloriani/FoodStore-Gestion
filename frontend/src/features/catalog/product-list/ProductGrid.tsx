/**
 * ProductGrid — responsive product grid for the public catalog.
 *
 * Renders skeleton cards while loading, or ProductCard for each product.
 * Grid columns: 1 (mobile) → 2 (sm) → 3 (md) → 4 (lg).
 */

import type { ProductoPublicoRead } from '@/entities/products'
import { ProductCard } from './ProductCard'

interface ProductGridProps {
  products?: ProductoPublicoRead[]
  isLoading?: boolean
}

function SkeletonCard() {
  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm animate-pulse">
      <div className="aspect-square bg-muted" />
      <div className="flex flex-col gap-2 p-3">
        <div className="h-4 w-3/4 rounded bg-muted" />
        <div className="h-4 w-1/2 rounded bg-muted" />
        <div className="mt-auto h-5 w-1/3 rounded bg-muted" />
      </div>
    </div>
  )
}

export function ProductGrid({ products = [], isLoading = false }: ProductGridProps) {
  return (
    <div
      aria-busy={isLoading}
      className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
    >
      {isLoading ? (
        <>
          <span role="status" className="sr-only">
            Cargando productos…
          </span>
          {Array.from({ length: 8 }).map((_, idx) => (
            <SkeletonCard key={idx} />
          ))}
        </>
      ) : (
        products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))
      )}
    </div>
  )
}
