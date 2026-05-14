# frontend-error-handling Specification

## Purpose
Define the global error-handling infrastructure for the Food Store frontend: an `AppError` type with structured codes (AUTH_EXPIRED, FORBIDDEN, VALIDATION_ERROR, RATE_LIMITED, SERVER_ERROR, UNKNOWN) and a pure `normalizeError` transformation function that converts any AxiosError into a typed `AppError`, plus a React `ErrorBoundary` provider at app root that catches render errors and presents a recoverable fallback UI. These modules are pure infrastructure — they produce no side effects and import no stores — establishing the error-propagation contract that feature-level handlers and toast integration will follow.

## Requirements

### Requirement: AppError type and error normalizer
`src/shared/lib/errors.ts` SHALL export an `AppError` type and a `normalizeError(error: unknown): AppError` function that converts any AxiosError or unknown error into a structured `AppError`.

`AppError` type:
```
AppError {
  code: string            // e.g. 'AUTH_EXPIRED', 'FORBIDDEN', 'VALIDATION_ERROR', 'RATE_LIMITED', 'SERVER_ERROR', 'UNKNOWN'
  status: number | null   // HTTP status code if available
  message: string         // Human-readable message
  details?: string        // Optional extra context
  fieldErrors?: Record<string, string[]>  // Populated for 422 validation errors
}
```

#### Scenario: 401 normalized to AUTH_EXPIRED
- **WHEN** `normalizeError` receives an AxiosError with status 401
- **THEN** it returns `AppError { code: 'AUTH_EXPIRED', status: 401 }`

#### Scenario: 403 normalized to FORBIDDEN
- **WHEN** `normalizeError` receives an AxiosError with status 403
- **THEN** it returns `AppError { code: 'FORBIDDEN', status: 403 }`

#### Scenario: 422 normalized with fieldErrors
- **WHEN** `normalizeError` receives an AxiosError with status 422 and a response body containing field-level errors
- **THEN** it returns `AppError { code: 'VALIDATION_ERROR', status: 422, fieldErrors: { <field>: [<messages>] } }`

#### Scenario: 429 normalized to RATE_LIMITED
- **WHEN** `normalizeError` receives an AxiosError with status 429
- **THEN** it returns `AppError { code: 'RATE_LIMITED', status: 429 }`

#### Scenario: 500 normalized to SERVER_ERROR
- **WHEN** `normalizeError` receives an AxiosError with status 500
- **THEN** it returns `AppError { code: 'SERVER_ERROR', status: 500 }`

#### Scenario: Unknown error normalized with UNKNOWN code
- **WHEN** `normalizeError` receives a non-Axios error (e.g., a plain `Error` or null)
- **THEN** it returns `AppError { code: 'UNKNOWN', status: null }` without throwing

---

### Requirement: Global ErrorBoundary provider
`src/app/providers/ErrorBoundary.tsx` SHALL export a React class component (or functional component with `react-error-boundary`) that:
- Catches all unhandled React render errors at the app level.
- Renders an accessible fallback UI when an error is caught (at minimum: a visible error message and a "retry" button that resets the boundary).
- Does NOT expose internal error stack traces to the user in production.

#### Scenario: Render error is caught and fallback shown
- **WHEN** a child component throws during render
- **THEN** the ErrorBoundary renders the fallback UI instead of an empty/broken screen

#### Scenario: Fallback provides a reset mechanism
- **WHEN** the fallback UI is rendered after an error
- **THEN** there is an interactive element (button) that resets the error boundary state

---

### Requirement: HTTP error mapping documented for toast integration
The architecture SHALL document (in `design.md`) how errors propagate to the UI in future changes:
- Errors with `code: 'AUTH_EXPIRED'` are handled exclusively by the Axios response interceptor (auto-refresh flow). They SHALL NOT be forwarded to the toast system.
- Errors with all other codes (FORBIDDEN, VALIDATION_ERROR, RATE_LIMITED, SERVER_ERROR, UNKNOWN) SHALL be published to `uiStore.addToast()` by feature-level error handlers in future changes.
- The infrastructure files in this change (http.ts, errors.ts) SHALL NOT import `uiStore` directly.

#### Scenario: http.ts does not import uiStore
- **WHEN** `src/shared/api/http.ts` is inspected
- **THEN** it does not contain an import of `uiStore` or any module from `src/shared/store/`

#### Scenario: errors.ts is a pure transformation module
- **WHEN** `src/shared/lib/errors.ts` is inspected
- **THEN** it does not produce side effects (no store writes, no DOM events, no navigation calls)
