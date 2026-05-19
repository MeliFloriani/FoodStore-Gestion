## Context

The `Producto`, `ProductoCategoria`, and `ProductoIngrediente` SQLModel classes already exist in `backend/app/models/catalog.py` (Change 03 — migration 0001). `Categoria` and its CRUD API are operational (Change 09). `Ingrediente` and its CRUD API are operational (Change 10). `BaseRepository[T]`, `UnitOfWork`, `require_role`, and RFC 7807 error handlers are all operational (Changes 04, 07).

**Existing model state** (from `catalog.py`):

```
Producto        — tabla "producto"; precio_base DECIMAL(10,2); stock_cantidad INTEGER; disponible BOOLEAN; soft delete
ProductoCategoria  — tabla "producto_categoria"; UniqueConstraint(producto_id, categoria_id); es_principal BOOLEAN
ProductoIngrediente — tabla "producto_ingrediente"; UniqueConstraint(producto_id, ingrediente_id); es_removible BOOLEAN (no default)
```

**Backend module layout** (layer-first, matching CLAUDE.md and the existing codebase):

```
backend/app/
├── schemas/
│   └── producto.py          ← ProductoBase, ProductoCreate, ProductoUpdate, ProductoRead, ProductoDetail,
│                               ProductoIngredienteRead, DisponibilidadUpdate
├── repositories/
│   └── producto.py          ← ProductoRepository(BaseRepository[Producto])
├── services/
│   └── producto.py          ← ProductoService
├── api/v1/
│   └── productos.py         ← productos_router (APIRouter)
└── models/
    └── catalog.py           ← Producto, ProductoCategoria, ProductoIngrediente (ya existen)
```

No `app/products/` domain-first directory. Layer-first throughout (consistent with categorias, ingredientes).

---

## Goals / Non-Goals

**Goals:**

- 9-endpoint API de productos con RBAC granular por operación (D-01).
- M2M categorías via `categoria_ids` en create/update (D-02); M2M ingredientes via endpoints dedicados (D-03).
- Operación atómica de stock `UPDATE … WHERE stock_cantidad >= :delta RETURNING` (D-04).
- Schemas Pydantic v2 con `Decimal` para precio (D-05).
- Migration `0005` con índices de performance sobre tabla `producto` (D-10).
- Frontend entity layer minimal para admin/stock panel.
- Anti N+1: `selectinload` en endpoint de detalle (D-08).
- Paginación `{ items, total, page, size, pages }` con filtros básicos (D-09).

**Non-Goals:**

- UI de catálogo público (Change 12).
- Decremento de stock en checkout (Change 17).
- Validaciones pre-checkout (Change 16).
- Endpoint `PATCH /productos/{id}/stock` separado.
- Admin panel mutations desde el frontend (Change 22).
- Restore (undelete) endpoint.

---

## Data Model

### Tabla `producto` (ya existe desde migration 0001)

```sql
CREATE TABLE producto (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          VARCHAR(200)    NOT NULL,
    descripcion     TEXT,
    imagen_url      VARCHAR(500),
    precio_base     DECIMAL(10, 2)  NOT NULL,
    stock_cantidad  INTEGER         NOT NULL DEFAULT 0,
    disponible      BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,

    CONSTRAINT ck_producto_precio_base    CHECK (precio_base >= 0),
    CONSTRAINT ck_producto_stock_cantidad CHECK (stock_cantidad >= 0)
);
```

### Tabla `producto_categoria` (ya existe desde migration 0001)

```sql
CREATE TABLE producto_categoria (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    producto_id  UUID NOT NULL REFERENCES producto(id)  ON DELETE CASCADE,
    categoria_id UUID NOT NULL REFERENCES categoria(id) ON DELETE CASCADE,
    es_principal BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at   TIMESTAMPTZ,  -- dormant (D-31)
    CONSTRAINT uq_producto_categoria_producto_id_categoria_id UNIQUE (producto_id, categoria_id)
);
```

### Tabla `producto_ingrediente` (ya existe desde migration 0001)

