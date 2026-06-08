/**
 * CategoriesPage — modal UX tests.
 *
 * Covers:
 *   - Renders flattened category list
 *   - "Nueva categoría" opens create modal
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
import StockCategoriesPage from '../index'

// ── Mocks ─────────────────────────────────────────────────────────────────────

const mockCreateMutate = vi.fn()
const mockUpdateMutate = vi.fn()
const mockDeleteMutate = vi.fn()

vi.mock('@/entities/categories', () => ({
  useCategoriesTree: () => ({
    data: [
      { id: 'cat-1', nombre: 'Bebidas', descripcion: 'Todo tipo de bebidas', subcategorias: [] },
      {
        id: 'cat-2',
        nombre: 'Comidas',
        descripcion: null,
        subcategorias: [
          { id: 'cat-3', nombre: 'Pizzas', descripcion: null, subcategorias: [] },
        ],
      },
    ],
    isLoading: false,
  }),
  useCreateCategoria: () => ({ mutateAsync: mockCreateMutate, isPending: false }),
  useUpdateCategoria: () => ({ mutateAsync: mockUpdateMutate, isPending: false }),
  useDeleteCategoria: () => ({ mutateAsync: mockDeleteMutate, isPending: false }),
}))

// ── Setup ─────────────────────────────────────────────────────────────────────

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <StockCategoriesPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('StockCategoriesPage', () => {
  it('renders the flattened category list', () => {
    renderPage()
    expect(screen.getByText('Bebidas')).toBeInTheDocument()
    expect(screen.getByText('Comidas')).toBeInTheDocument()
    expect(screen.getByText('Pizzas')).toBeInTheDocument()
  })

  it('opens create modal when "Nueva categoría" is clicked', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nueva categoría/i }))
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: /nueva categoría/i })).toBeInTheDocument()
  })

  it('opens edit modal with pre-populated name when "Editar" is clicked', async () => {
    renderPage()
    const editButtons = screen.getAllByRole('button', { name: /editar/i })
    fireEvent.click(editButtons[0]!)
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    const input = screen.getByLabelText(/nombre/i) as HTMLInputElement
    expect(input.value).toBe('Bebidas')
  })

  it('calls createMutate and closes modal on success', async () => {
    mockCreateMutate.mockResolvedValueOnce({})
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nueva categoría/i }))
    await waitFor(() => screen.getByRole('dialog'))
    const input = screen.getByLabelText(/nombre/i)
    fireEvent.change(input, { target: { value: 'Postres' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(mockCreateMutate).toHaveBeenCalledWith(
        expect.objectContaining({ nombre: 'Postres' }),
      ),
    )
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/categoría creada/i)).toBeInTheDocument()
  })

  it('shows error toast and keeps modal open when API call fails', async () => {
    mockCreateMutate.mockRejectedValueOnce(new Error('Nombre duplicado'))
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nueva categoría/i }))
    await waitFor(() => screen.getByRole('dialog'))
    const input = screen.getByLabelText(/nombre/i)
    fireEvent.change(input, { target: { value: 'Bebidas' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(screen.getByText(/Nombre duplicado/)).toBeInTheDocument(),
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
    expect(within(dialog).getByText(/eliminar categoría/i)).toBeInTheDocument()
    expect(within(dialog).getByText(/Bebidas/)).toBeInTheDocument()
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
    await waitFor(() => expect(mockDeleteMutate).toHaveBeenCalledWith('cat-1'))
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/eliminada correctamente/i)).toBeInTheDocument()
  })
})
