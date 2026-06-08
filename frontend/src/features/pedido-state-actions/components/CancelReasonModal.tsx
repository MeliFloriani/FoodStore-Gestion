/**
 * CancelReasonModal — modal dialog to collect cancellation reason (motivo).
 *
 * RN-05: motivo is required for all cancellations. This modal enforces
 * non-empty motivo before enabling the confirm button.
 *
 * Change 18: used by both client DELETE and staff PATCH CANCELADO flows.
 */

import React, { useState } from 'react'

export interface CancelReasonModalProps {
  /** Whether the modal is visible */
  isOpen: boolean
  /** Called when user confirms with a non-empty motivo */
  onConfirm: (motivo: string) => void
  /** Called when user cancels/closes the modal */
  onClose: () => void
  /** Whether cancellation is in progress (disables confirm button) */
  isLoading?: boolean
  /** Optional modal title */
  title?: string
}

const MIN_MOTIVO_LENGTH = 3

/**
 * Modal for collecting the mandatory cancellation reason.
 *
 * Enforces:
 * - Non-empty motivo (RN-05)
 * - Minimum length of 3 characters
 * - Confirm button disabled while loading
 */
export function CancelReasonModal({
  isOpen,
  onConfirm,
  onClose,
  isLoading = false,
  title = 'Cancelar pedido',
}: CancelReasonModalProps) {
  const [motivo, setMotivo] = useState('')

  if (!isOpen) {
    return null
  }

  const isValid = motivo.trim().length >= MIN_MOTIVO_LENGTH

  const handleConfirm = () => {
    if (!isValid || isLoading) return
    onConfirm(motivo.trim())
    setMotivo('')
  }

  const handleClose = () => {
    setMotivo('')
    onClose()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') handleClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-modal-title"
      onKeyDown={handleKeyDown}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <h2 id="cancel-modal-title" className="text-lg font-semibold text-gray-900 mb-4">
          {title}
        </h2>

        <div className="mb-4">
          <label
            htmlFor="cancel-motivo"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Motivo de cancelación <span className="text-red-500">*</span>
          </label>
          <textarea
            id="cancel-motivo"
            rows={3}
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ingresá el motivo de la cancelación..."
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500 focus:border-transparent resize-none"
            disabled={isLoading}
            autoFocus
          />
          {motivo.length > 0 && !isValid && (
            <p className="mt-1 text-xs text-red-600">
              El motivo debe tener al menos {MIN_MOTIVO_LENGTH} caracteres.
            </p>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            disabled={isLoading}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            Volver
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!isValid || isLoading}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Confirmar cancelación"
          >
            {isLoading ? 'Cancelando...' : 'Confirmar cancelación'}
          </button>
        </div>
      </div>
    </div>
  )
}
