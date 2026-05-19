/**
 * Integration tests for CatalogPage and ProductDetailPage.
 *
 * Uses axios-mock-adapter to intercept HTTP requests.
 * Wraps components in QueryClient + MemoryRouter for isolated testing.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import MockAdapter from 'axios-mock-adapter'
import { http } from '@/shared/api/http'
import CatalogPage from '../ui/CatalogPage'
import ProductDetailPage from '../ui/ProductDetailPage'
import type { PaginatedCatalogProductos, ProductoPublicoDetalleRead } from '@/entities/products'

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  })
}

function renderWithProviders(
  ui: React.ReactElement,
  {
    initialPath = '/catalog',
    queryClient = makeQueryClient(),
  }: { initialPath?: string; queryClient?: QueryClient } = {},
) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// ── Mock data ─────────────────────────────────────────────────────────────────

const mockProducts: PaginatedCatalogProductos = {
  items: [
    {
      id: 'uuid-1',
      nombre: 'Pizza Margherita',
      descripcion: 'Deliciosa pizza',
      imagen_url: null,
      precio_base: '12.50',
      disponible: true,
      tiene_stock: true,
    },
    {
      id: 'uuid-2',
      nombre: 'Hamburguesa Clásica',
      descripcion: null,
      imagen_url: null,
      precio_base: '9.00',
      disponible: true,
      tiene_stock: false,
    },
  ],
  total: 2,
  page: 1,
  size: 20,
  pages: 1,
}

const mockProductsMultiPage: PaginatedCatalogProductos = {
  ...mockProducts,
  total: 40,
  pages: 2,
}

const mockProductDetail: ProductoPublicoDetalleRead = {
  id: 'uuid-1',
  nombre: 'Pizza Margherita',
  descripcion: 'Deliciosa pizza con tomate y mozzarella',
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

// ── CatalogPage tests ─────────────────────────────────────────────────────────

describe('CatalogPage', () => {
  let mock: MockAdapter

  beforeEach(() => {
    mock = new MockAdapter(http)
    // Mock categories (used by CatalogFilters widget)
    mock.onGet('/api/v1/categorias').reply(200, [])
    // Mock allergens (used by AllergenosExclusion)
    mock.onGet('/api/v1/catalog/ingredientes-alergenos').reply(200, {
      items: [],
      total: 0,
    })
  })

  afterEach(() => {
    mock.reset()
    vi.clearAllMocks()
  })

  it('renders product cards on successful response', async () => {
    mock.onGet('/api/v1/catalog/productos').reply(200, mockProducts)

    renderWithProviders(<CatalogPage />)

    await waitFor(() => {
      expect(screen.getByText('Pizza Margherita')).toBeInTheDocument()
      expect(screen.getByText('Hamburguesa Clásica')).toBeInTheDocument()
    })
  })

  it('renders skeleton cards while loading', () => {
    // Delayed response — product cards should not be visible yet
    mock.onGet('/api/v1/catalog/productos').reply(200, mockProducts)

    const { container } = renderWithProviders(<CatalogPage />)

    // Skeleton cards should be visible during initial load
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('renders EmptyState when items is empty', async () => {
    mock.onGet('/api/v1/catalog/productos').reply(200, {
      items: [],
      total: 0,
      page: 1,
      size: 20,
      pages: 0,
    })

    renderWithProviders(<CatalogPage />)

    await waitFor(() => {
      expect(
        screen.getByText('No encontramos productos con los filtros seleccionados.'),
      ).toBeInTheDocument()
    })
  })

  it('renders ErrorState on network failure', async () => {
    mock.onGet('/api/v1/catalog/productos').reply(500)

    renderWithProviders(<CatalogPage />)

    await waitFor(() => {
      expect(screen.getByText(/error al cargar/i)).toBeInTheDocument()
    })
  })

  it('renders PaginationControls when pages > 1', async () => {
    mock.onGet('/api/v1/catalog/productos').reply(200, mockProductsMultiPage)

    renderWithProviders(<CatalogPage />)

    await waitFor(() => {
      expect(
        screen.getByRole('navigation', { name: 'Paginación del catálogo' }),
      ).toBeInTheDocument()
    })
  })

  it('does not render PaginationControls when pages <= 1', async () => {
    mock.onGet('/api/v1/catalog/productos').reply(200, mockProducts)

    renderWithProviders(<CatalogPage />)

    await waitFor(() => {
      expect(screen.getByText('Pizza Margherita')).toBeInTheDocument()
    })

    expect(
      screen.queryByRole('navigation', { name: 'Paginación del catálogo' }),
    ).not.toBeInTheDocument()
  })

  it('renders main landmark wrapping content', async () => {
    mock.onGet('/api/v1/catalog/productos').reply(200, mockProducts)

    renderWithProviders(<CatalogPage />)

    expect(screen.getByRole('main')).toBeInTheDocument()
  })
})

// ── ProductDetailPage tests ───────────────────────────────────────────────────

describe('ProductDetailPage', () => {
  let mock: MockAdapter

  beforeEach(() => {
    mock = new MockAdapter(http)
  })

  afterEach(() => {
    mock.reset()
    vi.clearAllMocks()
  })

  function renderDetailPage(id = 'uuid-1') {
    return render(
      <QueryClientProvider client={makeQueryClient()}>
        <MemoryRouter initialEntries={[`/catalog/${id}`]}>
          <Routes>
            <Route path="/catalog/:id" element={<ProductDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
  }

  it('renders product details on success', async () => {
    mock.onGet('/api/v1/catalog/productos/uuid-1').reply(200, mockProductDetail)

    renderDetailPage()

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Pizza Margherita')
    })

    expect(screen.getByText('$ 12.50')).toBeInTheDocument()
    expect(screen.getByText('Pizzas')).toBeInTheDocument()
  })

  it('renders skeleton while loading', () => {
    mock.onGet('/api/v1/catalog/productos/uuid-1').reply(200, mockProductDetail)

    const { container } = renderDetailPage()

    // Skeleton should be present during initial load
    const skeletons = container.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('renders "Producto no encontrado" on 404 error', async () => {
    mock.onGet('/api/v1/catalog/productos/nonexistent').reply(404, {
      code: 'PRODUCT_NOT_FOUND',
    })

    renderDetailPage('nonexistent')

    await waitFor(() => {
      expect(screen.getByText('Producto no encontrado')).toBeInTheDocument()
    })
  })

  it('renders back link to /catalog on 404', async () => {
    mock.onGet('/api/v1/catalog/productos/nonexistent').reply(404, {
      code: 'PRODUCT_NOT_FOUND',
    })

    renderDetailPage('nonexistent')

    await waitFor(() => {
      const backLink = screen.getByRole('link', { name: 'Volver al catálogo' })
      expect(backLink).toHaveAttribute('href', '/catalog')
    })
  })

  it('renders allergen badges for allergen ingredients', async () => {
    mock.onGet('/api/v1/catalog/productos/uuid-1').reply(200, mockProductDetail)

    renderDetailPage()

    await waitFor(() => {
      expect(screen.getByTitle('Alérgeno: Gluten')).toBeInTheDocument()
    })
  })

  it('renders main landmark', async () => {
    mock.onGet('/api/v1/catalog/productos/uuid-1').reply(200, mockProductDetail)

    renderDetailPage()

    expect(screen.getByRole('main')).toBeInTheDocument()
  })
})
