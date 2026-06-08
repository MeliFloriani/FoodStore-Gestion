## Why

Los clientes necesitan gestionar múltiples direcciones de entrega en su perfil para poder seleccionarlas al realizar un pedido. Actualmente no existe el módulo `direcciones` en el backend ni la página `/addresses` en el frontend, lo que bloquea el flujo de creación de pedidos con entrega a domicilio (Change 17 depende de este change).

## What Changes

- **Backend — archivos nuevos en estructura Layer-First** (`backend/app/models/direccion_entrega.py`, `backend/app/schemas/direccion_entrega.py`, `backend/app/repositories/direccion_entrega.py`, `backend/app/services/direccion_entrega.py`, `backend/app/api/v1/direcciones.py`): CRUD completo para la entidad `DireccionEntrega` con validación de ownership por `usuario_id` del JWT. Incluye modelo SQLModel, schemas Pydantic v2, repositorio, servicio (lógica de principal + auto-promote + rate-limit de 20 por usuario) y router registrado bajo `/api/v1/direcciones`.
- **Backend — migración Alembic nueva**: crea la tabla `direccion_entrega` con todos sus campos, índice parcial único para garantizar una sola dirección principal por usuario, e índice sobre `usuario_id` para performance.
- **Backend — registro del router**: agrega el router de direcciones al archivo `app/api/v1/router.py` (o equivalente) bajo el prefijo `/api/v1/direcciones`.
- **Frontend — entity FSD nueva `entities/direccion-entrega/`**: tipos TypeScript, funciones de API client y hooks TanStack Query (queries + mutations).
- **Frontend — página nueva `pages/addresses/`**: lista de direcciones, formulario crear/editar, acción marcar principal, eliminación con confirmación y estado vacío (sin dirección = retiro en local).
- **Frontend — routing (delta)**: agrega ruta protegida `/addresses` con guard `require_role("CLIENT")`.
- **Endpoint dedicado `PATCH /api/v1/direcciones/{id}/principal`**: marca la dirección como principal dentro de una transacción atómica (UoW) que desactiva la principal anterior.

## Capabilities

### New Capabilities

- `backend-direcciones-management`: módulo backend completo (model, schemas, repository, service, router) para CRUD de `DireccionEntrega` con lógica de `es_principal`, ownership y soft-delete.
- `frontend-direcciones-entity`: entity FSD con tipos TypeScript, API client functions y hooks TanStack Query para CRUD de direcciones.
- `frontend-direcciones-page`: página `/addresses` con lista, formularios y acciones de gestión de direcciones (FSD layer `pages/`).

### Modified Capabilities

- `backend-api-v1-router`: registrar el router de direcciones bajo el prefijo `/api/v1/direcciones`.
- `backend-migrations`: nueva migración Alembic para crear la tabla `direccion_entrega` con índices y constraints.
- `frontend-routing`: agregar la ruta protegida `/addresses` al árbol de rutas del frontend.

## Impact

- **Código afectado**: archivos backend en estructura layer-first: `backend/app/models/direccion_entrega.py`, `backend/app/schemas/direccion_entrega.py`, `backend/app/repositories/direccion_entrega.py`, `backend/app/services/direccion_entrega.py`, `backend/app/api/v1/direcciones.py` — siguiendo el patrón Layer-First establecido por los Changes anteriores (categorías, ingredientes, productos, perfil). El path `app/modules/` mencionado en algunos artifacts es la nomenclatura Feature-First del scaffold inicial de CLAUDE.md, pero el proyecto real usa Layer-First. El executor SHALL adaptar los paths al patrón Layer-First del proyecto real. Nuevo archivo de migración `backend/alembic/versions/`; modificación de `backend/app/api/v1/router.py`; nuevas carpetas `frontend/src/entities/direccion-entrega/` y `frontend/src/pages/addresses/`; modificación de `frontend/src/app/router.tsx` (o equivalente de routing).
- **APIs**: 6 endpoints nuevos bajo `/api/v1/direcciones` (ver API Contract en design.md).
- **Dependencias upstream**: Change 07 (`auth-refresh-logout-rbac-me`) provee `get_current_user` y `require_role` — deben estar archivados antes del apply.
- **Dependencias downstream**: Change 17 (`order-creation-with-snapshots`) consumirá `DireccionEntrega.id` como FK opcional (`direccion_id NULLABLE`) en el modelo `Pedido`. Este change NO toca el modelo `Pedido`.
- **Base de datos**: nueva tabla `direccion_entrega` con soft-delete (`deleted_at`), índice parcial único sobre `(usuario_id) WHERE es_principal AND deleted_at IS NULL`, e índice estándar sobre `usuario_id`.
