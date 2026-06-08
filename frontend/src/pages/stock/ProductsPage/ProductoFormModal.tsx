/**
 * ProductoFormModal — create or edit a product.
 *
 * Mode is determined by `item`:
 *   null  → create mode (empty form)
 *   value → edit mode (pre-populated)
 *
 * NOTE on roles: backend POST/PUT/DELETE require ADMIN; PATCH /disponibilidad
 * accepts ADMIN + STOCK. Route guard is ['ADMIN','STOCK'] — backend is
 * authoritative for fine-grained access.
 *
 * precio_base is handled as a string to preserve Decimal precision (H-02).
 * categoria_ids on edit: ProductoRead doesn't include them; user can set new
 * categories. Leave unchecked = don't change (omit from payload).
 *
 * On success: calls onSuccess(message) then closes via onClose().
 * On error:   calls onError(message), modal stays open.
 */

import { useState, type FormEvent } from 'react'
import {
  useCreateProducto,
  useUpdateProducto,
  type ProductoRead,
} from '@/entities/products'
import { type CategoriaTreeNode } from '@/entities/categories'

interface FlatCat {
  id: string
  nombre: string
  depth: number
}

function flattenCategoriesTree(nodes: CategoriaTreeNode[], depth = 0): FlatCat[] {
  return nodes.flatMap((n) => [
    { id: n.id, nombre: n.nombre, depth },
    ...flattenCategoriesTree(n.subcategorias, depth + 1),
  ])
}

interface ProductoFormModalProps {
  item: ProductoRead | null
  categoriesTree: CategoriaTreeNode[]
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
}

export function ProductoFormModal({
  item,
  categoriesTree,
  onClose,
  onSuccess,
  onError,
}: ProductoFormModalProps) {
  const isEditing = item !== null

  const [nombre, setNombre] = useState(item?.nombre ?? '')
  const [descripcion, setDescripcion] = useState(item?.descripcion ?? '')
  const [precioBase, setPrecioBase] = useState(item?.precio_base ?? '')
  const [stockCantidad, setStockCantidad] = useState(
    item ? String(item.stock_cantidad) : '0',
  )
  const [imagenUrl, setImagenUrl] = useState(item?.imagen_url ?? '')
  const [disponible, setDisponible] = useState(item?.disponible ?? true)
  // ProductoRead doesn't expose categoria_ids — starts unchecked (omit from payload)
  const [categoriaIds, setCategoriaIds] = useState<string[]>([])
  const [fieldError, setFieldError] = useState<string | null>(null)

  const createMut = useCreateProducto()
  const updateMut = useUpdateProducto(item?.id ?? '')
  const isPending = createMut.isPending || updateMut.isPending

  const flatCategories = flattenCategoriesTree(categoriesTree)

  function toggleCategory(id: string) {
    setCategoriaIds((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id],
    )
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFieldError(null)
    if (nombre.trim().length === 0) {
      setFieldError('El nombre es requerido.')
      return
    }
    if (!/^\d+(\.\d{1,2})?$/.test(precioBase)) {
      setFieldError('El precio debe ser un número con hasta 2 decimales (ej: 1500.00).')
      return
    }
    const stock = Number(stockCantidad)
    if (!Number.isInteger(stock) || stock < 0) {
      setFieldError('El stock debe ser un entero no negativo.')
      return
    }
    try {
      if (isEditing) {
        await updateMut.mutateAsync({
          nombre: nombre.trim(),
          descripcion: descripcion.trim() || null,
          imagen_url: imagenUrl.trim() || null,
          precio_base: precioBase,
          stock_cantidad: stock,
          disponible,
          ...(categoriaIds.length > 0 ? { categoria_ids: categoriaIds } : {}),
        })
        onSuccess('Producto actualizado correctamente.')
      } else {
        await createMut.mutateAsync({
          nombre: nombre.trim(),
          descripcion: descripcion.trim() || null,
          imagen_url: imagenUrl.trim() || null,
          precio_base: precioBase,
          stock_cantidad: stock,
          disponible,
          categoria_ids: categoriaIds.length > 0 ? categoriaIds : null,
        })
        onSuccess('Producto creado correctamente.')
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
      aria-labelledby="producto-modal-title"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4"
    >
      <div className="my-8 w-full max-w-lg rounded-lg bg-background shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 id="producto-modal-title" className="text-lg font-semibold">
            {isEditing ? 'Editar producto' : 'Nuevo producto'}
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
          aria-label={isEditing ? 'Editar producto' : 'Nuevo producto'}
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <label htmlFor="prd-modal-nombre" className="text-sm font-medium">
                Nombre
              </label>
              <input
                id="prd-modal-nombre"
                type="text"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                disabled={isPending}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                autoFocus
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="prd-modal-precio" className="text-sm font-medium">
                Precio base
              </label>
              <input
                id="prd-modal-precio"
                type="text"
                inputMode="decimal"
                placeholder="0.00"
                value={precioBase}
                onChange={(e) => setPrecioBase(e.target.value)}
                disabled={isPending}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div className="flex flex-col gap-1 sm:col-span-2">
              <label htmlFor="prd-modal-desc" className="text-sm font-medium">
                Descripción
              </label>
              <input
                id="prd-modal-desc"
                type="text"
                value={descripcion}
                onChange={(e) => setDescripcion(e.target.value)}
                disabled={isPending}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div className="flex flex-col gap-1 sm:col-span-2">
              <label htmlFor="prd-modal-imagen" className="text-sm font-medium">
                URL de imagen
              </label>
              <input
                id="prd-modal-imagen"
                type="url"
                placeholder="https://ejemplo.com/imagen.jpg"
                value={imagenUrl}
                onChange={(e) => setImagenUrl(e.target.value)}
                disabled={isPending}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label htmlFor="prd-modal-stock" className="text-sm font-medium">
                Stock
              </label>
              <input
                id="prd-modal-stock"
                type="number"
                min={0}
                step={1}
                value={stockCantidad}
                onChange={(e) => setStockCantidad(e.target.value)}
                disabled={isPending}
                className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>

            <label className="flex items-center gap-2 text-sm sm:mt-6">
              <input
                type="checkbox"
                checked={disponible}
                onChange={(e) => setDisponible(e.target.checked)}
                disabled={isPending}
              />
              Disponible
            </label>
          </div>

          {flatCategories.length > 0 && (
            <fieldset className="rounded-md border border-border p-3">
              <legend className="px-1 text-sm font-medium">
                Categorías{isEditing && ' (dejar sin marcar = sin cambios)'}
              </legend>
              <div className="flex flex-wrap gap-2 pt-1">
                {flatCategories.map((c) => (
                  <label
                    key={c.id}
                    className="flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs"
                  >
                    <input
                      type="checkbox"
                      checked={categoriaIds.includes(c.id)}
                      onChange={() => toggleCategory(c.id)}
                      disabled={isPending}
                    />
                    {'— '.repeat(c.depth)}
                    {c.nombre}
                  </label>
                ))}
              </div>
            </fieldset>
          )}

          {fieldError && (
            <p className="text-sm text-destructive" role="alert">
              {fieldError}
            </p>
          )}

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
