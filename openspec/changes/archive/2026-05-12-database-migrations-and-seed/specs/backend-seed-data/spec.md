# backend-seed-data Specification

## Purpose
Idempotent seed script that loads required static catalog data (EstadoPedido, FormaPago, Rol) and the admin user. The system CANNOT function without these records. Introduced in Change 03 (database-migrations-and-seed).

## ADDED Requirements

### Requirement: Script de seed invocable como módulo Python
El sistema SHALL proveer `backend/app/db/seed.py` invocable con `python -m app.db.seed` que cargue todos los datos de catálogo obligatorios y el usuario administrador.

#### Scenario: seed ejecuta sin errores en BD con schema creado
- **WHEN** se ejecuta `python -m app.db.seed` con `alembic upgrade head` ya aplicado
- **THEN** el script completa sin lanzar excepciones
- **THEN** se imprimen mensajes de progreso indicando los registros insertados/existentes

#### Scenario: seed falla con error claro si la BD no tiene el schema
- **WHEN** se ejecuta `python -m app.db.seed` en una BD vacía sin migraciones
- **THEN** el script lanza un error claro indicando que las tablas no existen
- **THEN** el error sugiere ejecutar `alembic upgrade head` primero

---

### Requirement: Seed de EstadoPedido — 6 estados con es_terminal correcto
El sistema SHALL insertar exactamente 6 registros en `estado_pedido` con los códigos y flags definidos en la FSM del Integrador v5.0.

#### Scenario: 6 estados con es_terminal correcto
- **WHEN** se ejecuta el seed en una BD vacía (post-migration)
- **THEN** existen exactamente 6 filas en `estado_pedido`
- **THEN** `PENDIENTE`: `es_terminal=False`, `orden=1`
- **THEN** `CONFIRMADO`: `es_terminal=False`, `orden=2`
- **THEN** `EN_PREP`: `es_terminal=False`, `orden=3`
- **THEN** `EN_CAMINO`: `es_terminal=False`, `orden=4`
- **THEN** `ENTREGADO`: `es_terminal=True`, `orden=5`
- **THEN** `CANCELADO`: `es_terminal=True`, `orden=6`

#### Scenario: seed de EstadoPedido es idempotente
- **WHEN** se ejecuta `python -m app.db.seed` dos veces consecutivas
- **THEN** `estado_pedido` sigue teniendo exactamente 6 filas (no hay duplicados)
- **THEN** la segunda ejecución no lanza excepciones

---

### Requirement: Seed de FormaPago — 3 formas habilitadas
El sistema SHALL insertar exactamente 3 registros en `forma_pago` con los códigos semánticos del Integrador v5.0.

#### Scenario: 3 formas de pago habilitadas
- **WHEN** se ejecuta el seed
- **THEN** existen exactamente 3 filas en `forma_pago`
- **THEN** `MERCADOPAGO`: `habilitado=True`
- **THEN** `EFECTIVO`: `habilitado=True`
- **THEN** `TRANSFERENCIA`: `habilitado=True`

#### Scenario: seed de FormaPago es idempotente
- **WHEN** se ejecuta el seed múltiples veces
- **THEN** `forma_pago` sigue teniendo exactamente 3 filas

---

### Requirement: Seed de Rol — 4 roles RBAC
El sistema SHALL insertar exactamente 4 registros en `rol` con los códigos semánticos del sistema RBAC.

#### Scenario: 4 roles con códigos RBAC
- **WHEN** se ejecuta el seed
- **THEN** existen exactamente 4 filas en `rol`
- **THEN** los códigos `ADMIN`, `STOCK`, `PEDIDOS`, `CLIENT` están presentes
- **THEN** cada rol tiene `nombre` descriptivo en español

#### Scenario: seed de Rol es idempotente
- **WHEN** se ejecuta el seed múltiples veces
- **THEN** `rol` sigue teniendo exactamente 4 filas

---

### Requirement: Seed del usuario administrador con bcrypt cost≥12
El sistema SHALL insertar un usuario administrador con email `admin@foodstore.com` (o configurable via `ADMIN_EMAIL`), contraseña `Admin1234!` hasheada con bcrypt (cost≥12) y rol `ADMIN` asignado.

#### Scenario: admin creado con hash bcrypt y rol ADMIN asignado
- **WHEN** se ejecuta el seed
- **THEN** existe exactamente 1 usuario con `email = 'admin@foodstore.com'` (o el valor de `ADMIN_EMAIL`)
- **THEN** `password_hash` tiene formato bcrypt (`$2b$12$...`), no contiene la contraseña en claro
- **THEN** el usuario tiene el rol `ADMIN` asignado en `usuario_rol` con `asignado_por_id=NULL`
- **NOTA crítica**: `asignado_por_id=NULL` es el valor correcto para bootstrap system-generated. No usar auto-asignación artificial (`asignado_por_id=admin.id` — el admin no se autoasignó, el sistema lo creó). No crear un "system user" sintético solo para satisfacer la FK. La columna es nullable precisamente para este escenario.

#### Scenario: contraseña es verificable con passlib
- **WHEN** se llama `CryptContext.verify("Admin1234!", usuario.password_hash)`
- **THEN** retorna `True`
- **WHEN** se llama `CryptContext.verify("OtraContrasena", usuario.password_hash)`
- **THEN** retorna `False`

#### Scenario: seed del admin es idempotente
- **WHEN** se ejecuta el seed dos veces
- **THEN** existe exactamente 1 usuario admin (no duplicado)
- **THEN** la asignación de rol `ADMIN` no se duplica en `usuario_rol`

#### Scenario: warning si se usa contraseña default
- **WHEN** `ADMIN_PASSWORD` no está configurada en el entorno y se usa el valor default `Admin1234!`
- **THEN** el script imprime un WARNING indicando que la contraseña default debe cambiarse en producción

---

### Requirement: Seed usa INSERT ... ON CONFLICT DO NOTHING para idempotencia
El sistema SHALL implementar la idempotencia del seed mediante `INSERT ... ON CONFLICT DO NOTHING` sobre la clave natural de cada entidad de catálogo.

#### Scenario: ON CONFLICT DO NOTHING en estado_pedido por codigo
- **WHEN** ya existe un `EstadoPedido` con `codigo='PENDIENTE'` y se ejecuta el seed de nuevo
- **THEN** no se lanza excepción de `UniqueViolation`
- **THEN** el registro existente no es modificado

#### Scenario: ON CONFLICT DO NOTHING en usuario por email
- **WHEN** ya existe un `Usuario` con `email='admin@foodstore.com'` y se ejecuta el seed
- **THEN** no se crea un segundo usuario admin
- **THEN** no se lanza excepción
