## Context

Changes 17–19 implementaron la creación atómica de pedidos, la FSM completa con historial append-only y la integración de pagos con MercadoPago Checkout Pro. El estado actual del módulo de pedidos en el backend tiene `POST /api/v1/pedidos`, `PATCH /api/v1/pedidos/{id}/estado`, `DELETE /api/v1/pedidos/{id}`, y `GET /api/v1/pedidos/{id}/historial`. Lo que **no existe** son `GET /api/v1/pedidos` y `GET /api/v1/pedidos/{id}`.

En el frontend, las páginas de listado y detalle de pedidos son placeholder. El hook `useHistorialPedido` y `pedidoEstadoKeys` ya existen en `frontend-pedido-state-actions`. El hook `usePaymentStatus` ya existe en `frontend-payment-polling`. El routing define `/orders` como `OrdersPage` placeholder y `/pedidos-panel/*` como subtree placeholder.

## Goals / Non-Goals

**Goals:**
- Exponer `GET /api/v1/pedidos` con discriminación RBAC: CLIENT filtra server-side por `usuario_id`; PEDIDOS/ADMIN acceden a todos con filtros opcionales.
- Exponer `GET /api/v1/pedidos/{id}` con 403 explícito para acceso cruzado de CLIENT.
- Implementar las 5 páginas/paneles frontend enumerados en la propuesta.
- Implementar `OrderHistoryTimeline` como componente reusable que consume el historial del Change 18.
- Integrar polling de `usePaymentStatus` en el detalle del pedido sin duplicar la lógica del Change 19.
- Paginación en todos los listados con el schema `Page[T]` de `backend-pagination-schema`.
- Panel de gestión con filtros debounced (estado, fechas, búsqueda de cliente).

**Non-Goals:**
- Cambios de estado del pedido (Change 18, ya implementado — se invoca desde el detalle mediante componentes existentes de `frontend-pedido-state-actions`).
- Flujo de pago o creación de preferencias MP (Change 19).
- Notificaciones push/email/SMS.
- Gestión de usuarios (Change 21).
- Dashboard de métricas con recharts (Change 23).
- Snapshot completo de dirección: la dirección se expone como FK nullable en el response (`direccion_id` + datos básicos si la FK no es NULL). El snapshot completo de dirección (nombre, calle, ciudad en el momento del pedido) es **deuda OQ-01** — documentada, no cerrada aquí.
- Endpoints `/api/v1/admin/pedidos`: Integrador §5.3 define un único `GET /api/v1/pedidos` con discriminación por RBAC. No existe un sub-router separado `/admin/pedidos`. Esta decisión se adopta fielmente (ver D-01).

## Decisions

### D-01 — Un solo endpoint GET /api/v1/pedidos con discriminación RBAC (sigue Integrador §5.3)

Integrador §5.3 especifica:

```
GET /api/v1/pedidos — Listar propios (CLIENT) o todos (ADMIN/PEDIDOS) — Rol: CLIENT/ADMIN/PEDIDOS
GET /api/v1/pedidos/{id} — Detalle completo — Rol: Propietario/ADMIN
```

Historial de usuario US-051 menciona `GET /api/admin/pedidos` como nota técnica, pero la fuente de verdad es `Integrador.txt §5.3`. Se sigue el Integrador: un solo endpoint con discriminación server-side. Los filtros adicionales para PEDIDOS/ADMIN (`desde`, `hasta`, `cliente`) se ignoran silenciosamente si el rol es CLIENT. El parámetro `?usuario_id=` no está expuesto (isolación de CLIENT).

**Discriminación en el service:**
```python
if current_user.has_role("CLIENT"):
    # Filter WHERE pedido.usuario_id = current_user.id
    # Ignore desde/hasta/cliente params
else:
    # Apply optional filters: estado, desde, hasta, cliente
```

**Alternativa descartada**: sub-router `/api/v1/admin/pedidos`. Razón: contradiría el Integrador §5.3 y duplicaría handlers.

### D-02 — 403 explícito (no 404) para acceso cruzado de CLIENT en GET /api/v1/pedidos/{id}

RN-RB05 (referenciado en el scope) establece que un CLIENT que intente ver un pedido ajeno recibe **403**, no 404. El backend verifica `pedido.usuario_id == current_user.id` **después** de verificar que el pedido existe. Si el pedido no existe → 404. Si existe pero no es del CLIENT → 403.

Esto aplica también para STOCK: el rol STOCK no puede ver pedidos (igual que en `/historial` según `backend-order-history`). Roles permitidos en el detalle: CLIENT (propio), PEDIDOS, ADMIN.