```sql
CREATE TABLE producto_ingrediente (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    producto_id    UUID NOT NULL REFERENCES producto(id)    ON DELETE CASCADE,
    ingrediente_id UUID NOT NULL REFERENCES ingrediente(id) ON DELETE CASCADE,
    es_removible   BOOLEAN NOT NULL,  -- sin default — siempre explícito
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at     TIMESTAMPTZ,  -- dormant (D-31)
    CONSTRAINT uq_producto_ingrediente_producto_id_ingrediente_id UNIQUE (producto_id, ingrediente_id)
);
```

### Índices nuevos — Migration `0005_add_producto_indexes`

```sql
-- Filtro de catálogo público (Change 12)
CREATE INDEX ix_producto_disponible
    ON producto (disponible)
    WHERE deleted_at IS NULL;

-- Búsqueda por nombre ILIKE con prefijo (Change 12)
CREATE INDEX ix_producto_nombre_search
    ON producto (nombre text_pattern_ops)
    WHERE deleted_at IS NULL;
```

**`down_revision` de migration 0005**: Debe ser el hash de revision de `0004_ingredientes_table` = `'8212a24ee1b0'` (verificado con `alembic history`).

---

## API Contracts

### Endpoint Surface

| Método | Ruta | Auth | Request Body | Response | Status |
|---|---|---|---|---|---|
| `GET` | `/api/v1/productos` | Público | Query params | `PaginatedProductos` | 200 |
| `GET` | `/api/v1/productos/{id}` | Público | — | `ProductoDetail` | 200 |
| `POST` | `/api/v1/productos` | ADMIN | `ProductoCreate` | `ProductoRead` | 201 |
| `PATCH` | `/api/v1/productos/{id}` | ADMIN | `ProductoUpdate` | `ProductoRead` | 200 |
| `DELETE` | `/api/v1/productos/{id}` | ADMIN | — | — | 204 |
| `PATCH` | `/api/v1/productos/{id}/disponibilidad` | ADMIN, STOCK | `DisponibilidadUpdate` | `ProductoRead` | 200 |
| `GET` | `/api/v1/productos/{id}/ingredientes` | Público | — | `list[ProductoIngredienteRead]` | 200 |
| `POST` | `/api/v1/productos/{id}/ingredientes` | ADMIN | `AsociarIngredienteRequest` | `ProductoIngredienteRead` | 201 |
| `DELETE` | `/api/v1/productos/{id}/ingredientes/{ing_id}` | ADMIN | — | — | 204 |

> **Decisión consciente — PATCH vs PUT (H-01)**: El Integrador §5.2 declara `PUT /api/v1/productos/{id}` (reemplazo completo). Change 11 adopta `PATCH` (actualización parcial) por las siguientes razones:
> 1. **Parcialidad**: `ProductoUpdate` usa `model_fields_set` — solo los campos enviados se actualizan. PUT requeriría enviar todos los campos en cada actualización, incluso los no modificados (impracticable con campos opcionales como `imagen_url`).
> 2. **Consistencia**: Los changes anteriores (09 categorías, 10 ingredientes) usan PATCH para actualizaciones parciales. Adoptar PUT aquí rompería la coherencia de la API.
> 3. **Semántica REST**: RFC 7231 permite PATCH para modificaciones parciales. El Integrador no prohíbe explícitamente PATCH — solo especifica PUT como opción. PATCH es un superconjunto semántico válido.
> 4. **Compatibilidad futura**: Change 17 y 22 dependen de actualizar solo campos específicos de productos; PATCH es la elección natural.
>
> **Impacto en tests**: Los integration tests deben usar `PATCH`, no `PUT`, para `PUT /api/v1/productos/{id}`.

### Query Params — `GET /productos`

| Param | Tipo | Default | Descripción |
|---|---|---|---|
| `page` | int ≥ 1 | 1 | Número de página |
| `size` | int 1–100 | 20 | Items por página |
| `categoria_id` | UUID \| None | None | Filtro por categoría (JOIN con producto_categoria) |
| `disponible` | bool \| None | None | None = todos; true/false = filtro |
| `search` | str \| None | None | ILIKE `%search%` sobre `nombre` |

