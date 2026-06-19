import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { AddToCartButton } from '../AddToCartButton'
import { useCartStore } from '@/entities/cart'
import type { ProductoPublicoRead } from '@/entities/products'

vi.mock('@/shared/ui/toast', () => ({
  useToast: vi.fn(() => ({ toast: vi.fn() })),
}))

const mockProduct: ProductoPublicoRead = {
  id: 'prod-1',
  nombre: 'Pizza',
  precio_base: '1200.00',
  tiene_stock: true,
  imagen_url: 'https://example.com/pizza.jpg',
  descripcion_corta: 'Rica pizza',
  descripcion_larga: null,
  categoria_id: 'cat-1',
  categoria_nombre: 'Pizzas',
  ingredientes: [],
}

describe('AddToCartButton', () => {
  beforeEach(() => {
    useCartStore.setState({ items: [] })
  })

  it('renders "Agregar al carrito" when product has stock', () => {
    render(<AddToCartButton product={mockProduct} />)
    const btn = screen.getByRole('button', { name: /Agregar Pizza al carrito/ })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveTextContent('Agregar al carrito')
    expect(btn).not.toBeDisabled()
  })

  it('renders "Sin stock" and disabled when product has no stock', () => {
    render(<AddToCartButton product={{ ...mockProduct, tiene_stock: false }} />)
    const btn = screen.getByRole('button', { name: /Agregar Pizza al carrito/ })
    expect(btn).toBeDisabled()
    expect(btn).toHaveTextContent('Sin stock')
  })

  it('adds item to cart and shows confirmation on click', () => {
    const addItemSpy = vi.spyOn(useCartStore.getState(), 'addItem')
    render(<AddToCartButton product={mockProduct} />)

    const btn = screen.getByRole('button', { name: /Agregar Pizza al carrito/ })

    fireEvent.click(btn)

    expect(addItemSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        producto_id: 'prod-1',
        nombre: 'Pizza',
        cantidad: 1,
      }),
      [],
    )

    expect(btn).toHaveTextContent('Agregado ✓')
  })

  it('stops propagation by calling preventDefault and stopPropagation', () => {
    render(<AddToCartButton product={mockProduct} />)

    const btn = screen.getByRole('button', { name: /Agregar Pizza al carrito/ })

    // The button is inside a form-like context; clicking should not submit
    const handleClick = vi.fn()
    document.body.addEventListener('click', handleClick)

    fireEvent.click(btn)

    // The click should not bubble up because stopPropagation is called
    expect(handleClick).not.toHaveBeenCalled()
    document.body.removeEventListener('click', handleClick)
  })

  it('applies custom className', () => {
    render(<AddToCartButton product={mockProduct} className="my-custom-class" />)
    const btn = screen.getByRole('button', { name: /Agregar Pizza al carrito/ })
    expect(btn.className).toContain('my-custom-class')
  })
})
