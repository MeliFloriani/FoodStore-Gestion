## Context

El carrito de FoodStore es completamente client-side (Change 15, archivado 2026-05-20): los items se persisten en localStorage con precios y disponibilidad capturados al momento de agregar al carrito. Al iniciar el checkout, la información del carrito puede estar desactualizada: productos eliminados del catálogo, sin stock suficiente, o con precios modificados por el administrador.

El sistema necesita un punto de validación explícito entre "mostrar carrito" y "crear pedido" (Change 17). Este punto debe consultar el estado actual de la BD, contrastar con lo que el cliente tiene en su carrito, y devolver un reporte detallado que permita a la UI informar al cliente y decidir cómo proceder.

**Estado actual**: Change 11 (`catalog-products-management`, archivado 2026-05-19) provee el modelo `Producto` con `precio_base DECIMAL(10,2)`, `stock_cantidad INTEGER`, `disponible BOOLEAN`, `deleted_at TIMESTAMPTZ`. Change 15 define `CartItem { producto_id: string, nombre: string, precio: number, cantidad: number, personalizacion: string[] }` con identidad compuesta `buildItemKey(producto_id, personalizacion)`.

**Restricción fundamental**: este change NO crea pedidos, NO modifica stock, NO reserva recursos. Es un servicio de consulta stateless que informa al cliente sobre discrepancias.

## Goals / Non-Goals

**Goals:**
- Endpoint `POST /api/v1/pedidos/validar` que valida disponibilidad y precios del carrito sin efectos secundarios.
- Respuesta estructurada `200 OK` con flag `ok`, lista de items validados y lista de cambios detectados (tipos: `PRODUCTO_NO_VIGENTE`, `PRODUCTO_NO_DISPONIBLE`, `STOCK_INSUFICIENTE`, `PRECIO_CAMBIADO`, `PERSONALIZACION_INVALIDA`).
- Frontend: hook `useValidatePreCheckout` + componente `<PreCheckoutReview />` en ruta `/checkout/review`.
- Integración con `cartStore` sin romper su contrato.
- Manejo de errores RFC 7807 estándar.

**Non-Goals:**
- Creación de pedidos (Change 17).
- Reserva o decremento de stock (Change 17).
- Snapshots inmutables de items de pedido (Change 17).
- Caché de resultado de validación (cada llamada es fresca, reflect current DB state).
- Pagos / MercadoPago (Change 19).
- FSM de pedidos (Change 18).
- Endpoints adicionales al único `POST /api/v1/pedidos/validar`.
- Migraciones de BD (no hay cambios de modelo).

## Decisions

### D-01: Endpoint dedicado separado de POST /api/v1/pedidos

**Decisión**: `POST /api/v1/pedidos/validar` es un endpoint independiente, no parte del flujo de creación de pedido.

**Rationale**: Separación clara entre consulta de viabilidad (sin efectos) y creación de orden (con efectos). El frontend puede llamar a la validación varias veces (si el usuario ajusta su carrito y revalida) sin riesgo de crear pedidos duplicados. Permite testear la UI de revisión de forma aislada.

**Alternativa considerada**: Validación implícita dentro de `POST /api/v1/pedidos` con 422 al detectar problemas. Rechazada porque mezcla errores de negocio (stock insuficiente) con errores de protocolo (payload mal formado), y no permite al usuario tomar decisiones antes de intentar crear el pedido.

**NOTA TOCTOU**: La validación de este change es "asesoría UX", no garantía transaccional. Change 17 deberá re-ejecutar las mismas verificaciones dentro de su UoW transaccional con `SELECT FOR UPDATE` para evitar la ventana de tiempo entre validación y creación.

### D-02: Autenticación — CLIENT autenticado (Bearer token)

**Decisión**: `require_role(["CLIENT", "ADMIN"])`. No es endpoint público.

**Rationale**: Exponer un endpoint que reporta stock disponible por producto al mundo sería equivalente a un endpoint de scraping de inventario. Dado que el carrito solo tiene sentido para usuarios autenticados, el costo de requerir auth es cero para el flujo normal. ADMIN incluido para facilitar testing manual en staging.

**Alternativa considerada**: Endpoint público (sin auth). Rechazada por riesgo de scraping de stock y porque el carrito requiere sesión activa de todas formas.

### D-03: Tipos numéricos del precio — wire format string, comparación Decimal exacta

**Decisión**: El cliente envía `precio` percibido como string decimal (mismo wire-format que la API de productos, serializado por `@field_serializer` en Change 11). El backend convierte a `Decimal`, cuantiza a 2 decimales, y compara con `precio_base` del producto. Tolerancia = 0: cualquier diferencia dispara `PRECIO_CAMBIADO`.

