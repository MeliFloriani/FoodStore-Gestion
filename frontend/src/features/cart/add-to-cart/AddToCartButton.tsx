/**
 * AddToCartButton — adds a public catalog product to the client cart.
 *
 * Minimal, smoke-test-grade feature. Adds 1 unit of the product with no
 * personalization (personalizacion: []) so it does not need to fetch the
 * non-public ProductoIngredienteRead list (which carries es_removible).
 *
 * - Disabled when product.tiene_stock === false.
 * - Shows a brief "Agregado" confirmation after a successful add.
 * - Uses slice subscription (only addItem) — does not subscribe to items.
 */

import { useState } from 'react'
import { useCartStore } from '@/entities/cart'
import type { ProductoPublicoRead } from '@/entities/products'

interface AddToCartButtonProps {
  product: ProductoPublicoRead
  /** Optional Tailwind override / extra classes for the button wrapper. */
  className?: string
}

export function AddToCartButton({ product, className }: AddToCartButtonProps) {
  const addItem = useCartStore((s) => s.addItem)
  const [confirmed, setConfirmed] = useState(false)

  const disabled = !product.tiene_stock

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    // Stop propagation so clicking the button inside a <Link> card
    // (ProductCard) does not navigate to the detail page.
    e.preventDefault()
    e.stopPropagation()
    if (disabled) return

    addItem(
      {
        producto_id: product.id,
        nombre: product.nombre,
        precio: Number(product.precio_base),
        cantidad: 1,
        imagen_url: product.imagen_url ?? '',
        personalizacion: [],
      },
      [], // no personalization → no ingredient validation needed
    )

    setConfirmed(true)
    setTimeout(() => setConfirmed(false), 1500)
  }

  const baseClass =
    'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-semibold text-white transition-colors'
  const stateClass = disabled
    ? 'bg-gray-400 cursor-not-allowed'
    : confirmed
      ? 'bg-green-600'
      : 'bg-orange-500 hover:bg-orange-600 active:bg-orange-700'

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={disabled}
      aria-label={`Agregar ${product.nombre} al carrito`}
      className={[baseClass, stateClass, className ?? ''].join(' ').trim()}
    >
      {disabled ? 'Sin stock' : confirmed ? 'Agregado ✓' : 'Agregar al carrito'}
    </button>
  )
}
