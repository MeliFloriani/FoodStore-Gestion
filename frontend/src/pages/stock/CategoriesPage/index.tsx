/**
 * StockCategoriesPage — CRUD for categories with modal UX.
 *
 * Route: /stock/categories (RoleGuard ['ADMIN', 'STOCK']).
 *
 * Backend returns categories as a recursive tree (CategoriaTreeNode).
 * This page flattens the tree for the list view (with depth indent).
 *
 * Create/edit opens a modal (CategoriaFormModal).
 * Delete uses useConfirm for confirmation.
 * Success/error feedback shown via useToast (context-based).
 */
import { lazy, Suspense, useMemo, useState } from 'react'
import {
  useCategoriesTree,
  useDeleteCategoria,
  type CategoriaTreeNode,
} from '@/entities/categories'
import { useToast } from '@/shared/ui/toast'
import { useConfirm } from '@/shared/ui/confirm-dialog'
import { SkeletonList } from '@/shared/ui/skeleton'
import { EmptyState } from '@/shared/ui/empty-state'
import type { CategoriaFormItem } from './CategoriaFormModal'

const CategoriaFormModal = lazy(() =>
  import('./CategoriaFormModal').then((m) => ({ default: m.CategoriaFormModal })),
)

function ModalSpinner() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

interface FlatNode {
  id: string
  nombre: string
  descripcion: string | null
  depth: number
}

function flattenTree(nodes: CategoriaTreeNode[], depth = 0): FlatNode[] {
  return nodes.flatMap((n) => [
    { id: n.id, nombre: n.nombre, descripcion: n.descripcion, depth },
    ...flattenTree(n.subcategorias, depth + 1),
  ])
}

type ModalState =
  | { type: 'create' }
  | { type: 'edit'; item: CategoriaFormItem }
  | null

export default function StockCategoriesPage() {
  const [modal, setModal] = useState<ModalState>(null)
  const { toast } = useToast()
  const { confirm } = useConfirm()

  const { data: tree = [], isLoading } = useCategoriesTree()
  const deleteMut = useDeleteCategoria()

  const flat = useMemo(() => flattenTree(tree), [tree])

  function closeModal() {
    setModal(null)
  }

  function handleSuccess(message: string) {
    toast({ variant: 'success', title: message })
    closeModal()
  }

  function handleError(message: string) {
    toast({ variant: 'error', title: message })
  }

  async function handleDeleteClick(node: FlatNode) {
    const ok = await confirm({
      variant: 'destructive',
      title: '¿Eliminar categoría?',
      description: `¿Eliminar "${node.nombre}"? Esta acción no se puede deshacer.`,
    })
    if (!ok) return
    try {
      await deleteMut.mutateAsync(node.id)
      toast({ variant: 'success', title: 'Categoría eliminada correctamente.' })
    } catch (err) {
      toast({
        variant: 'error',
        title: err instanceof Error ? err.message : 'Error al eliminar.',
      })
    }
  }

  return (
    <div className="space-y-6 p-6" data-testid="stock-categories-page">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Gestión de Categorías</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {flat.length} categoría{flat.length !== 1 ? 's' : ''} activa
            {flat.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ type: 'create' })}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          + Nueva categoría
        </button>
      </header>

      {isLoading && <SkeletonList rows={4} />}

      {!isLoading && flat.length === 0 && (
        <EmptyState
          title="Sin categorías"
          description="Aún no hay categorías creadas."
        />
      )}

      {!isLoading && flat.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Nombre</th>
                <th className="px-3 py-2 text-left font-medium">Descripción</th>
                <th className="px-3 py-2 text-right font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {flat.map((node) => (
                <tr key={node.id} className="border-t border-border">
                  <td className="px-3 py-2">
                    <span style={{ paddingLeft: `${node.depth * 16}px` }}>
                      {node.nombre}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {node.descripcion ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() =>
                        setModal({
                          type: 'edit',
                          item: {
                            id: node.id,
                            nombre: node.nombre,
                            descripcion: node.descripcion,
                          },
                        })
                      }
                      className="mr-2 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted transition-colors"
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteClick(node)}
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
          <CategoriaFormModal
            item={modal.type === 'edit' ? modal.item : null}
            tree={tree}
            onClose={closeModal}
            onSuccess={handleSuccess}
            onError={handleError}
          />
        </Suspense>
      )}
    </div>
  )
}
