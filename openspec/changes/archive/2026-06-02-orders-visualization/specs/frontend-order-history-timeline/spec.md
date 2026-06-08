## ADDED Requirements

### Requirement: Componente OrderHistoryTimeline — timeline visual del historial

El sistema SHALL proveer el componente `<OrderHistoryTimeline>` en `src/features/orders/ui/OrderHistoryTimeline.tsx` (o en `src/shared/ui/OrderHistoryTimeline.tsx` si se decide compartirlo entre features).

El componente SHALL:
- Aceptar `pedidoId: string` como prop.
- Consumir `useHistorialPedido(pedidoId)` de `src/features/pedido-state-actions/` (ya existente en Change 18). **No reimplementar el hook.**
- Renderizar una lista cronológica vertical (timeline) de las transiciones de estado.
- Cada entrada del timeline SHALL mostrar:
  - Flecha o conector visual: `estado_desde → estado_hacia` (el primer registro muestra solo `estado_hacia` ya que `estado_desde` es null).
  - Fecha y hora formateada (locale AR: `dd/MM/yyyy HH:mm`).
  - Actor: si `actor_user_id` es null → "Sistema" (transición automática por webhook MP); si no es null → "Gestor" o el `actor_user_id` truncado.
  - Motivo: si `motivo` no es null, mostrar el motivo entre paréntesis o en un sub-texto.
- Mostrar un icono/indicador visual distinto para el estado actual (último entry).
- Mostrar skeleton loaders mientras `useHistorialPedido` está cargando.
- Mostrar mensaje de error amigable si `useHistorialPedido` falla.

El componente SHALL seguir las reglas FSD: puede importar de `entities/` y `shared/`, y puede consumir hooks de `features/pedido-state-actions/` a través de su export público.

#### Scenario: Timeline renderiza todas las transiciones en orden cronológico
- **GIVEN** un pedido con historial: PENDIENTE (creación), CONFIRMADO (webhook), EN_PREP (manual)
- **WHEN** `<OrderHistoryTimeline pedidoId="..." />` se renderiza
- **THEN** el componente muestra 3 entradas en orden cronológico (más antiguo primero)
- **THEN** la primera entrada muestra `estado_hacia: "PENDIENTE"` (con `estado_desde: null`)
- **THEN** la segunda entrada muestra `PENDIENTE → CONFIRMADO`
- **THEN** la tercera entrada muestra `CONFIRMADO → EN_PREP`

#### Scenario: Transición automática de webhook muestra "Sistema"
- **WHEN** una entrada del historial tiene `actor_user_id: null`
- **THEN** el timeline muestra "Sistema" como actor de esa transición

#### Scenario: Primer registro con estado_desde null renderizado correctamente
- **WHEN** el primer entry del historial tiene `estado_desde: null`
- **THEN** el timeline muestra "Pedido creado — PENDIENTE" o similar (no crash por null)

#### Scenario: Skeleton durante la carga del historial
- **WHEN** `useHistorialPedido` está en estado `isLoading`
- **THEN** el timeline muestra skeleton placeholders en lugar de las entradas

#### Scenario: Motivo visible en entradas con motivo
- **WHEN** una entrada del historial tiene `motivo: "Pedido cancelado por el cliente"`
- **THEN** el timeline muestra ese motivo como sub-texto de la entrada

#### Scenario: Componente no duplica el hook useHistorialPedido
- **WHEN** el componente es inspeccionado en el codebase
- **THEN** usa `useHistorialPedido` importado de `features/pedido-state-actions/`
- **THEN** no existe una segunda implementación del fetching de historial

---

### Requirement: FSD compliance del OrderHistoryTimeline

El componente `OrderHistoryTimeline` SHALL cumplir con las reglas de Feature-Sliced Design.

#### Scenario: Import de useHistorialPedido desde su feature exportadora
- **WHEN** se analiza el import en `OrderHistoryTimeline.tsx`
- **THEN** `useHistorialPedido` es importado desde `@/features/pedido-state-actions` (no reimplementado)
- **THEN** no hay imports de `pages/` ni de otras features salvo `pedido-state-actions`
