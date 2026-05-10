## ADDED Requirements

### Requirement: Configuración tipada con pydantic-settings v2
El sistema SHALL proveer una clase `Settings(BaseSettings)` en `app/core/config.py` que lea variables de entorno y archivo `.env`, valide tipos al arranque y falle con error claro si falta una variable obligatoria. SHALL existir un singleton `get_settings()` decorado con `@lru_cache` para evitar releer el entorno en cada llamada.

#### Scenario: Arranque con variables completas
- **WHEN** todas las variables requeridas están presentes en el entorno o en `.env`
- **THEN** `get_settings()` retorna una instancia de `Settings` sin lanzar excepción
- **THEN** los tipos de cada campo coinciden con los declarados (str, list[str], int, etc.)

#### Scenario: Arranque con variable obligatoria ausente
- **WHEN** `DATABASE_URL` no está definida en el entorno ni en `.env`
- **THEN** pydantic-settings lanza `ValidationError` al instanciar `Settings`
- **THEN** el mensaje de error identifica el campo faltante

#### Scenario: Singleton con lru_cache
- **WHEN** `get_settings()` se llama dos veces consecutivas
- **THEN** retorna el mismo objeto (identidad de instancia, no solo igualdad de valores)

### Requirement: Variables de entorno definidas
`Settings` SHALL declarar al menos las siguientes variables con sus tipos y defaults:

| Variable | Tipo | Default | Obligatoria |
|---|---|---|---|
| `DATABASE_URL` | `str` | — | Sí |
| `ENVIRONMENT` | `str` | `"development"` | No |
| `BACKEND_CORS_ORIGINS` | `list[str]` | `["http://localhost:5173"]` | No |
| `API_V1_PREFIX` | `str` | `"/api/v1"` | No |
| `LOG_LEVEL` | `str` | `"INFO"` | No |
| `RATE_LIMIT_DEFAULT` | `str` | `"100/minute"` | No |
| `APP_VERSION` | `str` | `"0.1.0"` | No |

#### Scenario: BACKEND_CORS_ORIGINS acepta string separado por comas
- **WHEN** `BACKEND_CORS_ORIGINS` está definida como `"http://localhost:5173,http://localhost:3000"` en el entorno
- **THEN** `settings.BACKEND_CORS_ORIGINS` es una lista Python con dos elementos: `["http://localhost:5173", "http://localhost:3000"]`

#### Scenario: BACKEND_CORS_ORIGINS acepta JSON array
- **WHEN** `BACKEND_CORS_ORIGINS` está definida como `'["http://localhost:5173"]'` en el entorno
- **THEN** `settings.BACKEND_CORS_ORIGINS` es `["http://localhost:5173"]`

#### Scenario: Valores default aplicados
- **WHEN** solo `DATABASE_URL` está definida en el entorno
- **THEN** `settings.ENVIRONMENT` es `"development"`, `settings.API_V1_PREFIX` es `"/api/v1"`, `settings.LOG_LEVEL` es `"INFO"`

### Requirement: Archivo .env.example actualizado
El archivo `backend/.env.example` SHALL contener todas las variables declaradas en `Settings`, con valores de ejemplo para desarrollo local.

#### Scenario: .env.example contiene todas las variables nuevas
- **WHEN** se lee `backend/.env.example`
- **THEN** contiene claves para: `DATABASE_URL`, `ENVIRONMENT`, `BACKEND_CORS_ORIGINS`, `API_V1_PREFIX`, `LOG_LEVEL`, `RATE_LIMIT_DEFAULT`
- **THEN** `DATABASE_URL` tiene un ejemplo con formato postgresql+asyncpg://
