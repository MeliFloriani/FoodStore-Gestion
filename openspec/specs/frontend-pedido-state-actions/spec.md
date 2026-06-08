# frontend-pedido-state-actions Specification

## Purpose
Frontend integration layer for order state transitions introduced in Change 18 (`order-state-machine-transitions`). Provides TanStack Query hooks for the three new backend endpoints, a thin UI component (`EstadoActionBar`) with available actions per FSM state, and a `CancelReasonModal` that enforces the mandatory `motivo` requirement. Full order panel pages are NOT in scope here — those belong to Change 20.

## ADDED Requirements

---

### Requirement: TanStack Query keys — pedidoEstadoKeys

The feature SHALL define a stable query key factory `pedidoEstadoKeys` for cache invalidation and query coordination with future Change 20 panel queries.

```typescript
export const pedidoEstadoKeys = {
  historial: (pedidoId: string) => ['pedido', pedidoId, 'historial'] as const,
  detail:    (pedidoId: string) => ['pedido', pedidoId] as const,
  list:      ()                 => ['pedidos'] as const,
}
```

Keys SHALL be exported from `src/features/pedido-state-actions/index.ts` so Change 20 can import them without redeclaring.

#### Scenario: Query key shape is consistent for invalidation
- **WHEN** `useTransitionEstado.onSuccess` calls `queryClient.invalidateQueries`
- **THEN** it uses `pedidoEstadoKeys.detail(pedidoId)` and `pedidoEstadoKeys.historial(pedidoId)`
- **THEN** any other query that used `['pedido', pedidoId]` as its key is also invalidated

---

### Requirement: useTransitionEstado hook — PATCH staff transition

The system SHALL implement `useTransitionEstado(pedidoId: string)` as a TanStack Query `useMutation` hook that calls `PATCH /api/v1/pedidos/{pedidoId}/estado`.

```typescript
interface TransitionEstadoPayload {
  nuevo_estado: string
  motivo?: string
}
```

On success, the hook SHALL invalidate `pedidoEstadoKeys.detail(pedidoId)` and `pedidoEstadoKeys.historial(pedidoId)`.

The hook SHALL NOT perform optimistic updates — keep it simple.

#### Scenario: Successful transition invalidates cache keys
- **WHEN** `mutateAsync({ nuevo_estado: "EN_CAMINO" })` resolves
- **THEN** TanStack Query refetches the order detail and historial queries for that `pedidoId`

#### Scenario: API error is surfaced via hook's isError state
- **WHEN** the PATCH returns HTTP 409 `INVALID_TRANSITION`
- **THEN** `isError === true` and `error` contains the API error response
- **THEN** no cache invalidation occurs

---

### Requirement: useCancelarPedidoCliente hook — DELETE CLIENT cancellation

The system SHALL implement `useCancelarPedidoCliente(pedidoId: string)` as a TanStack Query `useMutation` hook that calls `DELETE /api/v1/pedidos/{pedidoId}` with optional body `{ motivo?: string }`.

On success, the hook SHALL invalidate `pedidoEstadoKeys.detail(pedidoId)` and `pedidoEstadoKeys.list()`.

The hook SHALL reside in `src/features/pedido-state-actions/hooks/useCancelarPedidoCliente.ts`.

#### Scenario: Successful cancellation invalidates list and detail caches
- **WHEN** `mutateAsync({ motivo: "Ya no lo quiero" })` resolves with HTTP 200
- **THEN** `pedidoEstadoKeys.detail(pedidoId)` query is invalidated
- **THEN** `pedidoEstadoKeys.list()` query is invalidated (order status changed in any list)

#### Scenario: Axios sends DELETE with body
- **WHEN** `mutateAsync({ motivo: "..." })` is called
- **THEN** the Axios call is `delete('/api/v1/pedidos/${pedidoId}', { data: { motivo } })`
- **THEN** if `motivo` is undefined, the body is omitted

---

### Requirement: useHistorialPedido hook — GET order historial

The system SHALL implement `useHistorialPedido(pedidoId: string)` as a TanStack Query `useQuery` hook that calls `GET /api/v1/pedidos/{pedidoId}/historial`.

```typescript
interface HistorialRead {
  id: string
  pedido_id: string
  estado_desde: string | null
  estado_hacia: string
  motivo: string | null
  actor_user_id: string | null
  created_at: string  // ISO 8601
}
```

Query key: `pedidoEstadoKeys.historial(pedidoId)`.

#### Scenario: Historial query returns ordered list
- **WHEN** `useHistorialPedido(pedidoId)` resolves
- **THEN** `data` is `HistorialRead[]` ordered by `created_at ASC` (as returned by backend)
- **THEN** `isLoading` transitions from `true` to `false` on success

#### Scenario: STOCK user gets a 403 from the backend
- **WHEN** a STOCK user renders a component that calls `useHistorialPedido`
- **THEN** `isError === true` with status 403
- **THEN** the component can check `error.response?.status === 403` to render appropriate feedback

---

### Requirement: EstadoActionBar component

`EstadoActionBar` SHALL be a React component that renders action buttons for the current order state. It accepts:

```typescript
interface EstadoActionBarProps {
  pedidoId: string
  currentEstado: string
  userRole: string       // "ADMIN" | "PEDIDOS" | "CLIENT"
  onCancelClick: () => void  // opens CancelReasonModal
}
```

The component SHALL derive available actions from the `FRONTEND_ALLOWED_TRANSITIONS` constant (defined in `pedidoEstadoApi.ts`) to avoid rendering buttons for impossible transitions. It SHALL call `useTransitionEstado` for advance transitions. For cancellation it SHALL call `onCancelClick` to open the modal.

