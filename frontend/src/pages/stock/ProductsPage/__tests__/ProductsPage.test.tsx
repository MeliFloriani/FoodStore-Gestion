/**
 * ProductsPage — modal UX tests.
 *
 * Covers:
 *   - Renders product table
 *   - "Nuevo producto" opens create modal
 *   - "Editar" opens edit modal with pre-populated data
 *   - Successful create shows success toast and closes modal
 *   - API error shows error toast and keeps modal open
 *   - "Eliminar" opens delete confirm modal
 *   - Delete confirm calls mutation and shows success toast
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import StockProductsPage from '../index'

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockCreateMutate = vi.fn()
const mockUpdateMutate = vi.fn()
const mockDeleteMutate = vi.fn()

vi.mock('@/entities/products', () => ({
  useProductos: () => ({
    data: {
      items: [
        {
          id: 'prod-1',
          nombre: 'Pizza Margherita',
          descripcion: 'Clásica',
          imagen_url: 'https://example.com/pizza.jpg',
          precio_base: '3500.00',
          stock_cantidad: 10,
          disponible: true,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'prod-2',
          nombre: 'Hamburguesa Clásica',
          descripcion: null,
          imagen_url: null,
          precio_base: '2800.00',
          stock_cantidad: 5,
          disponible: true,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 2,
      page: 1,
      pages: 1,
      size: 20,
    },
    isLoading: false,
  }),
  useCreateProducto: () => ({ mutateAsync: mockCreateMutate, isPending: false }),
  useUpdateProducto: () => ({ mutateAsync: mockUpdateMutate, isPending: false }),
  useDeleteProducto: () => ({ mutateAsync: mockDeleteMutate, isPending: false }),
}))

vi.mock('@/entities/categories', () => ({
  useCategoriesTree: () => ({ data: [], isLoading: false }),
}))

// ── Setup ─────────────────────────────────────────────────────────────────────

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <StockProductsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('StockProductsPage', () => {
  it('renders the product table', () => {
    renderPage()
    expect(screen.getByText('Pizza Margherita')).toBeInTheDocument()
    expect(screen.getByText('Hamburguesa Clásica')).toBeInTheDocument()
  })

  it('opens create modal when "Nuevo producto" is clicked', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo producto/i }))
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: /nuevo producto/i })).toBeInTheDocument()
  })

  it('opens edit modal with pre-populated name when "Editar" is clicked', async () => {
    renderPage()
    const editButtons = screen.getAllByRole('button', { name: /editar/i })
    fireEvent.click(editButtons[0]!)
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    const input = screen.getByLabelText(/nombre/i) as HTMLInputElement
    expect(input.value).toBe('Pizza Margherita')
  })

  it('calls createMutate and closes modal on success', async () => {
    mockCreateMutate.mockResolvedValueOnce({})
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo producto/i }))
    await waitFor(() => screen.getByRole('dialog'))
    fireEvent.change(screen.getByLabelText(/nombre/i), { target: { value: 'Calzone' } })
    fireEvent.change(screen.getByLabelText(/precio base/i), { target: { value: '4000.00' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(mockCreateMutate).toHaveBeenCalledWith(
        expect.objectContaining({ nombre: 'Calzone', precio_base: '4000.00' }),
      ),
    )
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/producto creado/i)).toBeInTheDocument()
  })

  it('shows error toast and keeps modal open when API call fails', async () => {
    mockCreateMutate.mockRejectedValueOnce(new Error('Error de API'))
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo producto/i }))
    await waitFor(() => screen.getByRole('dialog'))
    fireEvent.change(screen.getByLabelText(/nombre/i), { target: { value: 'Test' } })
    fireEvent.change(screen.getByLabelText(/precio base/i), { target: { value: '100.00' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(screen.getByText(/Error de API/)).toBeInTheDocument(),
    )
  })

  it('opens delete confirmation modal when "Eliminar" is clicked', async () => {
    renderPage()
    const deleteButtons = screen.getAllByRole('button', { name: /eliminar/i })
    fireEvent.click(deleteButtons[0]!)
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/eliminar producto/i)).toBeInTheDocument()
    expect(within(dialog).getByText(/Pizza Margherita/)).toBeInTheDocument()
  })

  it('calls deleteMutate and shows success toast on delete confirm', async () => {
    mockDeleteMutate.mockResolvedValueOnce({})
    renderPage()
    const deleteButtons = screen.getAllByRole('button', { name: /eliminar/i })
    fireEvent.click(deleteButtons[0]!)
    await waitFor(() => screen.getByRole('dialog'))
    const dialog = screen.getByRole('dialog')
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: /eliminar/i }))
    })
    await waitFor(() => expect(mockDeleteMutate).toHaveBeenCalledWith('prod-1'))
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/eliminado correctamente/i)).toBeInTheDocument()
  })

  it('shows "URL de imagen" field in create modal', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo producto/i }))
    await waitFor(() => screen.getByRole('dialog'))
    expect(screen.getByLabelText(/url de imagen/i)).toBeInTheDocument()
  })

  it('pre-populates imagen_url when editing', async () => {
    renderPage()
    const editButtons = screen.getAllByRole('button', { name: /editar/i })
    fireEvent.click(editButtons[0]!)
    await waitFor(() => screen.getByRole('dialog'))
    const input = screen.getByLabelText(/url de imagen/i) as HTMLInputElement
    expect(input.value).toBe('https://example.com/pizza.jpg')
  })

  it('includes imagen_url in create payload', async () => {
    mockCreateMutate.mockResolvedValueOnce({})
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo producto/i }))
    await waitFor(() => screen.getByRole('dialog'))
    fireEvent.change(screen.getByLabelText(/nombre/i), { target: { value: 'Calzone' } })
    fireEvent.change(screen.getByLabelText(/precio base/i), { target: { value: '4000.00' } })
    fireEvent.change(screen.getByLabelText(/url de imagen/i), {
      target: { value: 'https://example.com/calzone.jpg' },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(mockCreateMutate).toHaveBeenCalledWith(
        expect.objectContaining({ imagen_url: 'https://example.com/calzone.jpg' }),
      ),
    )
  })

  it('sends null imagen_url when field is empty on create', async () => {
    mockCreateMutate.mockResolvedValueOnce({})
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo producto/i }))
    await waitFor(() => screen.getByRole('dialog'))
    fireEvent.change(screen.getByLabelText(/nombre/i), { target: { value: 'Pan' } })
    fireEvent.change(screen.getByLabelText(/precio base/i), { target: { value: '500.00' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(mockCreateMutate).toHaveBeenCalledWith(
        expect.objectContaining({ imagen_url: null }),
      ),
    )
  })
})
