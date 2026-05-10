## ADDED Requirements

### Requirement: Configuración global de structlog en JSON
El sistema SHALL configurar structlog en `app/core/logging.py` con un pipeline de processors que produzca salida en formato JSON para `ENVIRONMENT != "development"` y texto legible (con colores) para `ENVIRONMENT == "development"`. La configuración SHALL aplicarse una única vez al arranque de la aplicación (llamada en `app/main.py`).

#### Scenario: Log en ambiente development con formato legible
- **WHEN** `settings.ENVIRONMENT == "development"` y la app arranca
- **THEN** los logs estructurados se imprimen en formato clave=valor o texto con colores

#### Scenario: Log en ambiente producción con formato JSON
- **WHEN** `settings.ENVIRONMENT != "development"` y la app arranca
- **THEN** cada evento de log es una línea JSON válida con campos: `event`, `level`, `timestamp`

#### Scenario: Configuración aplicada una vez al inicio
- **WHEN** `configure_logging()` se llama en `app/main.py` al inicializar la app
- **THEN** todos los subsiguientes `get_logger(__name__)` en cualquier módulo producen logs con el formato configurado

### Requirement: Helper get_logger disponible en todo el codebase
El sistema SHALL proveer `get_logger(name: str)` en `app/core/logging.py` que retorna un logger structlog bound con el nombre del módulo. Todos los módulos SHALL usar este helper en lugar de `logging.getLogger()` o `structlog.get_logger()` directamente.

#### Scenario: Logger con nombre de módulo
- **WHEN** `get_logger("app.core.config")` es llamado
- **THEN** retorna un logger bound que incluye `logger="app.core.config"` en cada evento

### Requirement: request_id propagado al logger via contextvars
El sistema SHALL integrar el middleware de `request_id` con el logger structlog de manera que cada evento de log emitido durante el procesamiento de un request incluya el `request_id` del middleware automáticamente, sin que el código de negocio lo pase explícitamente.

#### Scenario: Log durante un request incluye request_id
- **WHEN** cualquier módulo llama a `logger.info("evento")` durante el procesamiento de un HTTP request
- **THEN** el evento de log incluye el campo `request_id` con el mismo UUID que el header `X-Request-ID` de la respuesta

#### Scenario: Log fuera de un request no tiene request_id
- **WHEN** cualquier módulo llama a `logger.info("arranque")` durante el startup de la aplicación (fuera de un request)
- **THEN** el evento de log no incluye `request_id` (o lo incluye como None/vacío sin romper el pipeline)

### Requirement: LOG_LEVEL configurable via settings
El sistema SHALL usar `settings.LOG_LEVEL` para filtrar la salida de logs. Solo se emitirán eventos con nivel igual o superior al configurado.

#### Scenario: LOG_LEVEL=WARNING filtra INFO y DEBUG
- **WHEN** `settings.LOG_LEVEL == "WARNING"` y un módulo llama `logger.info("debug info")`
- **THEN** el evento NO aparece en la salida de logs

#### Scenario: LOG_LEVEL=DEBUG muestra todos los niveles
- **WHEN** `settings.LOG_LEVEL == "DEBUG"` y un módulo llama `logger.debug("detalle")`
- **THEN** el evento aparece en la salida de logs
