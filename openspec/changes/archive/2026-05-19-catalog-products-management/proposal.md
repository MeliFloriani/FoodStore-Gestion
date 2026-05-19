## Why

Food Store needs a fully operational product catalog before customers can browse, add items to their cart, or place orders. The `producto`, `producto_categoria`, and `producto_ingrediente` tables already exist in the database (migration 0001), and the SQLModel classes are defined in `backend/app/models/catalog.py`, but no CRUD API exists yet. Without Change 11, every downstream sprint (catálogo público, carrito, pedidos, pagos) is blocked.

Change 11 delivers the complete backend product management layer — CRUD with strict RBAC (write = ADMIN only; availability/stock toggles = ADMIN + STOCK), M2M associations to categories and ingredients (endpoints dedicados for ingredients, `categoria_ids` array in PATCH for categories), atomic stock operations via `UPDATE … WHERE stock_cantidad >= :delta RETURNING`, and the minimal frontend entity layer for admin and stock UIs.

**Historias de usuario cubiertas**: US-015, US-016, US-017, US-020, US-021, US-022.

**Sprint**: Sprint 3 — Catálogo II (Change 11 of the consolidated roadmap).

**Dependencias upstream** (deben estar archivados):
- Change 09 — `catalog-categories-management` (archivado 2026-05-18): provee `Categoria` model, `CategoriaRepository`, endpoint `/api/v1/categorias`. Requerido para M2M producto↔categoría.
- Change 10 — `catalog-ingredients-management` (archivado 2026-05-18): provee `Ingrediente` model, `IngredienteRepository`, endpoints `/api/v1/ingredientes`. Requerido para M2M producto↔ingrediente y flag `es_alergeno`.

**Dependencias downstream** (se desbloquean con Change 11):
- Change 12 — `catalog-public-browsing`: listado público de productos filtrado por `disponible=true AND deleted_at IS NULL`.
- Change 15 — `shopping-cart-clientside`: carrito usa `producto_id`, `nombre`, `precio`, `imagen_url` del catálogo.
- Change 16 — `pre-checkout-validations`: valida `disponible`, `stock_cantidad` contra snapshot del carrito.
- Change 17 — `order-creation-with-snapshots`: `nombre_snapshot` + `precio_snapshot` + `SELECT FOR UPDATE` de stock.

---

## What Changes

### New Capabilities

- **`backend-products-management`**: API completa de productos — 9 endpoints, schemas Pydantic v2 (`ProductoBase`, `ProductoCreate`, `ProductoUpdate`, `ProductoRead`, `ProductoDetail`, `ProductoIngredienteRead`, `DisponibilidadUpdate`), `ProductoRepository` con operación atómica de decremento de stock, `ProductoService` con reglas de negocio, RBAC granular por endpoint, RFC 7807 errors.
- **`frontend-products-entity`**: Capa de entidad frontend — tipos TypeScript, fetchers Axios, TanStack Query key factory, hooks de query y mutación para admin/stock panel. Sin páginas ni features en este change.

### Modified Capabilities

- **`backend-api-v1-router`**: Registrar `productos_router` en `build_v1_router` bajo `/api/v1/productos`.
- **`backend-migrations`**: Migration `0005_add_producto_indexes` — índices de performance sobre `producto` (no crea tabla nueva; la tabla existe desde migration 0001).
- **`backend-categorias-management`**: Agregar escenarios de referencia inversa M2M producto↔categoría (el delete-guard de categoría ya incluye `count_active_products`; documentar el comportamiento).
- **`backend-ingredientes-management`**: Agregar escenarios de referencia inversa M2M producto↔ingrediente y comportamiento en soft-delete de producto.

---

## Decisions

**D-01 — RBAC granular por operación (Integrador v5.0 §4.2 y §5.2 vinculantes)**

| Endpoint | Roles permitidos |
|---|---|
| `POST /productos` | ADMIN |
| `PATCH /productos/{id}` | ADMIN |
| `DELETE /productos/{id}` | ADMIN |
| `PATCH /productos/{id}/disponibilidad` | ADMIN, STOCK |
| `POST /productos/{id}/ingredientes` | ADMIN |
| `DELETE /productos/{id}/ingredientes/{ing_id}` | ADMIN |
| `GET /productos`, `GET /productos/{id}`, `GET /productos/{id}/ingredientes` | Público (sin auth) |

Rationale: Integrador §5.2 línea 212–218 especifica explícitamente el rol para cada operación. §4.2 confirma que STOCK puede modificar `disponible` y `stock_cantidad` pero NO tiene CRUD de productos. La decisión de devolver 401/403 ante tokens inválidos/insuficientes es consistente con el patrón de Change 09 y 10.