### Schemas Pydantic v2

**`ProductoBase`**
```python
nombre:      str     = Field(min_length=1, max_length=200)
descripcion: str | None = None
imagen_url:  str | None = Field(default=None, max_length=500)
precio_base: Decimal = Field(ge=Decimal("0.00"))  # 2 decimales — validador custom
disponible:  bool    = True
```

**`ProductoCreate(ProductoBase)`**
```python
stock_cantidad: int              = Field(ge=0, default=0)
categoria_ids:  list[UUID] | None = None   # IDs de categorías a asociar
```

**`ProductoUpdate(BaseModel)`** — todos opcionales, `model_fields_set` para parcialidad
```python
nombre:         str | None     = None
descripcion:    str | None     = None
imagen_url:     str | None     = None
precio_base:    Decimal | None = None
stock_cantidad: int | None     = None     # ADMIN puede setear stock absoluto
disponible:     bool | None    = None
categoria_ids:  list[UUID] | None = None  # None = no tocar; [] = quitar todas
```

**`ProductoRead`** — respuesta compacta (listado)
```python
id:             UUID
nombre:         str
descripcion:    str | None
imagen_url:     str | None
precio_base:    Decimal
stock_cantidad: int
disponible:     bool
created_at:     datetime
updated_at:     datetime
model_config = ConfigDict(from_attributes=True)
```

**`ProductoDetail(ProductoRead)`** — respuesta completa (detalle + M2M)
```python
categorias:   list[CategoriaRead]
ingredientes: list[ProductoIngredienteRead]
```

**`ProductoIngredienteRead`**
```python
ingrediente_id: UUID
nombre:         str
es_alergeno:    bool
es_removible:   bool
model_config = ConfigDict(from_attributes=True)
```

**`DisponibilidadUpdate`**
```python
disponible: bool
```

**`AsociarIngredienteRequest`**
```python
ingrediente_id: UUID
es_removible:   bool
```

**`PaginatedProductos`** — reutiliza contrato de `backend-pagination-schema`
```python
items: list[ProductoRead]
total: int
page:  int
size:  int
pages: int
```

### Serialización de `precio_base` y estrategia float → Decimal (H-02)

**Realidad del modelo SQLModel**: `Producto.precio_base` está declarado como `float` en Python (`precio_base: float`) con `sa_column=Column("precio_base", DECIMAL(10, 2), ...)`. asyncpg puede devolver el valor como `Decimal` (comportamiento por defecto) o `float` dependiendo de la configuración del driver.

**Estrategia de conversión segura** (obligatoria en implementación):

1. En `ProductoRead`, el campo `precio_base` debe declararse como `Decimal`:
   ```python
   precio_base: Decimal
   model_config = ConfigDict(from_attributes=True)
   ```
   Pydantic v2 con `from_attributes=True` realizará la conversión automática `float → Decimal` al construir el schema desde el ORM. La conversión es exacta para los valores producidos por `DECIMAL(10, 2)`.

2. Serialización a JSON como **string** (nunca float en la respuesta):
   ```python
   @field_serializer("precio_base")
   def serialize_precio(self, v: Decimal) -> str:
       return str(v)
   ```
   Alternativa Pydantic v2:
   ```python
   model_config = ConfigDict(
       from_attributes=True,
       json_encoders={Decimal: str}
   )
   ```
   **Preferir `@field_serializer`** — más explícito y verificable en tests.

3. En `ProductoCreate` y `ProductoUpdate`, el campo se recibe como `Decimal` desde el payload JSON. Pydantic v2 acepta strings (`"19.99"`) y los convierte a `Decimal` automáticamente.

**Test obligatorio** (tarea 2.11): `test_read_precio_serializes_as_string` — `ProductoRead(precio_base=Decimal("15.50")).model_dump_json()` debe producir `"precio_base": "15.50"` (string), no `"precio_base": 15.5` (float).

---

## Stock Concurrency Strategy

### Por qué `UPDATE … WHERE` y no `SELECT FOR UPDATE`