The component does NOT implement full design system polish — that is Change 24's responsibility. A functional button group is sufficient.

> **Non-authorization rule**: `EstadoActionBar` SHALL NOT use the frontend transition map as an authorization source. The `FRONTEND_ALLOWED_TRANSITIONS` map is UI-only — it is used to hide buttons that are not applicable, not to gate access. The backend SHALL always validate transitions and return 409/403 for invalid attempts. The component must handle these error responses gracefully (via the toast error mapping in `ESTADO_ERROR_MESSAGES`).

#### Scenario: PEDIDOS user on CONFIRMADO order sees EN_PREP and CANCELADO buttons
- **WHEN** `EstadoActionBar` renders with `currentEstado = "CONFIRMADO"` and `userRole = "PEDIDOS"`
- **THEN** an "Avanzar a EN_PREP" button is rendered
- **THEN** a "Cancelar pedido" button is rendered
- **THEN** no other transition buttons are rendered

#### Scenario: PEDIDOS user on EN_PREP order does NOT see cancel button
- **WHEN** `EstadoActionBar` renders with `currentEstado = "EN_PREP"` and `userRole = "PEDIDOS"`
- **THEN** an "Avanzar a EN_CAMINO" button is rendered
- **THEN** NO cancel button is rendered (only ADMIN can cancel EN_PREP — RN-RB08)

#### Scenario: CLIENT user on PENDIENTE order sees only Cancel button
- **WHEN** `EstadoActionBar` renders with `currentEstado = "PENDIENTE"` and `userRole = "CLIENT"`
- **THEN** only a "Cancelar pedido" button is rendered

#### Scenario: Terminal state renders no action buttons
- **WHEN** `EstadoActionBar` renders with `currentEstado = "ENTREGADO"` or `"CANCELADO"`
- **THEN** no action buttons are rendered
- **THEN** a read-only status indicator is displayed instead

---

### Requirement: CancelReasonModal component

`CancelReasonModal` SHALL be a controlled modal with a `<textarea>` for the cancellation reason. It SHALL enforce that the reason is non-empty before enabling the confirm button (mirroring backend RN-05).

```typescript
interface CancelReasonModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (motivo: string) => void
  isPending: boolean   // disables confirm button while mutation is in-flight
}
```

The component SHALL NOT call the mutation directly — it delegates via `onConfirm`. The parent (`EstadoActionBar` or a page wrapper) owns the mutation call.

#### Scenario: Confirm button disabled when reason is empty
- **WHEN** `CancelReasonModal` is open and the textarea is empty
- **THEN** the "Confirmar cancelación" button is `disabled`

#### Scenario: Confirm button enabled when reason has content
- **WHEN** the user types at least one non-whitespace character in the textarea
- **THEN** the confirm button becomes enabled

#### Scenario: onConfirm called with trimmed motivo
- **WHEN** the user types "  espacios innecesarios  " and clicks confirm
- **THEN** `onConfirm` is called with `"espacios innecesarios"` (trimmed)

#### Scenario: isPending disables submit and shows loading state
- **WHEN** `isPending = true` is passed (mutation is in-flight)
- **THEN** the confirm button is disabled
- **THEN** a loading indicator (spinner or text) is visible

---

### Requirement: Error mapping to toast notifications

The feature SHALL map backend error codes to user-facing toast messages via the shared toast utility from `frontend-error-handling`. The mapping SHALL be defined in `src/features/pedido-state-actions/api/pedidoEstadoApi.ts` or a dedicated `errorMessages.ts`.

| Backend `code` | Toast message |
|---|---|
| `INVALID_TRANSITION` | "Transición de estado no permitida desde el estado actual." |
| `TERMINAL_STATE` | "El pedido ya está en un estado terminal y no puede modificarse." |
| `MOTIVO_REQUIRED` | "Debes ingresar un motivo para cancelar el pedido." |
| `CANCEL_NOT_ALLOWED_FOR_ROLE` | "Tu rol no permite cancelar pedidos en este estado." |
| `ORDER_NOT_FOUND` | "Pedido no encontrado." |
| `ORDER_NOT_OWNED` | "No puedes cancelar un pedido que no es tuyo." |
| Unrecognized error | "Ocurrió un error al actualizar el estado del pedido." |

#### Scenario: 409 INVALID_TRANSITION surfaces correct toast
- **WHEN** `useTransitionEstado` mutation fails with backend `code = "INVALID_TRANSITION"`
- **THEN** the toast "Transición de estado no permitida desde el estado actual." is shown
- **THEN** no success side-effect occurs

#### Scenario: 422 MOTIVO_REQUIRED surfaces correct toast
- **WHEN** the DELETE or PATCH mutation fails with `code = "MOTIVO_REQUIRED"`
- **THEN** the toast "Debes ingresar un motivo para cancelar el pedido." is shown
- **THEN** `CancelReasonModal` remains open (or is reopened) so the user can correct the input

---

### Requirement: FSD layer compliance

All new files SHALL follow Feature-Sliced Design layer rules:
- `features/pedido-state-actions/` may import from `entities/` and `shared/` only.
- `features/pedido-state-actions/` SHALL NOT import from `pages/` or other `features/`.
- Hooks SHALL import Axios from the shared HTTP client (`src/shared/api/httpClient.ts` or equivalent from `frontend-http-client` spec).
- No state duplication: order state from the backend is managed exclusively by TanStack Query; no Zustand store is added for this feature.

#### Scenario: FSD import direction is respected
- **WHEN** the feature's source files are statically analyzed
- **THEN** no import crosses upward (no import from `pages/` or sibling features)
- **THEN** Axios calls use the shared interceptor-equipped client