### D-03 — PedidoDetail incluye datos del usuario (para roles PEDIDOS/ADMIN)

El schema `PedidoDetail` incluye un bloque `usuario` con datos básicos (`id`, `nombre`, `apellido`, `email`). Un CLIENT que consulta su propio detalle también recibe este bloque (es su propio dato). Esto evita un request adicional desde el panel de gestión.

### D-04 — Snapshot de dirección: solo FK + nombre básico (deuda OQ-01)

La tabla `Pedido.direccion_id` es FK nullable (Change 17, OQ-01). El response expone `direccion_id: UUID | None` y, si no es NULL, hace un JOIN para incluir `{ alias, linea1 }` de la dirección actual. **Advertencia**: si el cliente elimina la dirección después del pedido, el join devuelve NULL aunque el pedido existía con esa dirección. El snapshot completo (guardar los datos en `Pedido`) queda como deuda OQ-01.

### D-05 — Paginación con Page[T] de backend-pagination-schema

Ambos listados (CLIENT y panel) usan `Page[PedidoListItem]` con los params `page: int = 1` y `size: int = 20` (default, max 100). Se reutiliza `create_pagination_meta` del módulo `app/schemas/base.py`.

### D-06 — Polling de PaymentStatus reutilizado, no duplicado

El hook `usePaymentStatus` de `frontend-payment-polling` ya existe y pollea `GET /api/v1/pedidos/{pedidoId}` cada 30s mientras `estado_codigo === "PENDIENTE"`. En la página de detalle del pedido, si el pedido está en `PENDIENTE`, se monta `usePaymentStatus` con el mismo query key `["pedido", pedidoId]`. TanStack Query garantiza que no se hacen requests duplicados: si la página de detalle y `usePaymentStatus` usan el mismo query key, TanStack Query deduplicará los fetches automáticamente. El componente de detalle del pedido usa `useQuery({ queryKey: ["pedido", pedidoId] })` directamente, y el polling se activa como efecto secundario del mismo hook de Change 19 montado condicionalmente.

### D-07 — useHistorialPedido reutilizado (no reimplementado)

El hook `useHistorialPedido(pedidoId)` ya existe en `src/features/pedido-state-actions/`. El componente `OrderHistoryTimeline` importa este hook (respetando FSD: `features/` puede importar de `entities/` y `shared/`). Las páginas importan el timeline desde su feature correspondiente.

### D-08 — OrderConfirmation con routing propio (/order-confirmation/:id)

Post-creación del pedido (Change 17), el hook `useCreateOrder` navega a `/order-confirmation/:id`. Esta URL es independiente de `/orders/:id`: su propósito es mostrar el resumen inmediato post-creación + botón "Pagar con MercadoPago" que inicia el flujo del Change 19 (`POST /api/v1/pagos`). El botón de pago delega al componente `PayWithMercadoPagoButton` de `frontend-checkout-payment`, ya existente. La página NO duplica polling — si el usuario quiere ver el estado del pago, se redirige a `/checkout/return`.

### D-09 — Panel de gestión en /pedidos-panel (placeholder existente en Change 08)

Change 08 registró `/pedidos-panel/*` como placeholder con `RoleGuard roles={['PEDIDOS','ADMIN']}`. Este change conecta ese placeholder con el panel real: `PedidosPanelPage` y `PedidosPanelDetailPage`. La ruta `/pedidos-panel/:id` se agrega como sub-ruta.

### D-10 — Filtros: búsqueda de cliente por email o nombre

Para la búsqueda de cliente en el panel de gestión, el query param es `?cliente=` (string libre). El backend realiza `ILIKE '%{cliente}%'` sobre `usuario.email` OR `usuario.nombre || ' ' || usuario.apellido`. Índice sobre `usuario.email` ya existe (UQ). Para evitar full-table scan en nombre, la búsqueda se aplica únicamente cuando `cliente` tiene al menos 3 caracteres.

### D-11 — Debounce de filtros en el panel: 400ms

Todos los filtros del panel (búsqueda de cliente, rango de fechas) se implementan con debounce de 400ms via `useDebounce` en `src/shared/hooks/useDebounce.ts` (o crear si no existe). El filtro de estado (select) no tiene debounce. TanStack Query invalida el cache al cambiar los query params.

### D-12 — Schemas Pydantic: PedidoListItem y PedidoDetail