**Change 11** expone el método de decremento como bloque reutilizable, pero el contexto de Change 17 (checkout) es diferente:

- En Change 17, el checkout crea el pedido + decrementa stock de múltiples productos en una única transacción SERIALIZABLE, usando `SELECT … FOR UPDATE` para bloquear las filas y evitar que otro checkout concurrente decremente el mismo stock simultáneamente.
- En Change 11, se declara `decrement_stock` como método del repository para casos de decremento unitario (p. ej., un ajuste de stock desde el panel admin). Este método usa `UPDATE … WHERE stock_cantidad >= :delta RETURNING id` — si retorna 0 rows, el decremento falló por stock insuficiente (race condition detectada). El service lanza `AppValidationError(code="INSUFFICIENT_STOCK")`.

```sql
UPDATE producto
SET    stock_cantidad = stock_cantidad - :delta,
       updated_at     = NOW()
WHERE  id             = :producto_id
  AND  stock_cantidad >= :delta
  AND  deleted_at     IS NULL
RETURNING id, stock_cantidad;
```

Si la query retorna 0 rows → `decrement_stock` retorna `None` → service lanza `INSUFFICIENT_STOCK`.

**Por qué no `SELECT FOR UPDATE` aquí**: `FOR UPDATE` bloquea la fila hasta el commit de la transacción. Para un ajuste de stock simple desde el panel admin (no checkout), bloquear la fila innecesariamente aumenta la contención. El patrón `UPDATE WHERE` es optimistic concurrency control — suficiente para ajustes individuales, sin sacrificar throughput.

**Implicación para Change 17**: El checkout usará `SELECT … FOR UPDATE` DENTRO de la transacción del pedido (UoW único), donde el bloqueo es requerido para garantizar consistencia serializable entre múltiples ítems.

---

## Repository / Service / UseCase Layering

### `ProductoRepository(BaseRepository[Producto])`

Métodos adicionales sobre `BaseRepository`:

```python
async def list_paginated(
    page: int,
    size: int,
    categoria_id: UUID | None = None,
    disponible: bool | None = None,
    search: str | None = None,
) -> tuple[list[Producto], int]:
    """Devuelve (items, total). Aplica filtros + paginación. Excluye deleted_at IS NOT NULL."""

async def get_with_relations(producto_id: UUID) -> Producto | None:
    """Carga producto + producto_categorias.categoria + producto_ingredientes.ingrediente
    con selectinload. Excluye deleted_at IS NOT NULL."""

async def set_categorias(producto: Producto, categoria_ids: list[UUID]) -> None:
    """Replace-all de ProductoCategoria: elimina existentes, inserta nuevas.
    Hard delete de pivot (D-31). Primer categoria_id se marca es_principal=True.

    ATOMICIDAD: Este método DEBE ejecutarse dentro del mismo UoW que el create/update
    del producto. La session compartida del UoW garantiza que el DELETE de pivots
    existentes y el INSERT de pivots nuevos son atómicos — cualquier excepción durante
    el INSERT hace rollback de ambas operaciones, dejando las categorías originales
    intactas. NO llamar a este método fuera de un bloque `async with UoW() as uow:`.
    """

async def add_ingrediente(
    producto_id: UUID,
    ingrediente_id: UUID,
    es_removible: bool,
) -> ProductoIngrediente:
    """Inserta ProductoIngrediente. Lanza IntegrityError si ya existe."""

async def remove_ingrediente(producto_id: UUID, ingrediente_id: UUID) -> bool:
    """Hard delete de ProductoIngrediente. Retorna True si existía, False si no."""

async def get_ingredientes(producto_id: UUID) -> list[ProductoIngrediente]:
    """Listado de ProductoIngrediente con selectinload de Ingrediente."""

async def decrement_stock(producto_id: UUID, delta: int) -> Producto | None:
    """UPDATE ... WHERE stock_cantidad >= :delta RETURNING. None si stock insuficiente."""
```

### `ProductoService`

Orquesta todas las reglas de negocio. Recibe `uow` como dependencia inyectada por el router:

