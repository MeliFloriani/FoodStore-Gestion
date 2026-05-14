## 1. Backend — Failing Tests (write before implementation)

- [x] 1.1 Write unit tests for `RegisterRequest` and `LoginRequest` Pydantic schemas: field validation, min-length on password, EmailStr coercion — `backend/tests/unit/test_auth_schemas.py`
- [x] 1.2 Write unit tests for `UserRead` serialization: `id` as str, `roles` as flat list of codigo strings — `backend/tests/unit/test_auth_schemas.py`
- [x] 1.3 Write unit tests for `TokenResponse` schema: `token_type == "bearer"`, `expires_in == 1800` — `backend/tests/unit/test_auth_schemas.py`
- [x] 1.4 Write integration test stubs for `POST /api/v1/auth/register` (201, 409, 422) — mark `xfail` until router exists — `backend/tests/integration/test_auth_register.py`
- [x] 1.5 Write integration test stubs for `POST /api/v1/auth/login` (200, 401 wrong password, 401 unknown email, 429 rate limit) — mark `xfail` until router exists — `backend/tests/integration/test_auth_login.py`

## 2. Backend — Pydantic Schemas

- [x] 2.1 Create `backend/app/schemas/auth.py` with `RegisterRequest` (nombre, apellido, email: EmailStr, password: str min_length=8), `LoginRequest` (email: EmailStr, password: str), `UserRead` (id: str, nombre, apellido, email, roles: list[str] with @computed_field or @field_serializer reading usuario_roles), `TokenResponse` (access_token, refresh_token, token_type="bearer", expires_in: int = 1800)
- [x] 2.2 Add `UserRead` `@field_serializer` for `id` converting UUID → str; add `@computed_field` for `roles` extracting `ur.rol.codigo` from `usuario_roles` relationship — ensure `model_config = ConfigDict(from_attributes=True)`

## 3. Backend — Security Extensions (lift D-07)

- [x] 3.1 Add `BCRYPT_COST: int = 12` to `Settings` in `backend/app/core/config.py`; update `backend/.env.example` with `BCRYPT_COST=12`
- [x] 3.2 Extend `backend/app/core/security.py`: add `hash_password(plain: str) -> str` using `passlib[bcrypt]` at `get_settings().BCRYPT_COST`; add `verify_password(plain: str, hashed: str) -> bool` (no exceptions on invalid hash)
- [x] 3.3 Add `create_access_token(subject: str, expires_in: int = 1800) -> str` to `security.py`: payload `{sub, iat, exp, type: "access"}`, signed with SECRET_KEY
- [x] 3.4 Add `create_refresh_token(subject: str, expires_in: int = 7*24*3600) -> tuple[str, str]` to `security.py`: payload `{sub, iat, exp, type: "refresh"}`; return `(cleartext_jwt, sha256_hex_digest)`
- [x] 3.5 Write unit tests for `hash_password` and `verify_password` (happy path, wrong password, invalid hash) — `backend/tests/unit/test_security.py`
- [x] 3.6 Write unit tests for `create_access_token` (decodable, correct sub, respects expires_in) — `backend/tests/unit/test_security.py`
- [x] 3.7 Write unit tests for `create_refresh_token` (returns tuple, digest is 64 hex chars, sha256 of cleartext matches digest, payload type == "refresh") — `backend/tests/unit/test_security.py`
- [x] 3.8 Add `passlib[bcrypt]` to `backend/requirements.txt` if not already present; verify `python-jose[cryptography]` is present

## 4. Backend — RefreshTokenRepository

- [x] 4.1 Extend existing `RefreshTokenRepository` in `backend/app/repositories/user.py`: add method `insert(token: RefreshToken) -> RefreshToken` using `self.create(token)` (the `BaseRepository.create()` method which calls `session.add + session.flush`); add method `revoke_by_hash(token_hash: str) -> bool` setting `revoked_at = datetime.utcnow()` on match and flushing
- [x] 4.2 Write unit/integration tests for `RefreshTokenRepository.insert` (row exists after commit) and `revoke_by_hash` (returns True + sets revoked_at; returns False for unknown hash) — `backend/tests/unit/test_user_repository.py` (same file as other user-domain repository tests)

## 4.5 Backend — UsuarioRepository.get_by_email

> **TDD note**: write the unit test (4.6) FIRST as a failing test, then implement (4.5). The numbering is out-of-order intentionally to avoid cascade renumbering of §5+; the execution order MUST still be tests-before-implementation.

