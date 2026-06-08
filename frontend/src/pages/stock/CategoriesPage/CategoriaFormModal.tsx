/**
 * CategoriaFormModal — create or edit a category.
 *
 * Mode is determined by `item`:
 *   null  → create mode (empty form)
 *   value → edit mode (pre-populated, parent_id resolved from tree)
 *
 * The tree is passed as a prop (already loaded by the page; avoids double fetch).
 *
 * On success: calls onSuccess(message) then closes via onClose().
 * On error:   calls onError(message), modal stays open.
 */

import { useMemo, useState, type FormEvent } from 'react'
import {
  useCreateCategoria,
  useUpdateCategoria,
  type CategoriaTreeNode,
} from '@/entities/categories'

interface FlatNode {
  id: string
  nombre: string
  depth: number
}

function flattenTree(nodes: CategoriaTreeNode[], depth = 0): FlatNode[] {
  return nodes.flatMap((n) => [
    { id: n.id, nombre: n.nombre, depth },
    ...flattenTree(n.subcategorias, depth + 1),
  ])
}

function findParentId(
  nodes: CategoriaTreeNode[],
  childId: string,
  parentId: string | null,
): string | null {
  for (const n of nodes) {
    if (n.id === childId) return parentId
    const found = findParentId(n.subcategorias, childId, n.id)
    if (found !== null) return found
  }
  return null
}

export interface CategoriaFormItem {
  id: string
  nombre: string
  descripcion: string | null
}

interface CategoriaFormModalProps {
  item: CategoriaFormItem | null
  tree: CategoriaTreeNode[]
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
}

export function CategoriaFormModal({
  item,
  tree,
  onClose,
  onSuccess,
  onError,
}: CategoriaFormModalProps) {
  const isEditing = item !== null

  const resolvedParentId = isEditing ? (findParentId(tree, item.id, null) ?? '') : ''

  const [nombre, setNombre] = useState(item?.nombre ?? '')
  const [descripcion, setDescripcion] = useState(item?.descripcion ?? '')
  const [parentId, setParentId] = useState(resolvedParentId)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const createMut = useCreateCategoria()
  const updateMut = useUpdateCategoria(item?.id ?? '')
  const isPending = createMut.isPending || updateMut.isPending

  const flat = useMemo(() => flattenTree(tree), [tree])
  // Prevent selecting self as parent
  const parentOptions = isEditing ? flat.filter((n) => n.id !== item.id) : flat

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFieldError(null)
    if (nombre.trim().length === 0) {
      setFieldError('El nombre es requerido.')
      return
    }
    const payload = {
      nombre: nombre.trim(),
      descripcion: descripcion.trim() || null,
      parent_id: parentId || null,
    }
    try {
      if (isEditing) {
        await updateMut.mutateAsync(payload)
        onSuccess('Categoría actualizada correctamente.')
      } else {
        await createMut.mutateAsync(payload)
        onSuccess('Categoría creada correctamente.')
      }
      onClose()
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Error al guardar.')
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="categoria-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-background shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 id="categoria-modal-title" className="text-lg font-semibold">
            {isEditing ? 'Editar categoría' : 'Nueva categoría'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isPending}
            aria-label="Cerrar modal"
            className="rounded p-1 hover:bg-muted transition-colors disabled:opacity-50"
          >
            ✕
          </button>
        </div>

        <form
          onSubmit={handleSubmit}
          noValidate
          className="space-y-4 p-4"
          aria-label={isEditing ? 'Editar categoría' : 'Nueva categoría'}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="cat-modal-nombre" className="text-sm font-medium">
              Nombre
            </label>
            <input
              id="cat-modal-nombre"
              type="text"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              disabled={isPending}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              autoFocus
            />
            {fieldError && (
              <p className="text-xs text-destructive" role="alert">
                {fieldError}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="cat-modal-desc" className="text-sm font-medium">
              Descripción
            </label>
            <input
              id="cat-modal-desc"
              type="text"
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              disabled={isPending}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="cat-modal-parent" className="text-sm font-medium">
              Categoría padre
            </label>
            <select
              id="cat-modal-parent"
              value={parentId}
              onChange={(e) => setParentId(e.target.value)}
              disabled={isPending}
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="">— Sin padre (raíz) —</option>
              {parentOptions.map((n) => (
                <option key={n.id} value={n.id}>
                  {'— '.repeat(n.depth)}
                  {n.nombre}
                </option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? 'Guardando…' : isEditing ? 'Guardar cambios' : 'Crear'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
