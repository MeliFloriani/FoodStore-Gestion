## MODIFIED Requirements

### Requirement: User and AuthStatus types defined
`src/entities/auth/types.ts` SHALL export:
- `User` type with: `id: string` (UUID serialized as string — **BREAKING**: changed from `number`), `nombre: string`, `apellido: string` (NEW field), `email: string`, `roles: string[]`
- `AuthStatus` type: `'idle' | 'authenticating' | 'authenticated' | 'unauthenticated'`

The `id` field type change from `number` to `string` is a breaking change. All consumers of `User.id` MUST be updated to treat it as a string (UUID format).

The `apellido` field is newly required — any code constructing a `User` literal must supply it.

#### Scenario: User type matches backend UserRead schema
- **WHEN** the backend `POST /api/v1/auth/register` or `POST /api/v1/auth/login` response's user field is deserialized
- **THEN** it is assignable to the `User` type without TypeScript errors
- **THEN** `user.id` is a `string` (e.g. `"3fa85f64-5717-4562-b3fc-2c963f66afa6"`)
- **THEN** `user.apellido` is a non-empty `string`

#### Scenario: TypeScript strict mode rejects number-typed id
- **WHEN** code assigns `user.id = 42` (a number literal)
- **THEN** the TypeScript compiler emits a type error

#### Scenario: hasRole works unchanged with updated User type
- **WHEN** `hasRole('CLIENT')` is called with `user.roles = ['CLIENT']` (string array unchanged)
- **THEN** it returns `true` — the type change does not break this selector