```python
# PedidoListItem (para listados)
PedidoListItem:
  id: UUID
  estado_codigo: str
  total: Decimal  # serialized as str
  forma_pago_codigo: str
  items_count: int          # count of DetallePedido rows
  created_at: datetime
  # PEDIDOS/ADMIN only (null for CLIENT responses):
  usuario_nombre: str | None
  usuario_email: str | None

# PedidoDetail (para detalle)
PedidoDetail:
  id: UUID
  usuario_id: UUID
  usuario: UsuarioBasic | None   # { id, nombre, apellido, email }
  estado_codigo: str
  forma_pago_codigo: str
  subtotal: Decimal              # as str
  costo_envio: Decimal           # as str
  total: Decimal                 # as str
  notas: str | None
  direccion_id: UUID | None
  direccion: DireccionBasic | None   # { alias, linea1 } — best-effort, deuda OQ-01
  items: list[DetallePedidoRead]     # from backend-order-creation spec
  historial: list[HistorialRead]     # from backend-order-history spec
  pago: PagoResponse | None          # from backend-pagos-management spec
  created_at: datetime
```

`DetallePedidoRead` ya está definido en `backend-order-creation`. `HistorialRead` ya está definido en `backend-order-history`. `PagoResponse` ya está definido en `backend-pagos-management`. No se duplican.

### D-13 — Filtros backend para PEDIDOS/ADMIN

Query params de `GET /api/v1/pedidos` para PEDIDOS/ADMIN:
- `?estado=` (str, optional) — filtro por `EstadoPedido.codigo`
- `?desde=` (date, optional, ISO 8601) — `pedido.created_at >= desde`
- `?hasta=` (date, optional, ISO 8601) — `pedido.created_at <= hasta + 23:59:59`
- `?cliente=` (str, optional, min 3 chars) — búsqueda ILIKE en email o nombre completo
- `?page=` (int, default 1)
- `?size=` (int, default 20, max 100)

Para CLIENT, únicamente `?estado=`, `?page=` y `?size=` son aceptados. El parámetro `?usuario_id=` **no se expone** (violación de aislamiento CLIENT).

### D-15 — Separación estricta de vistas: CLIENT (comprador) vs PEDIDOS/ADMIN (gestión)

El sistema tiene dos vistas de pedidos con propósitos distintos y poblaciones de usuarios distintas. **No se documenta ni se implementa multi-rol ADMIN+CLIENT**: el rol ADMIN es exclusivamente de gestión y no se asume que los usuarios ADMIN generen pedidos como compradores.

**Vista cliente** (`/orders`, `/orders/:id`, `/order-confirmation/:id`):
- Accesible únicamente para **CLIENT**.
- El backend SIEMPRE filtra por `pedido.usuario_id = current_user.id`.
- Los query params `?desde`, `?hasta`, `?cliente` son ignorados silenciosamente si los envía un CLIENT.
- PEDIDOS y ADMIN son rechazados con 403 por el `RoleGuard` antes de llegar al backend.

**Vista gestión** (`/pedidos-panel`, `/pedidos-panel/:id`):
- Accesible únicamente para **PEDIDOS** y **ADMIN**.
- El backend **NUNCA** filtra por `usuario_id`. Siempre devuelve todos los pedidos del sistema.
- Los filtros `?estado`, `?desde`, `?hasta`, `?cliente` son opcionales y se aplican cuando están presentes.
- Sin filtros → listado completo paginado de todos los pedidos.
- CLIENT es rechazado por el `RoleGuard`.

**Regla de discriminación en el service (endpoint único `GET /api/v1/pedidos`):**
```python
if current_user.has_role("CLIENT"):
    # Vista cliente: filtrar siempre por usuario_id
    # WHERE pedido.usuario_id = current_user.id
    # Ignorar filtros admin (?desde, ?hasta, ?cliente)
else:  # PEDIDOS o ADMIN — vista gestión
    # Sin filtro por usuario_id — ver todos los pedidos del sistema
    # Aplicar filtros opcionales: estado, desde, hasta, cliente
```

**Regla en el frontend:**
- `/orders` → `RoleGuard roles={['CLIENT']}` → usa `useClientOrders` (nunca envía filtros admin).
- `/pedidos-panel` → `RoleGuard roles={['PEDIDOS','ADMIN']}` → usa `useAdminOrders` (puede enviar filtros admin).
- Las dos rutas son mutuamente excluyentes: CLIENT no puede acceder a `/pedidos-panel`, PEDIDOS/ADMIN no pueden acceder a `/orders`.

**Alternativa descartada**: ADMIN con acceso a `/orders` para ver "sus pedidos propios". Razón: no existe una regla documentada de multi-rol ADMIN+CLIENT en este proyecto. ADMIN es exclusivamente un rol de gestión. Si en el futuro se requiere que ADMIN también compre, se introduce como cambio documentado con su propio change (ej. `admin-buyer-mode`).

