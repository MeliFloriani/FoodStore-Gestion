## ADDED Requirements

### Requirement: Tipo genérico Page[T] para respuestas paginadas
El sistema SHALL proveer en `app/schemas/base.py` un modelo Pydantic v2 genérico `Page[T]` con los campos: `items: list[T]`, `total: int`, `page: int`, `size: int`, `pages: int`. Todos los endpoints paginados de dominio SHALL usar este tipo como modelo de respuesta.

#### Scenario: Page[T] instanciable con lista de items
- **WHEN** se instancia `Page[str](items=["a","b"], total=10, page=1, size=2, pages=5)`
- **THEN** el objeto es un modelo Pydantic válido sin excepción de validación

#### Scenario: pages calculado correctamente
- **WHEN** `total=10` y `size=3`
- **THEN** `pages = ceil(total / size) = 4`

#### Scenario: Page vacía válida
- **WHEN** se instancia `Page[str](items=[], total=0, page=1, size=20, pages=0)`
- **THEN** el objeto es válido y `items` es una lista vacía

### Requirement: Helper create_pagination_meta
El sistema SHALL proveer una función `create_pagination_meta(total: int, page: int, size: int) -> dict` en `app/schemas/base.py` que calcule y retorne los metadatos de paginación: `total`, `page`, `size`, `pages`.

#### Scenario: Meta calculada correctamente
- **WHEN** `create_pagination_meta(total=25, page=2, size=10)` es llamada
- **THEN** retorna `{"total": 25, "page": 2, "size": 10, "pages": 3}`

#### Scenario: Divisón exacta en pages
- **WHEN** `create_pagination_meta(total=20, page=1, size=10)` es llamada
- **THEN** retorna `"pages": 2` (no 2.0, no 3)

### Requirement: ProblemDetail como modelo Pydantic RFC 7807
El sistema SHALL proveer en `app/schemas/base.py` un modelo `ProblemDetail` con los campos: `type: str`, `title: str`, `status: int`, `detail: str`, `instance: str`. Campos opcionales: `code: str | None`, `field: str | None`. Este modelo SHALL ser el tipo de retorno declarado de todos los exception handlers.

#### Scenario: ProblemDetail instanciable con campos mínimos
- **WHEN** se instancia `ProblemDetail(type="about:blank", title="Not Found", status=404, detail="Recurso no encontrado", instance="/api/v1/productos/999")`
- **THEN** el objeto es válido y serializable a JSON

#### Scenario: ProblemDetail con campos opcionales
- **WHEN** se instancia con `code="product_not_found"` y `field=None`
- **THEN** el objeto es válido y la serialización JSON incluye `"code": "product_not_found"` y omite `field` o lo incluye como null

#### Scenario: ProblemDetail serializa a JSON válido
- **WHEN** se llama `problem.model_dump_json()` sobre una instancia válida
- **THEN** el resultado es una cadena JSON parseable con todos los campos declarados