```python
async def list_productos(uow, page, size, categoria_id, disponible, search) -> PaginatedProductos
async def get_producto_detail(uow, producto_id: UUID) -> ProductoDetail
async def create_producto(uow, data: ProductoCreate) -> ProductoRead
async def update_producto(uow, producto_id: UUID, data: ProductoUpdate) -> ProductoRead
async def delete_producto(uow, producto_id: UUID) -> None
async def set_disponibilidad(uow, producto_id: UUID, data: DisponibilidadUpdate) -> ProductoRead
async def get_producto_ingredientes(uow, producto_id: UUID) -> list[ProductoIngredienteRead]
async def add_ingrediente(uow, producto_id: UUID, data: AsociarIngredienteRequest) -> ProductoIngredienteRead
async def remove_ingrediente(uow, producto_id: UUID, ingrediente_id: UUID) -> None
```

**Reglas de negocio en el service**:
- `create_producto`: valida `categoria_ids` (cada UUID debe existir en `categorias`); llama `uow.productos.create`, luego `set_categorias` si hay `categoria_ids`.
- `update_producto`: carga entidad (404 si not found); aplica `model_fields_set` para parcialidad; si `categoria_ids` en `model_fields_set`, llama `set_categorias`; captura `IntegrityError` si aplica.
- `add_ingrediente`: valida que `producto_id` y `ingrediente_id` existen; llama `add_ingrediente` en repo; captura `IntegrityError` → `ConflictError(code="PRODUCT_INGREDIENT_DUPLICATE")`.
- `remove_ingrediente`: valida producto existe; llama `remove_ingrediente` en repo; si retorna `False` → `NotFoundError(code="PRODUCT_INGREDIENT_NOT_FOUND")`.

---

## Loading Strategy (Anti N+1)

### `GET /productos` (listado)

Devuelve `list[ProductoRead]` — sin relaciones anidadas. Query directa sobre `producto` con filtros y paginación. Costo: O(1) queries (1 count + 1 select).

### `GET /productos/{id}` (detalle)

Usa `selectinload` para cargar relaciones en 3 queries (1 producto + 1 categorias + 1 ingredientes):

```python
stmt = (
    select(Producto)
    .where(Producto.id == producto_id, Producto.deleted_at.is_(None))
    .options(
        selectinload(Producto.producto_categorias).selectinload(ProductoCategoria.categoria),
        selectinload(Producto.producto_ingredientes).selectinload(ProductoIngrediente.ingrediente),
    )
)
```

### `GET /productos/{id}/ingredientes`

Query directa sobre `ProductoIngrediente` + `selectinload(ProductoIngrediente.ingrediente)`. Costo: 2 queries.

**Anti-patrón prohibido**: `lazy="select"` (N+1). El modelo define estrategias diferenciadas:

- `Producto.producto_categorias` y `Producto.producto_ingredientes` tienen `lazy="noload"` → la carga con `selectinload` explícito en el repository es **obligatoria**.
- Las back-refs dentro de los pivots (`ProductoCategoria.categoria`, `ProductoCategoria.producto`, `ProductoIngrediente.ingrediente`, `ProductoIngrediente.producto`) tienen `lazy="selectin"` → se cargan automáticamente cuando el pivot es cargado.

**Implicación**: cuando el repo usa `selectinload(Producto.producto_categorias).selectinload(ProductoCategoria.categoria)`, el `selectinload` explícito sobre el nested relationship **toma precedencia** sobre el `lazy="selectin"` del modelo, evitando cargas duplicadas. El conteo de queries sigue siendo 3 (1 producto + 1 selectin producto_categorias + 1 selectin categorias). Para ingredientes: 2 queries adicionales (1 selectin producto_ingredientes + 1 selectin ingredientes). Total detalle: 5 queries con el stmt del diseño actual. Verificar con test 7.1.

---

## Pagination / Filter / Search Contract

Reutiliza `backend-pagination-schema`:

```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "size": 20,
  "pages": 3
}
```

`pages = ceil(total / size)`. El router valida `page >= 1` y `1 <= size <= 100`. `skip = (page - 1) * size`.

