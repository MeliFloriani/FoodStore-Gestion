/**
 * ProductCard — displays a single public product in the catalog grid.
 *
 * Card is a link to /catalog/{id}. Shows image, name, price, and
 * an "Agotado" badge if the product has no stock.
 */

import { Link } from 'react-router-dom'
import type { ProductoPublicoRead } from '@/entities/products'
import { AddToCartButton } from '@/features/cart/add-to-cart'

interface ProductCardProps {
  product: ProductoPublicoRead
}

export function ProductCard({ product }: ProductCardProps) {
  const { id, nombre, imagen_url, precio_base, tiene_stock } = product

  const formattedPrice = `$ ${Number(precio_base).toFixed(2)}`

  return (
    <Link
      to={`/catalog/${id}`}
      className="group flex flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm transition-shadow hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      aria-label={`Ver detalles de ${nombre}`}
    >
      {/* Product image */}
      <div className="relative aspect-square overflow-hidden bg-muted">
        <img
          src={imagen_url ?? '/placeholder.jpg'}
          alt={nombre}
          className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
        />
        {/* Agotado badge */}
        {!tiene_stock && (
          <span className="absolute left-2 top-2 rounded-full bg-destructive px-2 py-0.5 text-xs font-semibold text-destructive-foreground">
            Agotado
          </span>
        )}
      </div>

      {/* Product info */}
      <div className="flex flex-1 flex-col gap-2 p-3">
        <h3 className="line-clamp-2 text-sm font-semibold text-card-foreground">
          {nombre}
        </h3>
        <p className="mt-auto text-base font-bold text-primary">{formattedPrice}</p>
        <AddToCartButton product={product} className="w-full" />
      </div>
    </Link>
  )
}
