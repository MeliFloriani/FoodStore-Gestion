/**
 * StockProductsPage — CRUD for products with modal UX.
 *
 * Route: /stock/products (RoleGuard ['ADMIN', 'STOCK']).
 *
 * NOTE on roles: backend POST/PUT/DELETE on /api/v1/productos require ADMIN;
 * PATCH /disponibilidad accepts ADMIN or STOCK. Route guard is ['ADMIN','STOCK']
 * — backend stays authoritative for fine-grained access.
 *
 * precio_base is handled as a string to preserve Decimal precision (H-02).
 *
 * Create/edit opens a modal (ProductoFormModal).
 * Delete uses useConfirm for confirmation.
 * Success/error feedback shown via useToast (context-based).
 */
import { lazy, Suspense, useState } from 'react'
import {
  useProductos,
  useDeleteProducto,
  type ProductoRead,
} from '@/entities/products'
import { useCategoriesTree } from '@/entities/categories'
import { useToast } from '@/shared/ui/toast'
import { useConfirm } from '@/shared/ui/confirm-dialog'
import { SkeletonList } from '@/shared/ui/skeleton'
import { EmptyState } from '@/shared/ui/empty-state'

const ProductoFormModal = lazy(() =>
  import('./ProductoFormModal').then((m) => ({ default: m.ProductoFormModal })),
)

function ModalSpinner() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

const PAGE_SIZE = 20

type ModalState =
  | { type: 'create' }
  | { type: 'edit'; item: ProductoRead }
  | null

export default function StockProductsPage() {
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState<ModalState>(null)
  const { toast } = useToast()
  const { confirm } = useConfirm()

  const { data, isLoading } = useProductos({ page, size: PAGE_SIZE })
  const { data: categoriesTree = [] } = useCategoriesTree()
  const deleteMut = useDeleteProducto()

  const items = data?.items ?? []
  const pages = data?.pages ?? 0
  const total = data?.total ?? 0

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

  async function handleDeleteClick(item: ProductoRead) {
    const ok = await confirm({
      variant: 'destructive',
      title: '¿Eliminar producto?',
      description: `¿Eliminar "${item.nombre}"? Esta acción no se puede deshacer.`,
    })
    if (!ok) return
    try {
      await deleteMut.mutateAsync(item.id)
      toast({ variant: 'success', title: 'Producto eliminado correctamente.' })
    } catch (err) {
      toast({
        variant: 'error',
        title: err instanceof Error ? err.message : 'Error al eliminar.',
      })
    }
  }

  return (
    <div className="space-y-6 p-6" data-testid="stock-products-page">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Gestión de Productos</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {total > 0 ? `${total} producto${total !== 1 ? 's' : ''} en total` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModal({ type: 'create' })}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          + Nuevo producto
        </button>
      </header>

      {isLoading && <SkeletonList rows={6} />}

      {!isLoading && items.length === 0 && (
        <EmptyState
          title="Sin productos"
          description="Aún no hay productos en el catálogo."
        />
      )}

      {!isLoading && items.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left font-medium">Nombre</th>
                <th className="px-3 py-2 text-right font-medium">Precio</th>
                <th className="px-3 py-2 text-right font-medium">Stock</th>
                <th className="px-3 py-2 text-center font-medium">Disponible</th>
                <th className="px-3 py-2 text-right font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} className="border-t border-border">
                  <td className="px-3 py-2">{p.nombre}</td>
                  <td className="px-3 py-2 text-right">{p.precio_base}</td>
                  <td className="px-3 py-2 text-right">{p.stock_cantidad}</td>
                  <td className="px-3 py-2 text-center">
                    {p.disponible ? 'Sí' : 'No'}
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      type="button"
                      onClick={() => setModal({ type: 'edit', item: p })}
                      className="mr-2 rounded-md border border-border px-2 py-1 text-xs hover:bg-muted transition-colors"
                    >
                      Editar
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteClick(p)}
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

      {pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Página {page} de {pages}
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || isLoading}
              className="rounded-md border border-border px-3 py-1.5 text-sm font-medium disabled:opacity-50"
            >
              Anterior
            </button>
            <button
              type="button"
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              disabled={page >= pages || isLoading}
              className="rounded-md border border-border px-3 py-1.5 text-sm font-medium disabled:opacity-50"
            >
              Siguiente
            </button>
          </div>
        </div>
      )}

      {/* Form modal — create or edit */}
      {(modal?.type === 'create' || modal?.type === 'edit') && (
        <Suspense fallback={<ModalSpinner />}>
          <ProductoFormModal
            item={modal.type === 'edit' ? modal.item : null}
            categoriesTree={categoriesTree}
            onClose={closeModal}
            onSuccess={handleSuccess}
            onError={handleError}
          />
        </Suspense>
      )}
    </div>
  )
}