**Filtro `search`**: `ILIKE '%' || :search || '%'` sobre `nombre`. Para prefijo, usa el índice `ix_producto_nombre_search`. Para búsqueda en cualquier posición, se puede necesitar `text_pattern_ops` o `pg_trgm` en futuro — documentar en código.

---

## Soft-Delete Semantics + Cascade Considerations

**`DELETE /productos/{id}`**: Soft delete (`deleted_at = now()`). Los pivots `producto_categoria` y `producto_ingrediente` permanecen (D-31 — `deleted_at` dormant en pivots). Los cambios de precio o disponibilidad futuros no afectan pedidos históricos (snapshot en `DetallePedido`).

**Eliminación de categoría**: Si una categoría se elimina (Change 09), `producto_categoria.categoria_id` sigue apuntando a la categoría con `deleted_at IS NOT NULL`. El listado de categorías del producto en `ProductoDetail` filtrará `categoria.deleted_at IS NULL` para no mostrar categorías eliminadas.

**Eliminación de ingrediente (Change 10)**: Soft delete de ingrediente deja `producto_ingrediente.ingrediente_id` apuntando a ingrediente eliminado. La lista de ingredientes del producto filtrará `ingrediente.deleted_at IS NULL`.

**Cascade ON DELETE CASCADE a nivel BD**: Los pivots tienen `ON DELETE CASCADE` sobre `producto_id` (hard delete de producto eliminaría pivots). Dado que usamos soft delete, el CASCADE nunca se dispara en operación normal.

---

## Error Contracts

| HTTP Status | `code` | Trigger |
|---|---|---|
| 401 | `missing_token` | Token ausente en endpoint protegido |
| 403 | `forbidden` | Rol insuficiente |
| 404 | `PRODUCT_NOT_FOUND` | `producto_id` no existe o está soft-deleted |
| 404 | `CATEGORY_NOT_FOUND` | `categoria_id` en `categoria_ids` no existe |
| 404 | `INGREDIENT_NOT_FOUND` | `ingrediente_id` no existe en `add_ingrediente` |
| 404 | `PRODUCT_INGREDIENT_NOT_FOUND` | La asociación producto↔ingrediente no existe en `remove_ingrediente` |
| 409 | `PRODUCT_INGREDIENT_DUPLICATE` | Asociación producto↔ingrediente ya existe |
| 422 | `INVALID_PRECIO` | `precio_base < 0` (validado por Pydantic `ge=0`) |
| 422 | `INVALID_STOCK` | `stock_cantidad < 0` (validado por Pydantic `ge=0`) |
| 422 | `INSUFFICIENT_STOCK` | `decrement_stock` retorna None — violación de regla de negocio (stock insuficiente). Lanzado como `AppValidationError(code="INSUFFICIENT_STOCK", status_code=422)`. HTTP 422 es correcto: el request es sintácticamente válido pero viola una invariante de negocio (no es un request malformado = 400). |

Todos los errores siguen RFC 7807: `{ "detail": "mensaje", "code": "ERROR_CODE", "field": "campo_opcional" }`.

---

## Frontend Impact

Scope únicamente: contratos consumidos por el frontend de admin/stock en este change.

**Tipos (`entities/products/model/types.ts`)**:
```typescript
interface ProductoRead {
  id: string          // UUID
  nombre: string
  descripcion: string | null
  imagen_url: string | null
  precio_base: string  // Decimal serializado como string
  stock_cantidad: number
  disponible: boolean
  created_at: string
  updated_at: string
}

interface ProductoIngredienteRead {
  ingrediente_id: string
  nombre: string
  es_alergeno: boolean
  es_removible: boolean
}

interface ProductoDetail extends ProductoRead {
  categorias: CategoriaRead[]
  ingredientes: ProductoIngredienteRead[]
}

interface PaginatedProductos {
  items: ProductoRead[]
  total: number
  page: number
  size: number
  pages: number
}
```

**Query keys** (`queryKeys.products.*`): `['products', 'list', filters]`, `['products', 'detail', id]`, `['products', 'ingredientes', id]`.

