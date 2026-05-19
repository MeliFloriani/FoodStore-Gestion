/**
 * CatalogPage — public product catalog.
 *
 * Replaces the Change 08 placeholder.
 * Route: /catalog (under PublicLayout — no auth required).
 *
 * Responsibilities:
 *   - Consumes useCatalogFilters() for URL-synced filter state
 *   - Consumes useCatalogProducts(filters) for paginated product data
 *   - Renders CatalogFilters widget, ProductGrid, PaginationControls, EmptyState, ErrorState
 */

import { useCatalogProducts } from '@/entities/products'
import { useCatalogFilters } from '@/features/catalog/filters/useCatalogFilters'
import { ProductGrid } from '@/features/catalog/product-list/ProductGrid'
import { EmptyState } from '@/features/catalog/product-list/EmptyState'
import { ErrorState } from '@/features/catalog/product-list/ErrorState'
import { CatalogFilters } from '@/widgets/catalog/CatalogFilters'
import { PaginationControls } from '@/shared/ui/PaginationControls'

export default function CatalogPage() {
  const { filters, setFilter, resetFilters } = useCatalogFilters()

  const { data, isLoading, isError, refetch } = useCatalogProducts(filters)

  const products = data?.items ?? []
  const pages = data?.pages ?? 0
  const page = data?.page ?? 1
  const isEmpty = !isLoading && !isError && products.length === 0

  return (
    <main className="container mx-auto px-4 py-6">
      <h1 className="mb-6 text-2xl font-bold text-foreground">Catálogo</h1>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        {/* Filters sidebar */}
        <div className="w-full lg:w-64 lg:shrink-0">
          <CatalogFilters />
        </div>

        {/* Main content area */}
        <div className="flex flex-1 flex-col gap-6">
          {/* Error state */}
          {isError && <ErrorState onRetry={() => refetch()} />}

          {/* Empty state */}
          {isEmpty && <EmptyState onReset={resetFilters} />}

          {/* Product grid */}
          {!isError && (
            <ProductGrid products={products} isLoading={isLoading} />
          )}

          {/* Pagination */}
          {!isLoading && !isError && pages > 1 && (
            <div className="flex justify-center">
              <PaginationControls
                page={page}
                pages={pages}
                onPageChange={(p) => setFilter('page', p)}
                disabled={isLoading}
              />
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