- [x] 4.5 Add `get_by_email(email: str) -> Usuario | None` to `UsuarioRepository` in `backend/app/repositories/user.py`: query `select(Usuario).where(Usuario.email == email, Usuario.deleted_at.is_(None))`; return first result or `None`. NOTE: a comment in `user.py` deferred this to "Change 06" — this change arrives earlier and implements it here as required by the auth service.
- [x] 4.6 Write unit test for `UsuarioRepository.get_by_email`: returns matching `Usuario` for existing email, returns `None` for unknown email — `backend/tests/unit/test_user_repository.py`

## 4.3 Backend — RolRepository.get_by_codigo

> **TDD note**: write the unit test (4.4) FIRST as a failing test, then implement (4.3). The numbering is out-of-order intentionally to avoid cascade renumbering of §5+; the execution order MUST still be tests-before-implementation.

- [x] 4.3 Add `get_by_codigo(codigo: str) -> Rol | None` to `RolRepository` in `backend/app/repositories/user.py`: query `select(Rol).where(Rol.codigo == codigo, Rol.deleted_at.is_(None))`; return first result or `None`. NOTE: `RolRepository` already exists in `user.py` and `uow.roles` is already wired in `core/uow.py` — no new file or UoW changes required.
- [x] 4.4 Write unit test for `RolRepository.get_by_codigo`: returns matching `Rol` for valid codigo, returns `None` for unknown codigo — `backend/tests/unit/test_user_repository.py`

## 5. Backend — AuthService.register_user

- [x] 5.1 Create `backend/app/services/auth.py` with `AuthService` class (stateless, receives UoW via constructor or method parameter)
- [x] 5.2 Implement `register_user(uow: UnitOfWork, data: RegisterRequest) -> Usuario`: (a) look up email uniqueness via `await uow.usuarios.get_by_email(data.email)` → raise `ConflictError` if a user is returned; (b) hash password; (c) create `Usuario` via `uow.usuarios.create()`; (d) look up role via `rol = await uow.roles.get_by_codigo("CLIENT")` — if `rol is None`, raise HTTP 500 / `RuntimeError("CLIENT role not seeded")` (seed failure guard); (e) create `UsuarioRol(usuario_id=usuario.id, rol_id=rol.id, asignado_por_id=None)` via `uow.usuario_roles.create()`; (f) return the `Usuario` instance.
- [x] 5.3 Write unit tests for `AuthService.register_user`: successful registration (returns Usuario with roles loaded), 409 on duplicate email, 500 when CLIENT role missing from seed — `backend/tests/unit/test_auth_service.py`

## 6. Backend — AuthService.login_user

- [x] 6.1 Implement `login_user(uow: UnitOfWork, data: LoginRequest, request: Request) -> TokenResponse` in `AuthService`: look up user via `await uow.usuarios.get_by_email(data.email)`; if not found, run dummy `verify_password` call (enumeration prevention) + raise `UnauthorizedError("Invalid credentials", code="invalid_credentials")`; call `verify_password(data.password, user.password_hash)` — if False, raise same `UnauthorizedError`; call `create_access_token(str(user.id))`; call `create_refresh_token(str(user.id))`; insert `RefreshToken` row via `uow.refresh_tokens.insert()`; return `TokenResponse`
- [x] 6.2 Write unit test for `login_user` happy path (returns TokenResponse, refresh token row inserted) — `backend/tests/unit/test_auth_service.py`
- [x] 6.3 Write unit test for `login_user` with wrong password (raises UnauthorizedError with code "invalid_credentials") — `backend/tests/unit/test_auth_service.py`
- [x] 6.4 Write unit test for enumeration prevention: non-existent email path runs dummy bcrypt verify and returns same error shape as wrong-password path — `backend/tests/unit/test_auth_service.py`

## 7. Backend — Auth Router + Integration Tests

