/**
 * StockIngredientsPage — CRUD for ingredients with modal UX.
 *
 * Route: /stock/ingredients (RoleGuard ['ADMIN', 'STOCK']).
 *
 * Create/edit opens a modal (IngredienteFormModal).
 * Delete uses useConfirm for confirmation.
 * Success/error feedback shown via useToast (context-based).
 */
import { lazy, Suspense, useState } from 'react'
import {
  useIngredientes,
  useDeleteIngrediente,
  type Ingrediente,
} from '@/entities/ingrediente'
import { useToast } from '@/shared/ui/toast'
import { useConfirm } from '@/shared/ui/confirm-dialog'
import { SkeletonList } from '@/shared/ui/skeleton'
import { EmptyState } from '@/shared/ui/empty-state'

const IngredienteFormModal = lazy(() =>
  import('./IngredienteFormModal').then((m) => ({ default: m.IngredienteFormModal })),
)

function ModalSpinner() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

type ModalState =
  | { type: 'create' }
  | { type: 'edit'; item: Ingrediente }
  | null

export default function StockIngredientsPage() {
  const [modal, setModal] = useState<ModalState>(null)
  const { toast } = useToast()
  const { confirm } = useConfirm()

  const { data: items = [], isLoading } = useIngredientes()
  const deleteMut = useDeleteIngrediente()

  function closeModal() {
    setModal(null)
  }

  function handleSuccess(message: string) {
    toast({ variant: 'success', title: message })
    closeModal()
  }

  function handleError(message: string) {
    toast({ variant: 'error', title: message })
    // modal stays open (caller handles this)
  }

  async function handleDeleteClick(item: Ingrediente) {
    const ok = await confirm({
      variant: 'destructive',
      title: '¿Eliminar ingrediente?',
      description: `¿Eliminar "${item.nombre}"? Esta acción no se puede deshacer.`,
    })
    if (!ok) return
    try {
      await deleteMut.mutateAsync(item.id)
      toast({ variant: 'success', title: 'Ingrediente eliminado correctamente.' })
    } catch (err) {
      toast({
        variant: 'error',
        title: err instanceof Error ? err.message : 'Error al eliminar.',
      })
    }
  }

  return (
    <div className="space-y-6 p-6" data-testid="stock-ingredients-page">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Gestión de Ingredientes</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {items.length} ingrediente{items.length !== 1 ? 's' : ''} activo
            {items.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ type: 'create' })}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          + Nuevo ingrediente
        </button>
      </header>

      {isLoading && <SkeletonList rows={4} />}

      {!isLoading && items.length === 0 && (
        <EmptyState
          title="Sin ingredientes"
          description="Aún no hay ingredientes registrados."
        />
      )}

      {!isLoading && items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Nombre</th>
                <th className="px-3 py-2 text-left font-medium">Alérgeno</th>
                <th className="px-3 py-2 text-right font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {items.map((ing) => (
                <tr key={ing.id} className="border-t border-border">
                  <td className="px-3 py-2">{ing.nombre}</td>
                  <td className="px-3 py-2">{ing.es_alergeno ? 'Sí' : 'No'}</td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => setModal({ type: 'edit', item: ing })}
                      className="mr-2 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted transition-colors"
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteClick(ing)}
                      disabled={deleteMut.isPending}
                      className="rounded-md border border-destructive px-2 py-1 text-xs text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                    >
                      Eliminar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Form modal — create or edit */}
      {(modal?.type === 'create' || modal?.type === 'edit') && (
        <Suspense fallback={<ModalSpinner />}>
          <IngredienteFormModal
            item={modal.type === 'edit' ? modal.item : null}
            onClose={closeModal}
            onSuccess={handleSuccess}
            onError={handleError}
          />
        </Suspense>
      )}
    </div>
  )
}
