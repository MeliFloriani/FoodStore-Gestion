/**
 * ProductDetailPage — public product detail page.
 *
 * Route: /catalog/:id (under PublicLayout — no auth required).
 *
 * Responsibilities:
 *   - Reads :id from useParams
 *   - Consumes useCatalogProduct(id)
 *   - Renders ProductDetailView on success
 *   - Renders skeleton on loading
 *   - Renders "Producto no encontrado" + back link on 404
 */

import { Link, useParams } from 'react-router-dom'
import type { AxiosError } from 'axios'
import { useCatalogProduct } from '@/entities/products'
import { ProductDetailView } from '@/features/catalog/product-detail/ProductDetailView'

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6 md:grid md:grid-cols-2" aria-busy="true">
      <span role="status" className="sr-only">
        Cargando producto…
      </span>
      {/* Image skeleton */}
      <div className="aspect-square animate-pulse rounded-xl bg-muted" />
      {/* Details skeleton */}
      <div className="flex flex-col gap-4">
        <div className="h-8 w-3/4 animate-pulse rounded-lg bg-muted" />
        <div className="h-10 w-1/3 animate-pulse rounded-lg bg-muted" />
        <div className="h-4 w-full animate-pulse rounded bg-muted" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-muted" />
        <div className="flex gap-2">
          <div className="h-6 w-20 animate-pulse rounded-full bg-muted" />
          <div className="h-6 w-16 animate-pulse rounded-full bg-muted" />
        </div>
      </div>
    </div>
  )
}

function NotFound() {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <p className="text-xl font-semibold text-foreground">Producto no encontrado</p>
      <p className="text-sm text-muted-foreground">
        El producto que buscás no existe o ya no está disponible.
      </p>
      <Link
        to="/catalog"
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Volver al catálogo
      </Link>
    </div>
  )
}

export default function ProductDetailPage() {
  const { id = '' } = useParams<{ id: string }>()

  const { data: product, isLoading, isError, error } = useCatalogProduct(id)

  // Check for 404 using AxiosError pattern
  const is404 =
    isError &&
    (error as AxiosError)?.response?.status === 404

  return (
    <main className="container mx-auto px-4 py-6">
      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="mb-6">
        <Link
          to="/catalog"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Catálogo
        </Link>
      </nav>

      {isLoading && <DetailSkeleton />}
      {is404 && <NotFound />}
      {isError && !is404 && (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-base text-muted-foreground">
            Ocurrió un error al cargar el producto.
          </p>
          <Link
            to="/catalog"
            className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-accent"
          >
            Volver al catálogo
          </Link>
        </div>
      )}
      {product && <ProductDetailView product={product} />}
    </main>
  )
}
