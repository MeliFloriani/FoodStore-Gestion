/**
 * ProductDetailView — full product detail layout.
 *
 * Two-column on md+: image (left) + details (right).
 * Single column on mobile.
 */

import type { ProductoPublicoDetalleRead } from '@/entities/products'
import { AddToCartButton } from '@/features/cart/add-to-cart'
import { AllergenBadge } from './AllergenBadge'

interface ProductDetailViewProps {
  product: ProductoPublicoDetalleRead
}

export function ProductDetailView({ product }: ProductDetailViewProps) {
  const {
    nombre,
    descripcion,
    imagen_url,
    precio_base,
    tiene_stock,
    categorias,
    ingredientes,
  } = product

  const formattedPrice = `$ ${Number(precio_base).toFixed(2)}`

  return (
    <article className="flex flex-col gap-6 md:grid md:grid-cols-2">
      {/* Image */}
      <div className="overflow-hidden rounded-xl bg-muted">
        <img
          src={imagen_url ?? '/placeholder.jpg'}
          alt={nombre}
          className="h-full w-full object-cover"
        />
      </div>

      {/* Details */}
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold text-foreground">{nombre}</h1>

        <p className="text-3xl font-extrabold text-primary">{formattedPrice}</p>

        {/* Stock indicator */}
        <div>
          {tiene_stock ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-800 dark:bg-green-900/20 dark:text-green-400">
              <span aria-hidden="true" className="h-2 w-2 rounded-full bg-green-500 inline-block" />
              Disponible
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-800 dark:bg-red-900/20 dark:text-red-400">
              Agotado
            </span>
          )}
        </div>

        {/* Add to cart */}
        <AddToCartButton product={product} />

        {/* Description */}
        {descripcion && (
          <p className="text-sm leading-relaxed text-muted-foreground">{descripcion}</p>
        )}

        {/* Categories */}
        {categorias.length > 0 && (
          <div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Categorías
            </h2>
            <div className="flex flex-wrap gap-2">
              {categorias.map((cat) => (
                <span
                  key={cat.id}
                  className="rounded-full border border-border bg-background px-3 py-1 text-xs font-medium text-foreground"
                >
                  {cat.nombre}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Ingredients */}
        {ingredientes.length > 0 && (
          <div>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Ingredientes
            </h2>
            <ul className="flex flex-wrap gap-2">
              {ingredientes.map((ing) => (
                <li key={ing.ingrediente_id}>
                  {ing.es_alergeno ? (
                    <AllergenBadge nombre={ing.nombre} />
                  ) : (
                    <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                      {ing.nombre}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </article>
  )
}