**D-02 — M2M categorías vía `categoria_ids` en PATCH (no endpoints dedicados)**

`ProductoCreate` y `ProductoUpdate` incluyen `categoria_ids: list[UUID] | None`. El service reemplaza todas las relaciones `producto_categoria` en una transacción al recibir `categoria_ids`. NO se crean endpoints `POST/DELETE /productos/{id}/categorias/{cat_id}`.

Rationale: Integrador §5.2 muestra `PUT /api/v1/productos/{id}` como el único endpoint de actualización de producto (sin endpoints de categoría dedicados). Las historias de usuario US-016 mencionan "se le asignan categorías" en el contexto de gestión del producto, no como operación separada. El patrón replace-all es más simple y evita race conditions en la gestión de la lista de categorías.

**D-03 — M2M ingredientes vía endpoints dedicados**

`POST /productos/{id}/ingredientes` y `DELETE /productos/{id}/ingredientes/{ing_id}` son endpoints separados (Integrador §5.2 líneas 217–218 los lista explícitamente). Payload: `{ ingrediente_id: UUID, es_removible: bool }`. La asociación duplicada producto↔ingrediente devuelve 409 con `code="PRODUCT_INGREDIENT_DUPLICATE"` (no idempotente — el flag `es_removible` puede diferir).

Rationale: Integrador §5.2 los lista como endpoints separados. El flag `es_removible` en `ProductoIngrediente` es semánticamente diferente por asociación y no puede ignorarse si la relación ya existe.

**D-04 — Stock atómico vía `UPDATE ... WHERE stock_cantidad >= :delta RETURNING`**

El `ProductoRepository` expone `decrement_stock(producto_id, delta) -> Producto | None`. Si retorna `None`, el producto no tenía stock suficiente (race condition detectada). El service lanza `AppValidationError(code="INSUFFICIENT_STOCK")`.

Rationale: Evita race conditions sin bloqueo de fila (SELECT FOR UPDATE se reserva para Change 17, donde el checkout requiere consistencia serializable dentro de una transacción larga). El decremento atómico `UPDATE ... WHERE` es O(1) y no bloquea lecturas concurrentes. Alineado con Integrador §5.2 nota en Change 11.

**D-05 — `precio_base` como `Decimal` en Pydantic (no float)**

`ProductoCreate.precio_base: Decimal = Field(ge=0)`. En la respuesta JSON se serializa como string con 2 decimales. El model SQLModel ya usa `DECIMAL(10,2)`.

Rationale: RN-CA04 es explícita: "NUMERIC de precisión fija, nunca float/double". `float` introduce errores de representación binaria inaceptables para precios.

**D-06 — Soft delete preserva pivots; pivots no tienen soft delete propio**

`DELETE /productos/{id}` setea `deleted_at = now()` en `producto`. Los registros en `producto_categoria` y `producto_ingrediente` permanecen (D-31 en catalog.py: `deleted_at` dormant en pivots). El listado público (Change 12) filtra `producto.deleted_at IS NULL`. Restaurar un producto (futuro) recrearía los pivots si fuera necesario.

Rationale: Consistente con el patrón de Change 09 (soft-delete de categoría preserva hijos) y la decisión D-31 del modelo. Los pedidos históricos referencian `DetallePedido.producto_id`; eliminar los pivots podría romper joins en informes futuros.

**D-07 — `GET /productos/{id}/ingredientes` es endpoint público**

Integrador §5.2 lo lista con rol "Público". Change 12 y la personalización del carrito (Change 15) necesitan la lista de ingredientes (con `es_alergeno`, `es_removible`) para que el cliente personalice su pedido antes de confirmar.

**D-08 — Loading strategy anti N+1: `selectinload`**

`ProductoDetail` (respuesta de `GET /productos/{id}`) incluye `categorias` e `ingredientes` cargados con `selectinload(Producto.producto_categorias).selectinload(ProductoCategoria.categoria)` y análogamente para ingredientes. El listado `GET /productos` devuelve `ProductoRead` (sin relaciones anidadas) para evitar N+1 en paginación.

**D-09 — Paginación en `GET /productos` con filtros opcionales**

Reutiliza el contrato de `backend-pagination-schema`: `{ items, total, page, size, pages }`. Filtros opcionales: `page`, `size`, `categoria_id` (UUID), `disponible` (bool), `search` (str — ILIKE `%search%` sobre `nombre`). Los filtros de Change 12 (alérgenos, catálogo público solo) se añadirán en ese change.