- [x] 7.1 Create `backend/app/api/v1/auth.py` with `auth_router = APIRouter(prefix="/auth", tags=["auth"])`
- [x] 7.2 Implement `POST /register` endpoint: `response_model=UserRead`, status 201; call `AuthService.register_user`; wrap `ConflictError` → HTTP 409
- [x] 7.3 Implement `POST /login` endpoint: `response_model=TokenResponse`; apply `@limiter.limit("5/15minutes")` from `app/core/rate_limit.py`; call `AuthService.login_user`
- [x] 7.4 Write integration test: `POST /api/v1/auth/register` 201 happy path — verify response body shape (`id` is str UUID, `roles == ["CLIENT"]`) — `backend/tests/integration/test_auth_register.py`
- [x] 7.5 Write integration test: `POST /api/v1/auth/register` 409 on duplicate email — `backend/tests/integration/test_auth_register.py`
- [x] 7.6 Write integration test: `POST /api/v1/auth/register` 422 on short password — `backend/tests/integration/test_auth_register.py`
- [x] 7.7 Write integration test: `POST /api/v1/auth/login` 200 — verify TokenResponse shape and that `token_type == "bearer"` and `expires_in == 1800` — `backend/tests/integration/test_auth_login.py`
- [x] 7.8 Write integration test: `POST /api/v1/auth/login` 401 wrong password — verify body `{ code: "invalid_credentials" }` — `backend/tests/integration/test_auth_login.py`
- [x] 7.9 Write integration test: `POST /api/v1/auth/login` 401 non-existent email — verify same body shape as wrong password — `backend/tests/integration/test_auth_login.py`
- [x] 7.10 Write integration test: rate limit — 6th login request returns 429 — `backend/tests/integration/test_auth_login.py`

## 8. Backend — Wire into build_v1_router

- [x] 8.1 Import `auth_router` from `backend/app/api/v1/auth.py` inside `build_v1_router` in `backend/app/api/v1/router.py`; add `router.include_router(auth_router)` inside the factory
- [x] 8.2 Run `openapi.json` inspection smoke test: verify `/api/v1/auth/register` and `/api/v1/auth/login` appear in the schema with correct methods and response codes

## 9. Frontend — types.ts Contract Fixes

- [x] 9.1 In `frontend/src/entities/auth/types.ts`: change `id: number` to `id: string` on the `User` interface
- [x] 9.2 In same file: add `apellido: string` field to the `User` interface
- [x] 9.3 Audit all TypeScript files that reference `User.id` for numeric comparisons or numeric assignments; fix any type errors introduced by the `number → string` change
- [x] 9.4 If a unit test file exists for auth types (e.g. `frontend/src/entities/auth/__tests__/types.test.ts`), update or add a test asserting `User` is assignable from a backend `UserRead` shape with `id: string` and `apellido: string`

## 10. Frontend — errors.ts AppError Type + FastAPI 422 Parsing

- [x] 10.1 In `frontend/src/shared/lib/errors.ts`: update the `AppError` TypeScript type — change `status?: number` to `status: number | null`; remove the `details?: Record<string, unknown>` field; add `fieldErrors?: Record<string, string[]>` (field name → array of error message strings). This is a breaking type change: any consumer using `AppError.details` or relying on `status` being optional must be updated.
- [x] 10.2 Audit all TypeScript files that reference `AppError.details` or `AppError.status` for breaking-change impact introduced by task 10.1 (analogous to the `User.id: number → string` audit in task 9.3). Fix any type errors before proceeding to 10.3.
- [x] 10.3 In `frontend/src/shared/lib/errors.ts`: replace the 422 flat-string parsing block with FastAPI `detail` array parsing — implement the D-H key derivation rule: if `loc[0] === "body"` and `loc.length === 2`, key = `loc[1]`; if `loc[0] === "body"` and `loc.length > 2`, key = `loc.slice(1).join(".")`; if `loc[0] !== "body"`, key = `loc.join(".")`. Accumulate multiple `msg` strings for the same key into `fieldErrors[key]: string[]`. Set `status: null` for non-HTTP errors.
- [x] 10.4 Write unit tests (or update existing) in `frontend/src/shared/lib/__tests__/errors.test.ts`: test single body field, nested body field, non-body location, multiple errors same field (accumulated into array), flat-string fallback (no crash, `fieldErrors` undefined) — all per D-H spec

## 11. Frontend — AuthLayout authenticating Spinner

- [x] 11.1 In `frontend/src/app/layouts/AuthLayout.tsx`: extend the spinner/loading guard from `status === 'idle'` to also cover `status === 'authenticating'`; the condition should be `status === 'idle' || status === 'authenticating'`
- [x] 11.2 Write or update unit/smoke test for `AuthLayout` asserting that mounting with `status: 'authenticating'` renders the spinner (not the auth form) — `frontend/src/app/layouts/__tests__/AuthLayout.test.tsx`

## 12. End-to-End Happy-Path Test

- [x] 12.1 Write an E2E-style integration test (backend) that exercises the full auth round-trip: `POST /register` → get `UserRead`; `POST /login` with same credentials → get `TokenResponse`; `GET /api/v1/health` (or any protected endpoint once one exists) using the returned `access_token` in `Authorization: Bearer` header → verify the request is not rejected with 401 — `backend/tests/integration/test_auth_e2e.py`
