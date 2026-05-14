## MODIFIED Requirements

### Requirement: AppError type and error normalizer
`src/shared/lib/errors.ts` SHALL export an `AppError` type and a `normalizeError(error: unknown): AppError` function that converts any AxiosError or unknown error into a structured `AppError`.

`AppError` type (MODIFIED by this change from Change 04 baseline):
```
AppError {
  code: string            // e.g. 'AUTH_EXPIRED', 'FORBIDDEN', 'VALIDATION_ERROR', 'RATE_LIMITED', 'SERVER_ERROR', 'UNKNOWN'
  status: number | null   // HTTP status code, or null for non-HTTP errors (was: status?: number)
  message: string         // Human-readable message
  fieldErrors?: Record<string, string[]>  // Populated for 422 validation errors; each key maps to an array of error strings (was: details?: Record<string, unknown>)
}
```
**Breaking changes from Change 04 `AppError`**: `status` changes from `status?: number` (optional) to `status: number | null` (required, nullable). `details?: Record<string, unknown>` is removed and replaced by `fieldErrors?: Record<string, string[]>`. Any consumer of `AppError.details` or `AppError.status` must be audited (see tasks 10.1–10.2).

**MODIFIED behavior for HTTP 422**: When `normalizeError` receives an AxiosError with status 422, it SHALL parse the response body as FastAPI's structured `detail` array format: `detail: Array<{ loc: string[], msg: string, type: string }>`. It SHALL map each entry to `fieldErrors` using the following key derivation rule (D-H):
- If `loc[0]` is `"body"` and `loc.length === 2`: key = `loc[1]` (the field name)
- If `loc[0]` is `"body"` and `loc.length > 2`: key = `loc.slice(1).join(".")` (nested field path, e.g. `"address.calle"`)
- If `loc[0]` is NOT `"body"` (e.g. `"query"`, `"path"`): key = `loc.join(".")` (e.g. `"query.page"`)

Multiple entries with the same derived key SHALL have their `msg` values accumulated into an array: `fieldErrors[key]: string[]`.

The previous behavior (flat-string parsing of 422) is REPLACED by this structured parsing. The change is backward-compatible with the `AppError` type (the `fieldErrors` shape `Record<string, string[]>` is unchanged).

#### Scenario: 401 normalized to AUTH_EXPIRED
- **WHEN** `normalizeError` receives an AxiosError with status 401
- **THEN** it returns `AppError { code: 'AUTH_EXPIRED', status: 401 }`

#### Scenario: 403 normalized to FORBIDDEN
- **WHEN** `normalizeError` receives an AxiosError with status 403
- **THEN** it returns `AppError { code: 'FORBIDDEN', status: 403 }`

#### Scenario: 422 parsed from FastAPI detail array — single body field
- **WHEN** `normalizeError` receives an AxiosError with status 422 and body `{ "detail": [{ "loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error.email" }] }`
- **THEN** it returns `AppError { code: 'VALIDATION_ERROR', status: 422, fieldErrors: { email: ["value is not a valid email address"] } }`

#### Scenario: 422 parsed from FastAPI detail array — nested body field
- **WHEN** the 422 body contains `{ "detail": [{ "loc": ["body", "address", "calle"], "msg": "field required", "type": "missing" }] }`
- **THEN** `fieldErrors` contains key `"address.calle"` with value `["field required"]`

#### Scenario: 422 parsed from FastAPI detail array — non-body location
- **WHEN** the 422 body contains `{ "detail": [{ "loc": ["query", "page"], "msg": "value is not a valid integer", "type": "type_error.integer" }] }`
- **THEN** `fieldErrors` contains key `"query.page"` with value `["value is not a valid integer"]`

#### Scenario: 422 multiple errors for same field are accumulated
- **WHEN** the 422 body contains two entries both with `loc: ["body", "password"]`
- **THEN** `fieldErrors.password` is an array with both `msg` strings

#### Scenario: 422 with non-array detail falls back gracefully
- **WHEN** the 422 body contains `{ "detail": "Unprocessable Entity" }` (flat string, legacy format)
- **THEN** `normalizeError` returns `AppError { code: 'VALIDATION_ERROR', status: 422 }` without throwing
- **THEN** `fieldErrors` is undefined or empty (no crash)

#### Scenario: 429 normalized to RATE_LIMITED
- **WHEN** `normalizeError` receives an AxiosError with status 429
- **THEN** it returns `AppError { code: 'RATE_LIMITED', status: 429 }`

#### Scenario: 500 normalized to SERVER_ERROR
- **WHEN** `normalizeError` receives an AxiosError with status 500
- **THEN** it returns `AppError { code: 'SERVER_ERROR', status: 500 }`

#### Scenario: Unknown error normalized with UNKNOWN code
- **WHEN** `normalizeError` receives a non-Axios error (e.g., a plain `Error` or null)
- **THEN** it returns `AppError { code: 'UNKNOWN', status: null }` without throwing
