# backend-auth-register-login Specification

## Purpose
TBD - created by archiving change auth-register-login. Update Purpose after archive.
## Requirements
### Requirement: POST /api/v1/auth/register creates user with CLIENT role
The system SHALL expose `POST /api/v1/auth/register` accepting a JSON body of type `RegisterRequest` (`nombre: str`, `apellido: str`, `email: EmailStr`, `password: str` with minimum length 8). On success it SHALL:
1. Check email uniqueness via `await uow.usuarios.get_by_email(email)` — raise HTTP 409 if a `Usuario` is returned.
2. Hash the password with bcrypt at cost `Settings.BCRYPT_COST` (≥ 12 in production).
3. Create a `Usuario` record with `password_hash: CHAR(60)`.
4. Look up the CLIENT role via `rol = await uow.roles.get_by_codigo("CLIENT")`. If `rol is None` (seed not run), raise HTTP 500 with a server-error body (not a user-visible 4xx).
5. Auto-assign the `CLIENT` role by inserting `UsuarioRol(usuario_id=usuario.id, rol_id=rol.id, asignado_por_id=None)` (system-generated bootstrap, allowed per Change 03 task 8.4). `rol_id` MUST be `rol.id` (a `uuid.UUID`), never the string `"CLIENT"`.
6. Return HTTP 201 with `UserRead` body: `{ id: str, nombre: str, apellido: str, email: str, roles: list[str] }` where `roles` is a flat list of `rol.codigo` strings (e.g. `["CLIENT"]`).

All mutations MUST go through `UnitOfWork`; the router MUST NOT call `session.commit()` directly.

#### Scenario: Successful registration returns 201 UserRead
- **WHEN** `POST /api/v1/auth/register` is called with valid body `{ nombre, apellido, email, password }`
- **THEN** HTTP 201 is returned
- **THEN** the response body matches `{ id: <uuid-string>, nombre, apellido, email, roles: ["CLIENT"] }`
- **THEN** a `Usuario` row exists in the database with matching email and bcrypt-hashed password
- **THEN** the CLIENT role was looked up via `uow.roles.get_by_codigo("CLIENT")` (returning a `Rol` with a `uuid.UUID` primary key `id`)
- **THEN** a `UsuarioRol` row links the new user to role `CLIENT` via `rol_id = rol.id` (UUID FK) with `asignado_por_id = NULL`

#### Scenario: CLIENT role missing from seed returns 500
- **WHEN** `POST /api/v1/auth/register` is called and `uow.roles.get_by_codigo("CLIENT")` returns `None` (seed not run)
- **THEN** HTTP 500 is returned
- **THEN** no `Usuario` or `UsuarioRol` row is created (transaction rolled back)

#### Scenario: Duplicate email returns 409
- **WHEN** `POST /api/v1/auth/register` is called with an email that already exists in `usuario.email`
- **THEN** HTTP 409 is returned
- **THEN** the response body follows RFC 7807: `{ detail: "El email ya está registrado", code: "email_already_exists" }`
- **THEN** no duplicate `Usuario` row is created

#### Scenario: Invalid body returns 422
- **WHEN** `POST /api/v1/auth/register` is called with a missing required field or password shorter than 8 characters
- **THEN** HTTP 422 is returned
- **THEN** the response body is FastAPI's standard per-field `detail` array: `[{ loc: ["body", "<field>"], msg: "<message>", type: "<error_type>" }]`

#### Scenario: Password stored as bcrypt hash, never cleartext
- **WHEN** a `Usuario` is created via register
- **THEN** `usuario.password_hash` starts with `$2b$` (bcrypt prefix)
- **THEN** the cleartext password is NOT present anywhere in the database

---

### Requirement: POST /api/v1/auth/login issues JWT pair
The system SHALL expose `POST /api/v1/auth/login` accepting a JSON body of type `LoginRequest` (`email: EmailStr`, `password: str`). On success it SHALL return HTTP 200 with `TokenResponse`:
```
{ access_token: str, refresh_token: str, token_type: "bearer", expires_in: 1800 }
```
Access token TTL SHALL be 30 minutes (1800 seconds). Refresh token TTL SHALL be 7 days.

The refresh token cleartext SHALL be returned to the client exactly once and MUST NOT be stored in the database. Only the SHA-256 hex digest (64-char string) SHALL be persisted in `refresh_token.token_hash`.