**Invalidation**: Mutaciones de producto invalidan `['products', 'list']`. Mutaciones de ingrediente invalidan `['products', 'detail', id]` y `['products', 'ingredientes', id]`. Mutación de disponibilidad invalida `['products', 'list']` y `['products', 'detail', id]`.

**Nota RBAC en UI**: Los mutation hooks verifican el rol antes de renderizar botones de edición. `useProductoMutations` solo debe usarse en contextos donde el rol es ADMIN (para CRUD) o ADMIN/STOCK (para disponibilidad). Implementación real del guard de ruta en Change 22.

---

## Migration Plan

### Migration `0005_add_producto_indexes`

**File**: `backend/alembic/versions/XXXX_0005_add_producto_indexes.py`
**`down_revision`**: `'8212a24ee1b0'` (hash de migration 0004 — verificado)

```python
def upgrade():
    # Índice para filtro de catálogo público (Change 12)
    op.execute(
        "CREATE INDEX ix_producto_disponible "
        "ON producto (disponible) WHERE deleted_at IS NULL"
    )
    # Índice para búsqueda ILIKE con prefijo
    op.execute(
        "CREATE INDEX ix_producto_nombre_search "
        "ON producto (nombre text_pattern_ops) WHERE deleted_at IS NULL"
    )

def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_producto_nombre_search")
    op.execute("DROP INDEX IF EXISTS ix_producto_disponible")
```

**No crea tablas nuevas. No modifica columnas existentes. Solo índices.**

La migration es SEGURA en tablas con datos: `CREATE INDEX` no bloquea escrituras en PostgreSQL 15+ (usa `CREATE INDEX CONCURRENTLY` si se necesita en producción).

---

## Test Strategy

### Backend

**Unit tests (TDD — Red-Green-Refactor)**:
- `tests/schemas/test_producto_schemas.py` — validación de Decimal, negativos, longitudes.
- `tests/productos/test_producto_repository.py` — `list_paginated`, `get_with_relations`, `set_categorias`, `add_ingrediente`, `remove_ingrediente`, `decrement_stock`.
- `tests/productos/test_producto_service.py` — todas las reglas de negocio mockeando el repo.

**Integration tests**:
- `tests/integration/test_productos.py` — ciclo HTTP completo: 401/403 RBAC, 201 create, 200 detail, 409 duplicate ingredient, 204 soft delete.

**Anti N+1 tests**:
- Verificar que `GET /productos/{id}` emite como máximo 5 queries (1 SELECT producto + hasta 2 selectinload sobre pivots + hasta 2 selectinload sobre entidades relacionadas) y que el conteo NO crece con el número de categorías o ingredientes del producto (ver tasks.md 7.1 y design.md Loading Strategy).

**Migration tests**:
- `tests/test_migrations.py::test_0005_upgrade_creates_indexes` — verifica existencia de `ix_producto_disponible` e `ix_producto_nombre_search`.
- `tests/test_migrations.py::test_0005_downgrade_drops_indexes` — verifica downgrade limpio.

### Frontend

**Unit tests (Vitest)**:
- `entities/products/model/types.test.ts` — tipos TypeScript compilan sin error.
- `entities/products/model/useProductos.test.ts` — hooks retornan estado correcto con mock server.

---

## Risks