**Rationale**: Usar string en el wire evita pérdida de precisión por floating-point en JSON. La cuantización a 2 decimales alinea con `DECIMAL(10,2)` de la BD. Tolerancia cero es la política más simple y predecible para el usuario (si el precio cambió aunque sea 1 centavo, se le notifica).

**Alternativa considerada**: Tolerancia configurable (ej. ±0.01). Rechazada por complejidad adicional sin beneficio claro en v1.

### D-04: Identidad de ítems — producto_id + personalización

**Decisión**: El request incluye `producto_id` (UUID string) + `cantidad: int ≥ 1` + `personalizacion: list[str]` + `precio: str`. La personalización no afecta precio en v1 (no hay sobrecargo por ingredientes). Se valida defensivamente que todos los IDs de personalización correspondan a ingredientes `es_removible=true` del producto. Si alguno no cumple → tipo de cambio `PERSONALIZACION_INVALIDA`.

**Rationale**: Mantiene la identidad de items consistente con Change 15 (`buildItemKey(producto_id, personalizacion)`). La validación defensiva evita que el frontend envíe personalización arbitraria que luego Change 17 rechazaría.

**Alternativa considerada**: Ignorar personalización en la validación. Rechazada porque Change 17 necesitará saber si la personalización es válida antes de crear la línea de pedido.

### D-05: Respuesta SIEMPRE 200 OK con ok: bool + cambios[]

**Decisión**: El endpoint nunca devuelve 4xx por "stock insuficiente" o "precio cambiado". Esos son datos de negocio en el payload `200 OK`. RFC 7807 solo aplica a payload mal formado (422) o auth (401/403).

**Rationale**: Los cambios detectados son información, no errores de protocolo. Modelarlos como 4xx haría el manejo en el frontend más complejo (hay que parsear el error HTTP además de la respuesta) y viola el principio de que HTTP status representa el estado del protocolo, no del negocio.

**Alternativa considerada**: 422 con lista de errores de negocio. Rechazada por mezcla de capas y porque Pydantic ya usa 422 para validación de schema.

**UX de PRECIO_CAMBIADO (aceptación implícita con feedback explícito)**:
Cuando `ok=true` y existen cambios de tipo `PRECIO_CAMBIADO` (y ningún cambio bloqueante), el frontend:
1. Muestra aviso visible: `"Los precios de [N] producto(s) cambiaron. Al continuar, aceptás los nuevos precios."`
2. Cambia la etiqueta del botón de continuar a `"Continuar con nuevos precios"` (en lugar de `"Continuar al pago"`).
3. El botón `"Continuar al pago"` (texto estándar) solo se muestra cuando `cambios` está completamente vacío.
Esta distinción visual garantiza que el usuario no avanza sin haber visto que los precios cambiaron, sin requerir una confirmación modal adicional.

### D-06: UoW de solo lectura

**Decisión**: El service usa `UnitOfWork()` para abrir sesión de BD pero nunca llama métodos de escritura ni hace commit con cambios. El commit final es no-op porque no se modificaron entidades.

**Rationale**: Reutiliza el patrón UoW establecido en Change 11/14/15 sin crear un nuevo mecanismo. La semántica de "solo lectura" se documenta en el service y en la spec, no se fuerza con una transacción `READ ONLY` de PostgreSQL (innecesario para esta escala).

**Alternativa considerada**: Acceso directo a sesión de BD sin UoW. Rechazada por inconsistencia con el patrón establecido en el proyecto.

### D-07: Política anti-N+1 — SELECT WHERE id IN (...)

**Decisión**: El service recopila todos los `producto_id` del request y ejecuta un único `SELECT * FROM productos WHERE id IN (...)`. No consulta productos uno por uno.

**Rationale**: Un carrito puede tener N items. Con N consultas individuales, el tiempo de respuesta escalaría linealmente. El repository pattern ya soporta `get_by_ids(ids)` (establecido en Change 11). `lazy="noload"` garantiza que las relaciones no se cargan automáticamente.

### D-08: Idempotencia — sin idempotency-key

**Decisión**: No requiere `Idempotency-Key` header. Repetir la llamada N veces siempre devuelve la foto actual del estado de la BD.

**Rationale**: El endpoint no produce efectos secundarios, por lo que el concepto de idempotency-key no aplica (es idempotente por naturaleza).

### D-09: Frontend — validación on-mount al navegar a /checkout/review

