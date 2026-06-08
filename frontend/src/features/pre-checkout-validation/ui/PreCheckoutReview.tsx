/**
 * PreCheckoutReview — Cart validation review component.
 *
 * Fires the pre-checkout validation automatically on mount (D-09: no "Validar" button).
 * Shows:
 *   - Loading spinner while isPending
 *   - Error message + Reintentar button on isError
 *   - Validated item list + detected changes on isSuccess
 *   - Continue button logic:
 *     - "Continuar al pago" — when cambios is empty
 *     - "Continuar con nuevos precios" — when ok=true and only PRECIO_CAMBIADO changes
 *     - Disabled + tooltip — when ok=false with blocking changes
 *   - "Ajustar carrito" — always navigates to /cart
 *
 * Design decision D-05: PRECIO_CAMBIADO alone is non-blocking (ok=true).
 * Design decision D-09: validation fires on-mount, not on button click.
 */

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useValidatePreCheckout } from '../hooks/useValidatePreCheckout'
import type { CambioRead, ItemValidadoRead } from '../model/types'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-64 gap-4" role="status">
      <div
        aria-label="Cargando"
        className="h-10 w-10 animate-spin rounded-full border-4 border-amber-500 border-t-transparent"
      />
      <p className="text-slate-600 font-medium text-lg">Verificando tu carrito...</p>
    </div>
  )
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-64 gap-4 text-center" role="alert">
      <div className="text-4xl">⚠️</div>
      <p className="text-slate-700 font-semibold text-lg">
        No pudimos verificar tu carrito en este momento.
      </p>
      <p className="text-slate-500 text-sm">
        Ocurrió un error al conectar con el servidor. Por favor, intentá de nuevo.
      </p>
      <button
        onClick={onRetry}
        className="px-6 py-2 bg-amber-500 hover:bg-amber-600 text-white font-semibold rounded-lg transition-colors"
      >
        Reintentar
      </button>
    </div>
  )
}

function ItemStatusBadge({ item }: { item: ItemValidadoRead }) {
  if (!item.vigente) {
    return (
      <span className="px-2 py-0.5 text-xs font-semibold bg-red-100 text-red-700 rounded-full">
        No disponible
      </span>
    )
  }
  if (item.disponible === false) {
    return (
      <span className="px-2 py-0.5 text-xs font-semibold bg-orange-100 text-orange-700 rounded-full">
        Deshabilitado
      </span>
    )
  }
  if (item.stock_disponible !== null && item.stock_disponible < item.cantidad_solicitada) {
    return (
      <span className="px-2 py-0.5 text-xs font-semibold bg-yellow-100 text-yellow-700 rounded-full">
        Stock insuficiente ({item.stock_disponible} disponibles)
      </span>
    )
  }
  return (
    <span className="px-2 py-0.5 text-xs font-semibold bg-green-100 text-green-700 rounded-full">
      OK
    </span>
  )
}