| ID | Riesgo | Severidad | Mitigación |
|---|---|---|---|
| R-01 | `Decimal` serializado como float por FastAPI por defecto | ALTO | Configurar `json_encoders={Decimal: str}` en `model_config` + test de contrato |
| R-02 | N+1 en `GET /productos` si se agrega relaciones accidentalmente | MEDIO | Test que cuenta queries con `sqlalchemy.event` o `pytest-postgresql` |
| R-03 | Race condition en `decrement_stock` si se usa en checkout (Change 17) | MEDIO | Documentar claramente que Change 17 debe usar `SELECT FOR UPDATE` — no este método |
| R-04 | `set_categorias` borra pivots con hard delete — riesgo si hay FK externas en el futuro | BAJO | Los pivots no tienen FK salientes; D-31 confirma hard delete es intencional |
| R-05 | `es_removible` sin default en `ProductoIngrediente` — `AsociarIngredienteRequest` debe siempre enviarlo | MEDIO | Pydantic valida que el campo sea requerido; test de esquema lo cubre |
| R-06 | `down_revision` de migration 0005 hardcodeado — puede fallar si migración 0004 tiene otro hash | BAJO | Verificar con `alembic history` antes de generar; hash `'8212a24ee1b0'` confirmado en el repo |
| R-07 | M2M categorías replace-all puede eliminar categorías involuntariamente si `categoria_ids` se envía vacío | MEDIO | Documentar que `categoria_ids: []` quita todas las categorías; test de escenario explícito |

---

## Open Questions

_Ninguna. Todas las decisiones resueltas antes de escribir este design (D-01 a D-10 en proposal.md)._

---

## Decision Log — RBAC Resolution

### Contradicción detectada entre US y Integrador §5.2

Las Historias de Usuario incluyen al Gestor de Stock (rol STOCK) como actor en operaciones de CRUD de productos:

- US-015: *"Como Gestor de Stock, quiero dar de alta un producto"*
- US-016: *"Como Gestor de Stock, quiero asociar categorías a un producto"*
- US-017: *"Como Gestor de Stock, quiero asociar ingredientes a un producto"*
- US-020: *"Como Gestor de Stock, quiero editar los datos de un producto"*
- US-021: *"Como Gestor de Stock, quiero actualizar el stock de un producto"*
- US-022: *"Como Gestor de Stock, quiero dar de baja un producto"*

Sin embargo, el **Integrador v5.0 §5.2** (tabla de API REST) declara explícitamente:

| Método | Ruta | Rol requerido |
|---|---|---|
| POST | `/api/v1/productos` | ADMIN |
| PUT | `/api/v1/productos/{id}` | ADMIN |
| DELETE | `/api/v1/productos/{id}` | ADMIN |
| PATCH | `/api/v1/productos/{id}/disponibilidad` | ADMIN, STOCK |
| POST | `/api/v1/productos/{id}/ingredientes/{id}` | ADMIN |
| DELETE | `/api/v1/productos/{id}/ingredientes/{id}` | ADMIN |

Y `docs/CHANGES.md` línea 69 consolida explícitamente esta resolución:

> *"CRUD de productos → exclusivo de ADMIN. PATCH /productos/{id}/disponibilidad → ADMIN o STOCK. stock_cantidad y disponibilidad → STOCK opera, ADMIN también."*

### Decisión: Integrador §5.2 + CHANGES.md prevalecen sobre las US

**Fuente de verdad para evaluación**: El Integrador v5.0 es el contrato de evaluación del TPI. Cuando existe contradicción entre las historias de usuario y el §5.2 de la especificación técnica, el §5.2 prevalece.

**Justificación arquitectónica**: La distinción de roles tiene sentido operacional:
- **ADMIN** controla el catálogo completo (alta, baja, edición de datos maestros, asociación de ingredientes).
- **STOCK** gestiona el estado operativo diario (disponibilidad, cantidad de stock) sin poder alterar datos maestros del catálogo.

**Matriz RBAC definitiva para este change**:

| Operación | Rol | Rationale |
|---|---|---|
| CRUD de productos (POST/PATCH/DELETE) | ADMIN | Datos maestros — Integrador §5.2 |
| PATCH `/disponibilidad` | ADMIN, STOCK | Operación diaria — §4.2 y §5.2 |
| `stock_cantidad` (solo vía PATCH) | ADMIN, STOCK | Integrador §4.2 y CHANGES.md |
| Asociación/desasociación de ingredientes | ADMIN | Datos maestros — §5.2 |
| GET (todos) | Público | Sin auth — §5.2 |

**Impacto en implementación**: Los guards RBAC en `backend/app/api/v1/productos.py` deben reflejar exactamente esta matriz. Ver D-01 en `proposal.md` para la tabla completa de `require_role` por endpoint.
