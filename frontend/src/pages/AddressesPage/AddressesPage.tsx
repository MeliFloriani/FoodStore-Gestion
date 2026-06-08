/**
 * AddressesPage — delivery address management page.
 *
 * Change 14: delivery-addresses-management.
 *
 * Replaces the Change 08 placeholder at /addresses.
 * Displays the user's delivery addresses with full CRUD:
 *   - List with loading skeleton / empty state / address cards
 *   - Badge "Principal" on the current principal address
 *   - "Establecer como principal" button (hidden if already principal)
 *   - "Editar" button → opens AddressFormModal in edit mode
 *   - "Eliminar" button → shows confirmation dialog before deleting
 *   - "Agregar dirección" button → opens AddressFormModal in create mode
 *
 * Route is protected by RoleGuard(['CLIENT']) in routes.tsx (pre-Change-24:
 * addresses belong to the CLIENT purchase flow; ADMIN gets /403 here).
 *
 * Design: refined, minimal with purposeful use of color and space.
 * Uses Tailwind tokens consistent with the rest of the project.
 * Accessible: aria-labels on icon-only buttons, htmlFor on all form labels.
 */

import { useState } from 'react'
import { useForm } from '@tanstack/react-form'
import {
  useAddresses,
  useCreateAddress,
  useUpdateAddress,
  useSetMainAddress,
  useDeleteAddress,
} from '@/entities/direccion-entrega'
import type { DireccionEntrega, DireccionEntregaCreateDto, DireccionEntregaUpdateDto } from '@/entities/direccion-entrega'

// ---------------------------------------------------------------------------
// AddressSkeleton
// ---------------------------------------------------------------------------

