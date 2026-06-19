/**
 * IngredientsPage — modal UX tests.
 *
 * Covers:
 *   - Renders ingredient table
 *   - "Nuevo ingrediente" opens create modal
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
import StockIngredientsPage from '../index'
import { ConfirmDialogProvider } from '@/shared/ui/confirm-dialog'
import { ToastProvider } from '@/shared/ui/toast/ToastProvider'

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock('@/shared/ui/toast', async () => {
  const tp = await vi.importActual<typeof import('@/shared/ui/toast/ToastProvider')>('@/shared/ui/toast/ToastProvider')
  const ut = await vi.importActual<typeof import('@/shared/ui/toast/useToast')>('@/shared/ui/toast/useToast')
  return {
    ToastProvider: tp.ToastProvider,
    useToast: ut.useToast,
    Toast: () => null,
  }
})

const mockCreateMutate = vi.fn()
const mockUpdateMutate = vi.fn()
const mockDeleteMutate = vi.fn()

vi.mock('@/entities/ingrediente', () => ({
  useIngredientes: () => ({
    data: [
      { id: 'id-1', nombre: 'Tomate', es_alergeno: false, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' },
      { id: 'id-2', nombre: 'Gluten', es_alergeno: true, created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z' },
    ],
    isLoading: false,
  }),
  useCreateIngrediente: () => ({ mutateAsync: mockCreateMutate, isPending: false }),
  useUpdateIngrediente: () => ({ mutateAsync: mockUpdateMutate, isPending: false }),
  useDeleteIngrediente: () => ({ mutateAsync: mockDeleteMutate, isPending: false }),
}))

// ── Setup ─────────────────────────────────────────────────────────────────────

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <ToastProvider>
          <ConfirmDialogProvider>
            <StockIngredientsPage />
          </ConfirmDialogProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('StockIngredientsPage', () => {
  it('renders the ingredients table', () => {
    renderPage()
    expect(screen.getByText('Tomate')).toBeInTheDocument()
    expect(screen.getByText('Gluten')).toBeInTheDocument()
  })

  it('opens create modal when "Nuevo ingrediente" is clicked', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo ingrediente/i }))
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByRole('heading', { name: /nuevo ingrediente/i })).toBeInTheDocument()
  })

  it('opens edit modal with pre-populated name when "Editar" is clicked', async () => {
    renderPage()
    const editButtons = screen.getAllByRole('button', { name: /editar/i })
    fireEvent.click(editButtons[0]!)
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    const input = screen.getByLabelText(/nombre/i) as HTMLInputElement
    expect(input.value).toBe('Tomate')
  })

  it('calls createMutate and closes modal on success', async () => {
    mockCreateMutate.mockResolvedValueOnce({})
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo ingrediente/i }))
    await waitFor(() => screen.getByRole('dialog'))
    const input = screen.getByLabelText(/nombre/i)
    fireEvent.change(input, { target: { value: 'Cebolla' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(mockCreateMutate).toHaveBeenCalledWith({ nombre: 'Cebolla', es_alergeno: false }),
    )
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/ingrediente creado/i)).toBeInTheDocument()
  })

  it('shows error toast and keeps modal open when API call fails', async () => {
    mockCreateMutate.mockRejectedValueOnce(new Error('Error de servidor'))
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: /nuevo ingrediente/i }))
    await waitFor(() => screen.getByRole('dialog'))
    const input = screen.getByLabelText(/nombre/i)
    fireEvent.change(input, { target: { value: 'Ajo' } })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /crear/i }))
    })
    await waitFor(() =>
      expect(screen.getByRole('dialog')).toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(screen.getByText(/Error de servidor/)).toBeInTheDocument(),
    )
  })

  it('opens delete confirmation modal when "Eliminar" is clicked', async () => {
    renderPage()
    const deleteButtons = screen.getAllByRole('button', { name: /eliminar/i })
    fireEvent.click(deleteButtons[0]!)
    await waitFor(() =>
      expect(screen.getByRole('alertdialog')).toBeInTheDocument(),
    )
    const dialog = screen.getByRole('alertdialog')
    expect(within(dialog).getByText(/eliminar ingrediente/i)).toBeInTheDocument()
    expect(within(dialog).getByText(/Tomate/)).toBeInTheDocument()
  })

  it('calls deleteMutate and shows success toast on delete confirm', async () => {
    mockDeleteMutate.mockResolvedValueOnce({})
    renderPage()
    const deleteButtons = screen.getAllByRole('button', { name: /eliminar/i })
    fireEvent.click(deleteButtons[0]!)
    await waitFor(() => screen.getByRole('alertdialog'))
    const dialog = screen.getByRole('alertdialog')
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: /confirmar/i }))
    })
    await waitFor(() => expect(mockDeleteMutate).toHaveBeenCalledWith('id-1'))
    await waitFor(() =>
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument(),
    )
    expect(screen.getByText(/eliminado correctamente/i)).toBeInTheDocument()
  })
})