**D-10 — Migration `0005` solo agrega índices sobre tabla `producto` existente**

Migration 0001 ya creó la tabla `producto` con los CHECK constraints. Migration 0005 agrega:
- `ix_producto_disponible` — `(disponible) WHERE deleted_at IS NULL` — optimiza el filtro de Change 12.
- `ix_producto_nombre_search` — `(nombre text_pattern_ops) WHERE deleted_at IS NULL` — optimiza ILIKE con prefijo.
No hay DDL de tablas nuevas ni columnas nuevas (los pivots `producto_categoria` y `producto_ingrediente` ya existen en migration 0001).

---

## Impact

**Backend** — Archivos nuevos (layer-first):
- `backend/app/schemas/producto.py` — 7 schemas Pydantic v2
- `backend/app/repositories/producto.py` — `ProductoRepository(BaseRepository[Producto])`
- `backend/app/services/producto.py` — `ProductoService`
- `backend/app/api/v1/productos.py` — `productos_router` (9 endpoints)

**Backend** — Archivos modificados:
- `backend/app/core/uow.py` — agregar `uow.productos: ProductoRepository` lazy accessor
- `backend/app/api/v1/router.py` — registrar `productos_router` con prefix `/productos`

**Database** — Migration `0005_add_producto_indexes` (ALTER, sin CREATE TABLE):
- `ix_producto_disponible` — partial index sobre `disponible`
- `ix_producto_nombre_search` — partial index sobre `nombre` con `text_pattern_ops`

**Frontend** — Archivos nuevos:
- `frontend/src/entities/products/model/types.ts` — interfaces TypeScript
- `frontend/src/entities/products/api/productoFetchers.ts` — fetchers Axios
- `frontend/src/entities/products/model/useProductos.ts` — hooks TanStack Query (read)
- `frontend/src/entities/products/model/useProductoMutations.ts` — hooks de mutación (admin/stock)
- `frontend/src/entities/products/index.ts` — barrel export

**Frontend** — Archivos modificados:
- `frontend/src/shared/api/endpoints.ts` — constante `PRODUCTOS`

---

## RBAC Matrix

| Endpoint | Sin token | CLIENT | STOCK | PEDIDOS | ADMIN |
|---|---|---|---|---|---|
| `GET /productos` | 200 | 200 | 200 | 200 | 200 |
| `GET /productos/{id}` | 200 | 200 | 200 | 200 | 200 |
| `GET /productos/{id}/ingredientes` | 200 | 200 | 200 | 200 | 200 |
| `POST /productos` | 401 | 403 | 403 | 403 | 201 |
| `PATCH /productos/{id}` | 401 | 403 | 403 | 403 | 200 |
| `DELETE /productos/{id}` | 401 | 403 | 403 | 403 | 204 |
| `PATCH /productos/{id}/disponibilidad` | 401 | 403 | 200 | 403 | 200 |
| `POST /productos/{id}/ingredientes` | 401 | 403 | 403 | 403 | 201 |
| `DELETE /productos/{id}/ingredientes/{ing_id}` | 401 | 403 | 403 | 403 | 204 |

---

## Out of Scope (Change 11)

Los siguientes ítems están explícitamente fuera del alcance de este change:

- **Listado público de productos (Change 12)**: filtros avanzados por `es_alergeno`, UI de catálogo con TanStack Query cache, paginación con debounce, skeleton loaders. Change 12 depende de este change.
- **Decremento real de stock en checkout (Change 17)**: el `ProductoRepository.decrement_stock` se declara aquí como bloque reutilizable; la lógica de `SELECT FOR UPDATE` dentro de la transacción del pedido se implementa en Change 17.
- **Validación pre-checkout de disponibilidad/precio (Change 16)**: Change 16 consume los endpoints de este change pero los implementa allí.
- **Gestión de stock PATCH dedicado (no en scope de Integrador v5.0 §5.2)**: el stock se actualiza vía `PATCH /productos/{id}` (campo `stock_cantidad`) por ADMIN, y por `decrement_stock` interno (Change 17). No hay endpoint `PATCH /productos/{id}/stock` separado (el Integrador §5.2 no lo lista).
- **Admin UI de productos (Change 22)**: los endpoints existen en este change; la UI de gestión en el panel admin se habilita en Change 22.
- **Restauración de producto eliminado**: no existe endpoint de undelete.
- **Búsqueda avanzada / facetas**: básica `search` ILIKE se incluye; facetas y filtros ricos son Change 12.