function CambioDescription({ cambio }: { cambio: CambioRead }) {
  switch (cambio.tipo) {
    case 'PRODUCTO_NO_VIGENTE':
      return (
        <p className="text-sm text-red-600">
          Este producto ya no está disponible en el catálogo. Eliminalo del carrito para continuar.
        </p>
      )
    case 'PRODUCTO_NO_DISPONIBLE':
      return (
        <p className="text-sm text-orange-600">
          Este producto está temporalmente deshabilitado.
        </p>
      )
    case 'STOCK_INSUFICIENTE': {
      const disponible = cambio.detalle.stock_disponible as number
      const solicitado = cambio.detalle.cantidad_solicitada as number
      return (
        <p className="text-sm text-yellow-700">
          Stock insuficiente: pedís {solicitado} pero solo hay {disponible} disponible
          {disponible !== 1 ? 's' : ''}.
        </p>
      )
    }
    case 'PRECIO_CAMBIADO': {
      const anterior = cambio.detalle.precio_anterior as string
      const actual = cambio.detalle.precio_actual as string
      return (
        <p className="text-sm text-blue-600">
          El precio cambió de ${anterior} a ${actual}.
        </p>
      )
    }
    case 'PERSONALIZACION_INVALIDA': {
      const razon = cambio.detalle.razon as string
      return (
        <p className="text-sm text-red-600">
          Personalización inválida: {razon === 'no_es_removible' ? 'un ingrediente no es removible' : 'ingrediente no válido para este producto'}.
        </p>
      )
    }
    default:
      return <p className="text-sm text-slate-600">Cambio detectado en este producto.</p>
  }
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PreCheckoutReview() {
  const navigate = useNavigate()
  const { mutateAsync, isPending, isError, isSuccess, data } = useValidatePreCheckout()

  // D-09: Fire validation automatically on mount — no "Validar" button
  useEffect(() => {
    void mutateAsync()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleRetry = () => {
    void mutateAsync()
  }

  const handleGoToCart = () => {
    navigate('/cart')
  }

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------
  if (isPending) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <LoadingState />
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Error state
  // -------------------------------------------------------------------------
  if (isError) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8">
        <ErrorState onRetry={handleRetry} />
      </div>
    )
  }

  // -------------------------------------------------------------------------
  // Success state
  // -------------------------------------------------------------------------
  if (!isSuccess || !data) {
    return null
  }

  const { ok, items, cambios } = data

  // Count PRECIO_CAMBIADO changes
  const precioCambiadoCount = cambios.filter((c) => c.tipo === 'PRECIO_CAMBIADO').length
  const hasOnlyPrecioCambiado =
    precioCambiadoCount > 0 && cambios.every((c) => c.tipo === 'PRECIO_CAMBIADO')
  const hasBlockingChanges = !ok

  // Group cambios by producto_id for display
  const cambiosByProducto = cambios.reduce<Record<string, CambioRead[]>>((acc, cambio) => {
    const key = cambio.producto_id
    if (!acc[key]) acc[key] = []
    acc[key].push(cambio)
    return acc
  }, {})

  // -------------------------------------------------------------------------
  // Continue button logic (D-05 UX decision)
  // -------------------------------------------------------------------------
  let continueButtonText = 'Continuar al pago'
  let continueButtonDisabled = false
  let continueButtonTitle: string | undefined

  if (hasOnlyPrecioCambiado) {
    continueButtonText = 'Continuar con nuevos precios'
    continueButtonDisabled = false
  } else if (hasBlockingChanges) {
    continueButtonDisabled = true
    continueButtonTitle = 'Ajustá tu carrito para poder continuar'
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Revisión del carrito</h1>
        <p className="text-slate-500 text-sm mt-1">
          Verificamos tu carrito contra el catálogo actual.
        </p>
      </div>

      {/* Price change warning (D-05) */}
      {hasOnlyPrecioCambiado && (
        <div
          className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-blue-800 text-sm font-medium"
          role="alert"
        >
          Los precios de {precioCambiadoCount} producto{precioCambiadoCount !== 1 ? 's' : ''}
          {' '}cambiaron. Al continuar, aceptás los nuevos precios.
        </div>
      )}

      {/* Blocking changes summary */}
      {hasBlockingChanges && (
        <div
          className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-800 text-sm font-medium"
          role="alert"
        >
          Hay cambios en tu carrito que requieren tu atención antes de continuar.
        </div>
      )}

      {/* Item list */}
      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.producto_id}
            className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-slate-700 font-medium text-sm truncate">
                  Producto: {item.producto_id.slice(0, 8)}…
                </p>
                <p className="text-slate-500 text-xs mt-0.5">
                  Cantidad: {item.cantidad_solicitada}
                  {item.precio_actual && (
                    <> · Precio actual: ${item.precio_actual}</>
                  )}
                  {item.precio_actual && item.precio_percibido !== item.precio_actual && (
                    <> · Tu precio: ${item.precio_percibido}</>
                  )}
                </p>
              </div>
              <ItemStatusBadge item={item} />
            </div>

            {/* Cambios for this item */}
            {cambiosByProducto[item.producto_id] && (
              <div className="mt-3 space-y-1 border-t border-slate-100 pt-3">
                {cambiosByProducto[item.producto_id].map((cambio, idx) => (
                  <CambioDescription key={idx} cambio={cambio} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Action buttons */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={handleGoToCart}
          className="flex-1 px-5 py-2.5 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-semibold rounded-lg transition-colors text-sm"
        >
          Ajustar carrito
        </button>

        <button
          disabled={continueButtonDisabled}
          title={continueButtonTitle}
          className={`flex-1 px-5 py-2.5 font-semibold rounded-lg text-sm transition-colors ${
            continueButtonDisabled
              ? 'bg-slate-200 text-slate-400 cursor-not-allowed'
              : 'bg-amber-500 hover:bg-amber-600 text-white'
          }`}
        >
          {continueButtonText}
        </button>
      </div>
    </div>
  )
}
