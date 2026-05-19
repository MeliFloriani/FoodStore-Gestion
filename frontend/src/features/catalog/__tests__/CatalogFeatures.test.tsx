/**
 * Unit tests for catalog feature components.
 *
 * Tests:
 *   - ProductCard renders alt text, nombre, price, Agotado badge
 *   - ProductGrid shows skeleton cards when isLoading=true
 *   - ProductGrid renders product cards when not loading
 *   - EmptyState renders message and reset button
 *   - ErrorState renders message and retry button
 *   - AllergenBadge renders ingredient name
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ProductCard } from '../product-list/ProductCard'
import { ProductGrid } from '../product-list/ProductGrid'
import { EmptyState } from '../product-list/EmptyState'
import { ErrorState } from '../product-list/ErrorState'
import { AllergenBadge } from '../product-detail/AllergenBadge'
import { ProductDetailView } from '../product-detail/ProductDetailView'
import type { ProductoPublicoRead, ProductoPublicoDetalleRead } from '@/entities/products'

const mockProduct: ProductoPublicoRead = {
  id: 'uuid-1',
  nombre: 'Pizza Margherita',
  descripcion: 'Una deliciosa pizza',
  imagen_url: 'https://example.com/pizza.jpg',
  precio_base: '12.50',
  disponible: true,
  tiene_stock: true,
}

const mockProductNoStock: ProductoPublicoRead = {
  ...mockProduct,
  id: 'uuid-2',
  nombre: 'Burger Especial',
  tiene_stock: false,
}

describe('ProductCard', () => {
  it('renders alt text equal to product nombre', () => {
    render(
      <MemoryRouter>
        <ProductCard product={mockProduct} />
      </MemoryRouter>,
    )
    const img = screen.getByAltText('Pizza Margherita')
    expect(img).toBeInTheDocument()
  })

  it('renders product nombre as h3', () => {
    render(
      <MemoryRouter>
        <ProductCard product={mockProduct} />
      </MemoryRouter>,
    )
    const heading = screen.getByRole('heading', { level: 3 })
    expect(heading).toHaveTextContent('Pizza Margherita')
  })

  it('renders formatted price', () => {
    render(
      <MemoryRouter>
        <ProductCard product={mockProduct} />
      </MemoryRouter>,
    )
    expect(screen.getByText('$ 12.50')).toBeInTheDocument()
  })

  it('renders Agotado badge when tiene_stock is false', () => {
    render(
      <MemoryRouter>
        <ProductCard product={mockProductNoStock} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Agotado')).toBeInTheDocument()
  })

  it('does not render Agotado badge when tiene_stock is true', () => {
    render(
      <MemoryRouter>
        <ProductCard product={mockProduct} />
      </MemoryRouter>,
    )
    expect(screen.queryByText('Agotado')).not.toBeInTheDocument()
  })

  it('renders a link to /catalog/{id}', () => {
    render(
      <MemoryRouter>
        <ProductCard product={mockProduct} />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: /Pizza Margherita/i })
    expect(link).toHaveAttribute('href', '/catalog/uuid-1')
  })

  it('renders placeholder image when imagen_url is null', () => {
    render(
      <MemoryRouter>
        <ProductCard product={{ ...mockProduct, imagen_url: null }} />
      </MemoryRouter>,
    )
    const img = screen.getByAltText('Pizza Margherita')
    expect(img).toHaveAttribute('src', '/placeholder.jpg')
  })
})

describe('ProductGrid', () => {
  it('renders 8 skeleton cards when isLoading is true', () => {
    const { container } = render(
      <MemoryRouter>
        <ProductGrid isLoading />
      </MemoryRouter>,
    )
    // Skeletons have animate-pulse class
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons).toHaveLength(8)
  })

  it('shows aria-busy="true" when loading', () => {
    const { container } = render(
      <MemoryRouter>
        <ProductGrid isLoading />
      </MemoryRouter>,
    )
    const grid = container.firstChild as HTMLElement
    expect(grid).toHaveAttribute('aria-busy', 'true')
  })

  it('renders product cards when not loading', () => {
    const products: ProductoPublicoRead[] = [mockProduct, mockProductNoStock]
    render(
      <MemoryRouter>
        <ProductGrid products={products} isLoading={false} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Pizza Margherita')).toBeInTheDocument()
    expect(screen.getByText('Burger Especial')).toBeInTheDocument()
  })

  it('renders empty grid when products is empty and not loading', () => {
    const { container } = render(
      <MemoryRouter>
        <ProductGrid products={[]} isLoading={false} />
      </MemoryRouter>,
    )
    const grid = container.firstChild as HTMLElement
    expect(grid.children).toHaveLength(0)
  })
})

describe('EmptyState', () => {
  it('renders the no-results message', () => {
    render(<EmptyState onReset={() => {}} />)
    expect(
      screen.getByText('No encontramos productos con los filtros seleccionados.'),
    ).toBeInTheDocument()
  })

  it('calls onReset when Limpiar filtros button clicked', () => {
    const onReset = vi.fn()
    render(<EmptyState onReset={onReset} />)
    screen.getByRole('button', { name: 'Limpiar filtros' }).click()
    expect(onReset).toHaveBeenCalledOnce()
  })
})

describe('ErrorState', () => {
  it('renders error message', () => {
    render(<ErrorState onRetry={() => {}} />)
    expect(screen.getByText(/error al cargar/i)).toBeInTheDocument()
  })

  it('calls onRetry when Reintentar button clicked', () => {
    const onRetry = vi.fn()
    render(<ErrorState onRetry={onRetry} />)
    screen.getByRole('button', { name: 'Reintentar' }).click()
    expect(onRetry).toHaveBeenCalledOnce()
  })
})

describe('AllergenBadge', () => {
  it('renders allergen name', () => {
    render(<AllergenBadge nombre="Gluten" />)
    expect(screen.getByText('Gluten')).toBeInTheDocument()
  })
})

describe('ProductDetailView', () => {
  const mockDetail: ProductoPublicoDetalleRead = {
    id: 'uuid-1',
    nombre: 'Pizza Margherita',
    descripcion: 'Una deliciosa pizza con tomate y mozzarella',
    imagen_url: 'https://example.com/pizza.jpg',
    precio_base: '12.50',
    disponible: true,
    tiene_stock: true,
    categorias: [{ id: 'cat-1', nombre: 'Pizzas' }],
    ingredientes: [
      { ingrediente_id: 'ing-1', nombre: 'Gluten', es_alergeno: true },
      { ingrediente_id: 'ing-2', nombre: 'Tomate', es_alergeno: false },
    ],
  }

  it('renders product nombre', () => {
    render(<ProductDetailView product={mockDetail} />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Pizza Margherita')
  })

  it('renders formatted price', () => {
    render(<ProductDetailView product={mockDetail} />)
    expect(screen.getByText('$ 12.50')).toBeInTheDocument()
  })

  it('renders product image with correct alt', () => {
    render(<ProductDetailView product={mockDetail} />)
    expect(screen.getByAltText('Pizza Margherita')).toBeInTheDocument()
  })

  it('renders categorias', () => {
    render(<ProductDetailView product={mockDetail} />)
    expect(screen.getByText('Pizzas')).toBeInTheDocument()
  })

  it('renders AllergenBadge for allergen ingredients', () => {
    render(<ProductDetailView product={mockDetail} />)
    // Gluten should be an allergen badge
    expect(screen.getByTitle('Alérgeno: Gluten')).toBeInTheDocument()
  })

  it('renders non-allergen ingredient without badge', () => {
    render(<ProductDetailView product={mockDetail} />)
    expect(screen.getByText('Tomate')).toBeInTheDocument()
    expect(screen.queryByTitle('Alérgeno: Tomate')).not.toBeInTheDocument()
  })

  it('shows Disponible when tiene_stock is true', () => {
    render(<ProductDetailView product={mockDetail} />)
    expect(screen.getByText('Disponible')).toBeInTheDocument()
  })

  it('shows Agotado when tiene_stock is false', () => {
    render(<ProductDetailView product={{ ...mockDetail, tiene_stock: false }} />)
    expect(screen.getByText('Agotado')).toBeInTheDocument()
  })
})