**Decisión**: La mutación se dispara on-mount al navegar a `/checkout/review`. El componente `<PreCheckoutReview/>` invoca `mutateAsync()` automáticamente en su `useEffect` de montaje. No hay un botón de "Verificar" adicional — la validación es parte del proceso de carga de la página. El usuario ve inmediatamente el loading state (spinner) y luego el resultado de la validación. No se ejecuta automáticamente al modificar el carrito.

**Rationale**: El usuario llega a `/checkout/review` con intención de proceder al pago; disparar la validación automáticamente es más fluido que pedirle hacer clic en un botón adicional. Llamar al endpoint en cada cambio del carrito (fuera de esta página) generaría requests innecesarios. TanStack Query `useMutation` es el patrón correcto — `mutateAsync()` en `useEffect([], [])` garantiza que se ejecuta exactamente una vez al montar.

**Alternativa considerada**: Botón "Validar carrito" explícito. Rechazada porque agrega un paso innecesario al flujo de checkout — el usuario ya tomó la decisión de ir a `/checkout/review`.

### D-10: Contrato hacia Change 17 — diferido explícitamente

**Decisión**: Change 17 puede elegir entre (a) invocar internamente `validar_pre_checkout` antes de crear el pedido, o (b) re-implementar validaciones equivalentes dentro de su UoW transaccional con `SELECT FOR UPDATE`. Esta decisión queda diferida a Change 17. Change 16 no la fija.

**Rationale**: Forzar una implementación aquí introduciría acoplamiento prematuro. Change 17 conocerá mejor sus necesidades transaccionales. Lo importante es documentar que la validación de Change 16 no es suficiente como garantía transaccional.

## Risks / Trade-offs

**[Risk] TOCTOU entre validación y creación de pedido** → Mitigation: Documentado explícitamente en D-01 y D-10. Change 17 deberá re-ejecutar validaciones con `SELECT FOR UPDATE`. La UI de Change 16 debe comunicar claramente que el resultado es "a este momento" y no garantiza el slot hasta que el pedido sea creado.

**[Risk] Personalización inválida no detectada en Change 15** → Mitigation: La validación de `PERSONALIZACION_INVALIDA` en Change 16 actúa como barrera. Si el frontend envía ingredientes inválidos, el usuario recibe feedback antes de intentar crear el pedido.

**[Risk] Stock cambia entre validación y creación** → Mitigation: Inherente al diseño (no hay reserva). Documentado. Change 17 cierra esta ventana con `SELECT FOR UPDATE`.

**[Risk] Carrito muy grande (muchos items únicos)** → Mitigation: `SELECT WHERE id IN (...)` escala O(1) en número de consultas. PostgreSQL maneja bien IN con decenas de IDs. No se anticipa un carrito con más de 20-30 items distintos.

**[Risk] Precio almacenado en cartStore como `number` (JavaScript float)** → Mitigation: El hook `useValidatePreCheckout` convierte `item.precio` a string con `item.precio.toFixed(2)` antes de enviar al backend, garantizando precisión decimal correcta en el wire.

## Migration Plan

No hay cambios de BD. No hay datos que migrar. El despliegue consiste en:
1. Registrar el nuevo router en el `main.py` del backend.
2. Desplegar el nuevo módulo `app/pedidos/` (router, service, schemas).
3. Desplegar el nuevo feature frontend `pre-checkout-validation`.
4. La ruta `/checkout/review` queda disponible automáticamente con el guard CLIENT.

**Rollback**: Remover el registro del router (1 línea) y el deploy del módulo. Sin impacto en BD ni en otras features.

## Naming Decisions

### NOTA DE NAMING (D-11)
El módulo de service de este change se nombra `pedidos_validar_service.py` (no `pedidos_service.py`) para dejar ese namespace disponible para Change 17, que creará el service transaccional de creación de pedidos. Change 16 NO debe crear `pedidos_service.py`.

- Archivo correcto: `backend/app/services/pedidos_validar_service.py`
- Función principal: `pedidos_validar_service.validar_pre_checkout(uow, request)`
- Change 17 usará: `pedidos_service.py` para la creación transaccional del pedido

## Open Questions

- **OQ-01**: ¿Debe `<PreCheckoutReview />` permitir al usuario "ajustar carrito" inline (abrir cart drawer) o redirigir a `/cart`? Decisión de UX — ambas opciones son válidas y el componente puede soportar ambas con una prop de configuración. Diferida a la implementación (Change 17 task de UX review).
- **OQ-02**: ¿Cuántos items como máximo puede tener un carrito? No hay límite definido actualmente en Change 15. Si se define un límite, Change 16 podría rechazar requests con más de N items distintos (422). Diferido a Change 17 o política de límites del carrito.