### D-14 — Omisión de `descuento` en PedidoDetail (Integrador §5.3 vs modelo real)

Integrador §5.3 menciona `descuento` como campo del schema `PedidoDetail`. Sin embargo, el modelo `Pedido` (Change 17, migraciones 0007/0008 archivadas en `openspec/changes/archive/2026-05-21-order-creation-with-snapshots/`) **no implementa la columna `descuento`**: no aparece en `openspec/specs/backend-data-model/spec.md`, `openspec/specs/backend-order-creation/spec.md` ni en ningún spec de change archivado. `PedidoDetail` lo omite intencionalmente.

Si en el futuro se requiere soporte para descuentos, se necesita: migración Alembic con columna `descuento NUMERIC(10,2) DEFAULT 0.00` en `Pedido`, extensión del schema Pydantic `PedidoDetail` con `descuento: Decimal` y actualización del `@field_serializer` correspondiente. Este trabajo está **fuera del alcance de Change 20** y es candidato a un change dedicado (ej. `discount-support`).

### D-16 — Interfaces TypeScript de spec son normativas

Las interfaces TypeScript definidas inline en specs de Change 20 (`PedidoListItem`, `PedidoPage`, `ClientOrdersParams`, `PedidoDetail`, `UsuarioBasic`, `DireccionBasic`) son **normativas**: los archivos en `src/entities/pedido/model/types.ts` (FSD layer) DEBEN coincidir exactamente en nombres de campo, tipos, opcionalidad y nullabilidad. Cualquier divergencia entre spec y código TS debe resolverse actualizando el código, no el spec.

Convención: `snake_case` en backend Pydantic (Read schemas), `snake_case` también en TS interface (sin transformación automática) — el frontend consume el JSON tal cual viene del backend.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|------------|
| R-07: Snapshot incompleto de dirección (OQ-01) — si el cliente elimina su dirección, el detalle del pedido mostrará `direccion: null` aunque el pedido tenía una dirección al crearse. | Documentado como deuda OQ-01. Se muestra `direccion_id` como fallback. El snapshot completo requiere agregar columnas a `Pedido` (migración), fuera de scope. |
| Performance en el listado de PEDIDOS/ADMIN con muchos pedidos y joins a `usuario` | Limitar `size` a 100. Index en `pedido.created_at DESC` para el sort. La búsqueda ILIKE en nombre/apellido puede ser lenta en tablas grandes — mitigado con mínimo 3 chars. |
| Polling duplicado en detalle del pedido + CheckoutReturnPage | Reuso del mismo query key `["pedido", pedidoId]` garantiza deduplicación por TanStack Query. Si ambas páginas están montadas simultáneamente (imposible en SPA), no hay race condition. |
| RoleGuard en /pedidos-panel ya existía como placeholder — cambio de comportamiento al activar la implementación real | El guard `roles={['PEDIDOS','ADMIN']}` no cambia, solo el componente que renderiza. Backward-compatible. |
| R-09 (Checkout Pro): /order-confirmation/:id debe coordinar con /checkout/return sin duplicar polling | OrderConfirmation muestra solo datos estáticos del pedido + botón de pago. No monta usePaymentStatus (ese es rol de CheckoutReturnPage). |

## Deuda Documental

**Deuda doc-D-01**: El Purpose de `openspec/specs/frontend-payment-polling/spec.md` (Change 19) menciona endpoint `/pedidos/{pedido_id}/latest` que es de `backend-pagos-management`, mientras el body del mismo spec referencia `/pedidos/{pedidoId}` (el detalle introducido por este Change 20). La contradicción documental se debe corregir vía micro-change `frontend-payment-polling-purpose-fix` post-archive de Change 20, o como parte del archive de Change 20 si el orchestrator lo aprueba. NO se modifica desde este change para preservar trazabilidad SDD.

## Migration Plan

No hay migraciones de base de datos en este change. Los endpoints son nuevos (no modifican tablas existentes). El routing agrega rutas sin remover existentes. El frontend agrega páginas/features sin eliminar componentes previos.

## Open Questions

- OQ-01 (deuda): ¿Cuándo se agrega el snapshot completo de dirección? Requiere columna `direccion_snapshot JSONB` en `Pedido` + migración. Candidato para Change 24 (UI/UX) o un micro-change futuro.
- OQ-02: ¿Los items del listado CLIENT deben mostrar la primera imagen del primer producto? No está especificado en las historias de usuario. Se excluye del scope y se puede agregar en Change 24.