#### Scenario: Successful login returns 200 TokenResponse
- **WHEN** `POST /api/v1/auth/login` is called with correct email and password
- **THEN** HTTP 200 is returned
- **THEN** the body contains `{ access_token, refresh_token, token_type: "bearer", expires_in: 1800 }`
- **THEN** `access_token` is a valid JWT decodable with `Settings.SECRET_KEY` and algorithm `Settings.JWT_ALGORITHM`
- **THEN** the decoded access token payload contains `sub` (user UUID as string)
- **THEN** a `RefreshToken` row is inserted with `token_hash = sha256(refresh_token).hexdigest()` and `expires_at = now + 7 days`

#### Scenario: Wrong password returns 401 with generic message
- **WHEN** `POST /api/v1/auth/login` is called with a correct email but wrong password
- **THEN** HTTP 401 is returned
- **THEN** the body is `{ "detail": "Invalid credentials", "code": "invalid_credentials" }`
- **THEN** the response does NOT reveal that the email exists

#### Scenario: Non-existent email returns 401 with generic message
- **WHEN** `POST /api/v1/auth/login` is called with an email that does not exist in the database
- **THEN** HTTP 401 is returned
- **THEN** the body is `{ "detail": "Invalid credentials", "code": "invalid_credentials" }`
- **THEN** the response is indistinguishable from a wrong-password response (no enumeration)

#### Scenario: Login rate limit triggers 429 after 5 failed attempts
- **WHEN** the same client IP sends 6 or more `POST /api/v1/auth/login` requests within 15 minutes
- **THEN** the 6th and subsequent requests receive HTTP 429
- **THEN** the response body contains a rate-limit message

#### Scenario: Refresh token cleartext never stored in database
- **WHEN** a successful login inserts a `RefreshToken` row
- **THEN** `refresh_token.token_hash` is exactly 64 hexadecimal characters (SHA-256 digest)
- **THEN** querying `refresh_token` for the cleartext JWT value returns no results

---

### Requirement: 401 enumeration policy (no email disclosure)
The login endpoint SHALL apply a constant-time verification path regardless of whether the email exists. If the email is not found, the system SHALL run a dummy `bcrypt.checkpw` call (or equivalent) to prevent timing-based enumeration. The HTTP response MUST be identical (status, body, timing within acceptable variance) for "email not found" and "wrong password" cases.

#### Scenario: Timing attack mitigated on non-existent email
- **WHEN** login is called with a non-existent email
- **THEN** the handler still performs a dummy password-verification call to equalize response time
- **THEN** the returned 401 body is `{ "detail": "Invalid credentials", "code": "invalid_credentials" }`

---

### Requirement: Auth router registered under /api/v1/auth
`backend/app/api/v1/auth.py` SHALL define an `APIRouter` with prefix `/auth` and tags `["auth"]`. This router SHALL be included inside the `build_v1_router` factory in `app/api/v1/router.py` so that all auth endpoints are reachable at `/api/v1/auth/*`.

#### Scenario: Register endpoint is reachable at correct path
- **WHEN** the app routes are inspected
- **THEN** `POST /api/v1/auth/register` exists and is wired to the register handler

#### Scenario: Login endpoint is reachable at correct path
- **WHEN** the app routes are inspected
- **THEN** `POST /api/v1/auth/login` exists and is wired to the login handler

---

### Requirement: UsuarioRepository.get_by_email
`UsuarioRepository` in `backend/app/repositories/user.py` SHALL implement `get_by_email(email: str) -> Usuario | None` using `select(Usuario).where(Usuario.email == email, Usuario.deleted_at.is_(None))`. The register and login flows MUST use this method for email lookups — not `list_all(filters=...)`.

#### Scenario: get_by_email returns Usuario for existing email
- **WHEN** `uow.usuarios.get_by_email("existing@example.com")` is called
- **THEN** the matching `Usuario` instance is returned

#### Scenario: get_by_email returns None for unknown email
- **WHEN** `uow.usuarios.get_by_email("unknown@example.com")` is called
- **THEN** `None` is returned without raising any exception

---

### Requirement: RolRepository.get_by_codigo
`RolRepository` in `backend/app/repositories/user.py` SHALL implement `get_by_codigo(codigo: str) -> Rol | None` using `select(Rol).where(Rol.codigo == codigo, Rol.deleted_at.is_(None))`. The register flow MUST use this method to resolve the CLIENT role's UUID before creating a `UsuarioRol` record.

#### Scenario: get_by_codigo returns Rol for existing codigo
- **WHEN** `uow.roles.get_by_codigo("CLIENT")` is called and the CLIENT role is seeded
- **THEN** the matching `Rol` instance is returned with its `id` (uuid.UUID) populated

#### Scenario: get_by_codigo returns None for unknown codigo
- **WHEN** `uow.roles.get_by_codigo("NONEXISTENT")` is called
- **THEN** `None` is returned without raising any exception

