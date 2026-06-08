/**
 * IngredienteFormModal — create or edit an ingredient.
 *
 * Mode is determined by `item`:
 *   null  → create mode (empty form)
 *   value → edit mode (pre-populated)
 *
 * On success: calls onSuccess(message) then closes via onClose().
 * On error:   calls onError(message), modal stays open.
 */

import { useState, type FormEvent } from 'react'
import {
  useCreateIngrediente,
  useUpdateIngrediente,
  type Ingrediente,
} from '@/entities/ingrediente'

interface IngredienteFormModalProps {
  item: Ingrediente | null
  onClose: () => void
  onSuccess: (message: string) => void
  onError: (message: string) => void
}

export function IngredienteFormModal({
  item,
  onClose,
  onSuccess,
  onError,
}: IngredienteFormModalProps) {
  const isEditing = item !== null

  const [nombre, setNombre] = useState(item?.nombre ?? '')
  const [esAlergeno, setEsAlergeno] = useState(item?.es_alergeno ?? false)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const createMut = useCreateIngrediente()
  const updateMut = useUpdateIngrediente(item?.id ?? '')
  const isPending = createMut.isPending || updateMut.isPending

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFieldError(null)
    if (nombre.trim().length === 0) {
      setFieldError('El nombre es requerido.')
      return
    }
    const payload = { nombre: nombre.trim(), es_alergeno: esAlergeno }
    try {
      if (isEditing) {
        await updateMut.mutateAsync(payload)
        onSuccess('Ingrediente actualizado correctamente.')
      } else {
        await createMut.mutateAsync(payload)
        onSuccess('Ingrediente creado correctamente.')
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
      aria-labelledby="ingrediente-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-background shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 id="ingrediente-modal-title" className="text-lg font-semibold">
            {isEditing ? 'Editar ingrediente' : 'Nuevo ingrediente'}
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
          aria-label={isEditing ? 'Editar ingrediente' : 'Nuevo ingrediente'}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="ing-modal-nombre" className="text-sm font-medium">
              Nombre
            </label>
            <input
              id="ing-modal-nombre"
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

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={esAlergeno}
              onChange={(e) => setEsAlergeno(e.target.checked)}
              disabled={isPending}
            />
            Es alérgeno
          </label>

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
