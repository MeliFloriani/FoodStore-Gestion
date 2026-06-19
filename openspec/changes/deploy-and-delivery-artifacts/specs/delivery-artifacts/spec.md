## ADDED Requirements

### Requirement: Screenshots of key screens
The system SHALL generate at least 10 screenshots of the application running in production, covering the CE evaluation criteria.

#### Scenario: Screenshots cover CE criteria
- **WHEN** the screenshots are captured
- **THEN** they SHALL include at least:
  - CE-01: Home / Catálogo público con productos
  - CE-02: Detalle de producto con ingredientes
  - CE-03: Registro de nuevo usuario
  - CE-04: Inicio de sesión
  - CE-05: Carrito de compras con productos
  - CE-06: Checkout con selección de dirección
  - CE-07: Pago con MercadoPago (redirect a Checkout Pro)
  - CE-08: Documentación Swagger/OpenAPI en `/docs`
  - CE-09: Confirmación de pedido después del pago
  - CE-10: Historial de pedidos del cliente
  - CE-11: Timeline de estados del pedido
  - CE-12: Panel de administración (dashboard con métricas)
  - CE-13: Gestión de productos por ADMIN
  - CE-14: Gestión de pedidos con transición de estados

#### Scenario: Screenshots are organized
- **WHEN** the screenshots are saved
- **THEN** they are placed in `docs/screenshots/` directory
- **AND** named as `CE-NN-descripcion-breve.png`
- **AND** each screenshot is in PNG format

### Requirement: Video demo (5–10 minutes)
The system SHALL produce a video demonstration walking through the complete user and admin flows.

#### Scenario: Video covers end-to-end flow
- **WHEN** the demo video is recorded
- **THEN** it SHALL include:
  - Registro de cliente nuevo
  - Navegación del catálogo con filtros
  - Agregado de productos al carrito con personalización
  - Checkout y pago con MercadoPago (simulado en sandbox)
  - Seguimiento del pedido (timeline)
  - Panel de administración (dashboard, gestión de pedidos, usuarios, productos)

#### Scenario: Video is accessible
- **WHEN** the video is produced
- **THEN** it is uploaded as unlisted to YouTube or similar platform
- **AND** the link is included in the README

<!-- README update is a documentation task, not system behavior — tracked in tasks.md group 6 -->
