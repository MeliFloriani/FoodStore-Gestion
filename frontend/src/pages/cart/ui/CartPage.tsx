/**
 * CartPage — client cart view (minimal, smoke-test ready).
 *
 * Reads items from cartStore, renders qty controls, subtotal/total,
 * and a "Continuar al checkout" button.
 *
 * Slice subscription convention (D-06): subscribe to individual slices, not
 * the full store.
 */

import { Link, useNavigate } from 'react-router-dom'
import { useCartStore, buildItemKey } from '@/entities/cart'

function formatCurrency(n: number): string {
  return `$ ${n.toFixed(2)}`
}

export default function CartPage() {
  const navigate = useNavigate()

  // Slice subscriptions only — never useCartStore() without selector (D-06)
  const items = useCartStore((s) => s.items)
  const incrementQuantity = useCartStore((s) => s.incrementQuantity)
  const decrementQuantity = useCartStore((s) => s.decrementQuantity)
  const removeItem = useCartStore((s) => s.removeItem)
  const clearCart = useCartStore((s) => s.clearCart)

  // Selectors re-derive on every render — cheap (sum over items)
  const subtotal = useCartStore((s) => s.subtotal)()
  const costoEnvio = useCartStore((s) => s.costoEnvio)()
  const total = useCartStore((s) => s.total)()
  const totalItems = useCartStore((s) => s.totalItems)()

  const isEmpty = items.length === 0

  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-foreground">Mi Carrito</h1>

      {isEmpty && (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <p className="mb-4 text-muted-foreground">Tu carrito está vacío.</p>
          <Link
            to="/catalog"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            Ir al catálogo
          </Link>
        </div>
      )}

      {!isEmpty && (
        <>
          <ul className="flex flex-col gap-3">
            {items.map((item) => {
              const key = buildItemKey(item)
              const lineTotal = item.precio * item.cantidad
              return (
                <li
                  key={key}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 shadow-sm"
                >
                  <img
                    src={item.imagen_url || '/placeholder.jpg'}
                    alt={item.nombre}
                    className="h-16 w-16 flex-shrink-0 rounded-md bg-muted object-cover"
                  />
                  <div className="flex flex-1 flex-col gap-1">
                    <span className="text-sm font-semibold text-foreground">
                      {item.nombre}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatCurrency(item.precio)} c/u
                    </span>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => decrementQuantity(key)}
                        aria-label={`Disminuir cantidad de ${item.nombre}`}
                        className="h-7 w-7 rounded-md border border-border bg-background text-sm font-semibold hover:bg-accent"
                      >
                        −
                      </button>
                      <span
                        aria-label={`Cantidad de ${item.nombre}`}
                        className="w-8 text-center text-sm font-medium tabular-nums"
                      >
                        {item.cantidad}
                      </span>
                      <button
                        type="button"
                        onClick={() => incrementQuantity(key)}
                        aria-label={`Aumentar cantidad de ${item.nombre}`}
                        className="h-7 w-7 rounded-md border border-border bg-background text-sm font-semibold hover:bg-accent"
                      >
                        +
                      </button>
                    </div>
                    <span className="text-sm font-bold text-foreground">
                      {formatCurrency(lineTotal)}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeItem(key)}
                      className="text-xs text-red-600 hover:underline"
                    >
                      Quitar
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>

          {/* Totals */}
          <div className="mt-6 rounded-lg border border-border bg-card p-4">
            <dl className="flex flex-col gap-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Ítems</dt>
                <dd className="font-medium tabular-nums">{totalItems}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Subtotal</dt>
                <dd className="font-medium tabular-nums">
                  {formatCurrency(subtotal)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Costo de envío</dt>
                <dd className="font-medium tabular-nums">
                  {formatCurrency(costoEnvio)}
                </dd>
              </div>
              <div className="mt-2 flex justify-between border-t border-border pt-2 text-base">
                <dt className="font-semibold">Total</dt>
                <dd className="font-bold tabular-nums">
                  {formatCurrency(total)}
                </dd>
              </div>
            </dl>
          </div>

          {/* Actions */}
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-between">
            <button
              type="button"
              onClick={clearCart}
              className="rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-accent"
            >
              Vaciar carrito
            </button>
            <button
              type="button"
              onClick={() => navigate('/checkout')}
              className="rounded-md bg-orange-500 px-6 py-2 text-sm font-semibold text-white hover:bg-orange-600 active:bg-orange-700"
            >
              Continuar al checkout
            </button>
          </div>
        </>
      )}
    </section>
  )
}