function AddressSkeleton() {
  return (
    <div role="status" aria-label="Cargando direcciones" className="space-y-4 animate-pulse">
      {[1, 2].map((i) => (
        <div key={i} className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/3"></div>
          <div className="h-3 bg-gray-200 rounded w-2/3"></div>
          <div className="h-3 bg-gray-200 rounded w-1/2"></div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AddressFormModal
// ---------------------------------------------------------------------------

type AddressFormModalProps = {
  initialData?: DireccionEntrega | null
  onClose: () => void
}

function AddressFormModal({ initialData, onClose }: AddressFormModalProps) {
  const createMutation = useCreateAddress()
  const updateMutation = useUpdateAddress()
  const isEditing = !!initialData

  const form = useForm({
    defaultValues: {
      alias: initialData?.alias ?? '',
      linea1: initialData?.linea1 ?? '',
      linea2: initialData?.linea2 ?? '',
      ciudad: initialData?.ciudad ?? '',
      provincia: initialData?.provincia ?? '',
      codigo_postal: initialData?.codigo_postal ?? '',
      referencia: initialData?.referencia ?? '',
    },
    onSubmit: async ({ value }) => {
      const cleaned = {
        alias: value.alias?.trim() || null,
        linea1: value.linea1.trim(),
        linea2: value.linea2?.trim() || null,
        ciudad: value.ciudad?.trim() || null,
        provincia: value.provincia?.trim() || null,
        codigo_postal: value.codigo_postal?.trim() || null,
        referencia: value.referencia?.trim() || null,
      }

      if (isEditing && initialData) {
        updateMutation.mutate(
          { id: initialData.id, data: cleaned as DireccionEntregaUpdateDto },
          { onSuccess: onClose },
        )
      } else {
        createMutation.mutate(cleaned as DireccionEntregaCreateDto, { onSuccess: onClose })
      }
    },
  })

  const isPending = createMutation.isPending || updateMutation.isPending
  const isError = createMutation.isError || updateMutation.isError

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label={isEditing ? 'Editar dirección' : 'Agregar dirección'}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEditing ? 'Editar dirección' : 'Agregar dirección'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar formulario"
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void form.handleSubmit()
          }}
          noValidate
          className="px-6 py-5 space-y-4"
        >
          {/* Alias */}
          <form.Field
            name="alias"
            validators={{
              onChange: ({ value }) => {
                if (value && value.length > 50) return 'El alias no puede superar 50 caracteres'
                return undefined
              },
            }}
          >
            {(field) => (
              <div>
                <label htmlFor="alias" className="block text-sm font-medium text-gray-700 mb-1">
                  Alias <span className="text-gray-400 font-normal">(opcional)</span>
                </label>
                <input
                  id="alias"
                  type="text"
                  placeholder="Casa, Trabajo…"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  maxLength={50}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="text-red-500 text-xs mt-1" role="alert">
                    {field.state.meta.errors[0]}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          {/* Línea 1 (requerido) */}
          <form.Field
            name="linea1"
            validators={{
              onChange: ({ value }) => {
                if (!value || value.trim().length < 3)
                  return 'La dirección es requerida (mínimo 3 caracteres)'
                return undefined
              },
            }}
          >
            {(field) => (
              <div>
                <label htmlFor="linea1" className="block text-sm font-medium text-gray-700 mb-1">
                  Calle y número <span className="text-red-500">*</span>
                </label>
                <input
                  id="linea1"
                  type="text"
                  placeholder="Av. Siempre Viva 742"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  maxLength={255}
                  required
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="text-red-500 text-xs mt-1" role="alert">
                    {field.state.meta.errors[0]}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          {/* Línea 2 */}
          <form.Field name="linea2">
            {(field) => (
              <div>
                <label htmlFor="linea2" className="block text-sm font-medium text-gray-700 mb-1">
                  Piso / Depto <span className="text-gray-400 font-normal">(opcional)</span>
                </label>
                <input
                  id="linea2"
                  type="text"
                  placeholder="Piso 3, Depto B"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  maxLength={255}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
          </form.Field>

          {/* Ciudad + Provincia */}
          <div className="grid grid-cols-2 gap-3">
            <form.Field name="ciudad">
              {(field) => (
                <div>
                  <label htmlFor="ciudad" className="block text-sm font-medium text-gray-700 mb-1">
                    Ciudad
                  </label>
                  <input
                    id="ciudad"
                    type="text"
                    placeholder="Buenos Aires"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                    maxLength={100}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}
            </form.Field>

            <form.Field name="provincia">
              {(field) => (
                <div>
                  <label htmlFor="provincia" className="block text-sm font-medium text-gray-700 mb-1">
                    Provincia
                  </label>
                  <input
                    id="provincia"
                    type="text"
                    placeholder="CABA"
                    value={field.state.value}
                    onChange={(e) => field.handleChange(e.target.value)}
                    onBlur={field.handleBlur}
                    maxLength={100}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}
            </form.Field>
          </div>

          {/* Código Postal */}
          <form.Field name="codigo_postal">
            {(field) => (
              <div>
                <label htmlFor="codigo_postal" className="block text-sm font-medium text-gray-700 mb-1">
                  Código Postal <span className="text-gray-400 font-normal">(opcional)</span>
                </label>
                <input
                  id="codigo_postal"
                  type="text"
                  placeholder="C1001"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  maxLength={10}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
          </form.Field>

          {/* Referencia */}
          <form.Field name="referencia">
            {(field) => (
              <div>
                <label htmlFor="referencia" className="block text-sm font-medium text-gray-700 mb-1">
                  Referencia <span className="text-gray-400 font-normal">(opcional)</span>
                </label>
                <input
                  id="referencia"
                  type="text"
                  placeholder="Portero automático, timbre en lateral…"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  maxLength={255}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            )}
          </form.Field>

          {/* Error */}
          {isError && (
            <p className="text-red-500 text-sm" role="alert">
              Error al guardar la dirección. Intenta nuevamente.
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isPending ? 'Guardando…' : isEditing ? 'Guardar cambios' : 'Agregar dirección'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DeleteConfirmDialog
// ---------------------------------------------------------------------------

type DeleteConfirmDialogProps = {
  onConfirm: () => void
  onCancel: () => void
  isLoading: boolean
}

function DeleteConfirmDialog({ onConfirm, onCancel, isLoading }: DeleteConfirmDialogProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      role="dialog"
      aria-modal="true"
      aria-label="Confirmar eliminación"
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h3 className="text-base font-semibold text-gray-900 mb-2">Eliminar dirección</h3>
        <p className="text-sm text-gray-600 mb-6">
          ¿Querés eliminar esta dirección? Esta acción no se puede deshacer.
        </p>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg text-sm hover:bg-gray-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg text-sm hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Eliminando…' : 'Eliminar'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AddressCard
// ---------------------------------------------------------------------------

type AddressCardProps = {
  address: DireccionEntrega
  onEdit: (address: DireccionEntrega) => void
  onSetMain: (id: string) => void
  onDelete: (id: string) => void
  isSettingMain: boolean
}

function AddressCard({ address, onEdit, onSetMain, onDelete, isSettingMain }: AddressCardProps) {
  const displayName = address.alias ?? address.linea1
  const fullAddress = [address.linea1, address.linea2, address.ciudad, address.provincia]
    .filter(Boolean)
    .join(', ')

  return (
    <div
      className={`bg-white rounded-xl border shadow-sm p-5 transition-all ${
        address.es_principal ? 'border-blue-200 ring-1 ring-blue-200' : 'border-gray-100'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-medium text-gray-900 text-sm truncate">{displayName}</span>
            {address.es_principal && (
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700"
                aria-label="Dirección principal"
              >
                Principal
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 truncate">{fullAddress}</p>
          {address.codigo_postal && (
            <p className="text-xs text-gray-400 mt-0.5">CP: {address.codigo_postal}</p>
          )}
          {address.referencia && (
            <p className="text-xs text-gray-400 mt-0.5 italic">{address.referencia}</p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          {/* Edit */}
          <button
            type="button"
            onClick={() => onEdit(address)}
            aria-label={`Editar ${displayName}`}
            className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
          </button>

          {/* Delete */}
          <button
            type="button"
            onClick={() => onDelete(address.id)}
            aria-label={`Eliminar ${displayName}`}
            className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Set as main button */}
      {!address.es_principal && (
        <div className="mt-3 pt-3 border-t border-gray-50">
          <button
            type="button"
            onClick={() => onSetMain(address.id)}
            disabled={isSettingMain}
            aria-label={`Establecer ${displayName} como dirección principal`}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isSettingMain ? 'Actualizando…' : 'Establecer como principal'}
          </button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AddressesPage
// ---------------------------------------------------------------------------

export default function AddressesPage() {
  const { data: addresses, isLoading, isError } = useAddresses()
  const setMainMutation = useSetMainAddress()
  const deleteMutation = useDeleteAddress()

  const [formModal, setFormModal] = useState<{
    open: boolean
    editAddress: DireccionEntrega | null
  }>({ open: false, editAddress: null })

  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const openCreateForm = () => setFormModal({ open: true, editAddress: null })
  const openEditForm = (address: DireccionEntrega) =>
    setFormModal({ open: true, editAddress: address })
  const closeForm = () => setFormModal({ open: false, editAddress: null })

  const handleSetMain = (id: string) => setMainMutation.mutate(id)

  const handleDeleteRequest = (id: string) => setDeleteConfirm(id)
  const handleDeleteConfirm = () => {
    if (deleteConfirm) {
      deleteMutation.mutate(deleteConfirm, { onSuccess: () => setDeleteConfirm(null) })
    }
  }
  const handleDeleteCancel = () => setDeleteConfirm(null)

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Mis Direcciones</h1>
        <button
          type="button"
          onClick={openCreateForm}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          aria-label="Agregar nueva dirección"
        >
          + Agregar dirección
        </button>
      </div>

      {/* Loading state */}
      {isLoading && <AddressSkeleton />}

      {/* Error state */}
      {isError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-center">
          <p className="text-red-700 text-sm">
            No se pudo cargar tus direcciones. Intenta nuevamente.
          </p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && addresses && addresses.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-xl p-8 text-center">
          <div className="w-12 h-12 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg
              className="w-6 h-6 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </div>
          <p className="text-gray-600 text-sm mb-1 font-medium">
            No tenés direcciones guardadas.
          </p>
          <p className="text-gray-500 text-sm mb-5">
            Podés retirar tu pedido en nuestro local o agregar una dirección.
          </p>
          <button
            type="button"
            onClick={openCreateForm}
            className="px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Agregar dirección
          </button>
        </div>
      )}

      {/* Address list */}
      {!isLoading && !isError && addresses && addresses.length > 0 && (
        <div className="space-y-4">
          {addresses.map((address) => (
            <AddressCard
              key={address.id}
              address={address}
              onEdit={openEditForm}
              onSetMain={handleSetMain}
              onDelete={handleDeleteRequest}
              isSettingMain={setMainMutation.isPending}
            />
          ))}
        </div>
      )}

      {/* Form modal */}
      {formModal.open && (
        <AddressFormModal initialData={formModal.editAddress} onClose={closeForm} />
      )}

      {/* Delete confirm dialog */}
      {deleteConfirm !== null && (
        <DeleteConfirmDialog
          onConfirm={handleDeleteConfirm}
          onCancel={handleDeleteCancel}
          isLoading={deleteMutation.isPending}
        />
      )}
    </div>
  )
}
