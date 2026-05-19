## ADDED Requirements

### Requirement: ProfileUpdate schema — editable fields only
`backend/app/schemas/profile.py` SHALL define `ProfileUpdate(BaseModel)` with:
- `model_config = ConfigDict(extra='ignore')` — extra fields (including `email`) are silently dropped.
- `nombre: str | None = Field(default=None, max_length=80)`
- `apellido: str | None = Field(default=None, max_length=80)`

No `email` field. If `email` appears in the request body, Pydantic's `extra='ignore'` removes it before the service processes the update.

#### Scenario: ProfileUpdate drops email field silently
- **WHEN** `ProfileUpdate(nombre="Ana", email="hack@test.com")` is instantiated
- **THEN** the resulting model has `nombre="Ana"` and no `email` attribute
- **THEN** no `ValidationError` is raised

#### Scenario: ProfileUpdate accepts partial update (only nombre)
- **WHEN** `ProfileUpdate(nombre="Ana")` is instantiated
- **THEN** `model.nombre` equals `"Ana"`
- **THEN** `model.apellido` is `None`

#### Scenario: ProfileUpdate rejects nombre exceeding 80 chars
- **WHEN** `ProfileUpdate(nombre="A" * 81)` is instantiated
- **THEN** a `ValidationError` is raised

---

### Requirement: PasswordChangeRequest schema
`backend/app/schemas/profile.py` SHALL define `PasswordChangeRequest(BaseModel)` with:
- `model_config = ConfigDict(extra="forbid")` — `PasswordChangeRequest` is a security schema. Extra fields (e.g., `password_confirm` sent by a misconfigured client) SHALL be rejected with HTTP 422 Unprocessable Entity. This is intentional: `password_confirm` is a frontend-only UX field and MUST NOT be sent to the backend; if it arrives it signals a frontend implementation error that should be visible rather than silently ignored.
- `current_password: str`
- `new_password: str = Field(min_length=8)` with a `@field_validator` that reuses the canonical password validation logic from Change 06 (minimum 8 characters). The validator SHALL be the same function as used in `RegisterRequest` — extracted to `backend/app/core/validators.py` as `validate_password(value: str) -> str` if not already there.

The `password_confirm` field SHALL NOT exist on this schema. It is a frontend-only UX concern and MUST NOT be sent to the backend.

#### Scenario: PasswordChangeRequest validates new_password minimum length
- **WHEN** `PasswordChangeRequest(current_password="old", new_password="short")` is instantiated with `new_password` length < 8
- **THEN** a `ValidationError` is raised

#### Scenario: PasswordChangeRequest accepts valid passwords
- **WHEN** `PasswordChangeRequest(current_password="OldPass1", new_password="NewPass1")` is instantiated
- **THEN** no `ValidationError` is raised
- **THEN** `request.current_password` equals `"OldPass1"`

---

### Requirement: RefreshTokenRepository gains revoke_all_for_user method
`backend/app/repositories/user.py` `RefreshTokenRepository` SHALL add:

`revoke_all_for_user(user_id: uuid.UUID) -> int` — sets `revoked_at = now_utc()` on ALL `RefreshToken` rows WHERE `usuario_id == user_id` AND `revoked_at IS NULL`. Returns the count of revoked rows. No `session.commit()` — the method MUST call `await self.session.flush()` explicitly after the bulk UPDATE, equal to how `revoke_family` handles it. `BaseRepository` does not guarantee automatic flush for bulk UPDATE operations that do not go through `add()` — the explicit flush is required to make the changes visible within the current transaction before the UoW commits.

#### Scenario: revoke_all_for_user revokes all active tokens for a user
- **WHEN** a user has three active `RefreshToken` rows (different family_ids) and one already revoked
- **WHEN** `revoke_all_for_user(user_id)` is called
- **THEN** all three active tokens have `revoked_at` set to a non-null timestamp after flush
- **THEN** the method returns `3`
- **THEN** the already-revoked token is unchanged

#### Scenario: revoke_all_for_user returns 0 when no active tokens exist
- **WHEN** a user has no active refresh tokens
- **WHEN** `revoke_all_for_user(user_id)` is called
- **THEN** no error is raised
- **THEN** the method returns `0`

---

### Requirement: ProfileService.update_profile
`backend/app/services/profile.py` SHALL define a `ProfileService` class with:

`@staticmethod async update_profile(uow: UnitOfWork, user_id: uuid.UUID, data: ProfileUpdate) -> UserRead`

Logic:
1. Fetch the `Usuario` by `user_id` via `uow.users.get(user_id)`. If not found, raise `NotFoundError(code="USER_NOT_FOUND")`.
2. Apply non-None fields from `data` to the model (`model_fields_set` pattern — only fields explicitly provided).
3. Persist via repository update. Return `UserRead.model_validate(user)`.
4. If `data` has no non-None fields, return current `UserRead` without a DB write (idempotent no-op).
5. SHALL NOT call `session.commit()` directly.

#### Scenario: update_profile updates nombre successfully
- **WHEN** `update_profile(uow, user_id, ProfileUpdate(nombre="Nuevo"))` is called
- **THEN** the returned `UserRead.nombre` equals `"Nuevo"`
- **THEN** the `Usuario` row in DB has `nombre="Nuevo"` after UoW commit

#### Scenario: update_profile with all-None payload is a no-op
- **WHEN** `update_profile(uow, user_id, ProfileUpdate())` is called
- **THEN** the returned `UserRead` matches the current user data
- **THEN** no database write occurs

#### Scenario: update_profile raises 404 for unknown user_id
- **WHEN** `update_profile(uow, non_existent_uuid, ProfileUpdate(nombre="X"))` is called
- **THEN** `NotFoundError` with `code="USER_NOT_FOUND"` is raised

---

### Requirement: ProfileService.change_password — transactional atomic password change
`backend/app/services/profile.py` `ProfileService` SHALL define:

`@staticmethod async change_password(uow: UnitOfWork, user_id: uuid.UUID, data: PasswordChangeRequest) -> None`

**Transactional constraint**: The entire operation (verify current password, update hash, revoke tokens) MUST occur within the SAME `UnitOfWork` context passed by the router. This ensures atomicity: if any step fails, the entire operation rolls back.

Logic:
1. Fetch `Usuario` by `user_id`. If not found, raise `NotFoundError(code="USER_NOT_FOUND")`.
2. Verify: `bcrypt.checkpw(data.current_password.encode(), user.password_hash.encode())`. If False, raise `ConflictError(code="CURRENT_PASSWORD_MISMATCH")` (HTTP 409).
3. Hash new password: `bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt(rounds=12)).decode()`.
4. Update `user.password_hash` in DB.
5. Call `uow.refresh_tokens.revoke_all_for_user(user_id)`.
6. Return `None`.
7. SHALL NOT call `session.commit()` directly.

#### Scenario: change_password updates hash and revokes all tokens atomically
- **WHEN** `change_password(uow, user_id, PasswordChangeRequest(current_password="Old1234!", new_password="New5678!"))` is called
- **THEN** `usuario.password_hash` is updated with a new bcrypt hash
- **THEN** all active `RefreshToken` rows for `user_id` have `revoked_at` set
- **THEN** both changes are committed in the same transaction

#### Scenario: change_password rolls back if revoke_all_for_user fails
- **WHEN** the DB raises an error during `revoke_all_for_user`
- **THEN** the password hash update is also rolled back (UoW rollback)
- **THEN** the database is in its original state

#### Scenario: change_password raises 409 on wrong current_password
- **WHEN** `change_password(uow, user_id, PasswordChangeRequest(current_password="WrongPass!", new_password="New5678!"))` is called
- **THEN** `ConflictError` with `code="CURRENT_PASSWORD_MISMATCH"` is raised (HTTP 409)
- **THEN** no database writes occur

---

### Requirement: PATCH /api/v1/profile/me endpoint
`backend/app/api/v1/profile.py` SHALL define `PATCH /profile/me` with:
- `response_model=UserRead`, `status_code=200`.
- Body: `ProfileUpdate`.
- Dependency: `current_user: Usuario = Depends(get_current_user)` — JWT is the only credential; `user_id` is NEVER accepted as a path or body parameter.
- Delegates to `ProfileService.update_profile(uow, current_user.id, data)`.
- Returns the updated `UserRead`.

#### Scenario: PATCH /profile/me updates nombre for authenticated user
- **WHEN** an authenticated CLIENT sends `PATCH /api/v1/profile/me` with `{"nombre": "Carlos"}`
- **THEN** HTTP 200 is returned
- **THEN** the response body is `UserRead` with `nombre="Carlos"`

#### Scenario: PATCH /profile/me ignores email field
- **WHEN** an authenticated CLIENT sends `PATCH /api/v1/profile/me` with `{"email": "new@test.com", "nombre": "Carlos"}`
- **THEN** HTTP 200 is returned
- **THEN** the response `email` field is unchanged from the original
- **THEN** `nombre` is updated to `"Carlos"`

#### Scenario: PATCH /profile/me returns 401 without valid JWT
- **WHEN** `PATCH /api/v1/profile/me` is called without `Authorization` header
- **THEN** HTTP 401 is returned

---

### Requirement: POST /api/v1/profile/me/password endpoint with rate limiting
`backend/app/api/v1/profile.py` SHALL define `POST /profile/me/password` with:
- `response_model=None`, `status_code=204`.
- Body: `PasswordChangeRequest`.
- Dependency: `current_user: Usuario = Depends(get_current_user)`.
- Rate limit: `@_limiter.limit("5/15minutes")` per user_id (key_func extracts user_id from `request.state`).
- Delegates to `ProfileService.change_password(uow, current_user.id, data)` inside a `UnitOfWork`.
- Returns `Response(status_code=204)`.

**Contrato de `req.state.user_id`**: La `key_func` de slowapi usa `req.state.user_id` (string del UUID del usuario). Este atributo es populado por la dependencia `get_current_user` (que DEBE ejecutarse antes del rate-limiter, garantizado por el orden de `Depends` en la firma del endpoint). El implementador DEBE asegurarse de que `get_current_user` escriba `request.state.user_id = str(current_user.id)` en su implementación. Si por alguna razón `req.state.user_id` no existe (error de dependencia), el endpoint retorna 500 antes de llegar al rate-limiter — esto es aceptable dado que `get_current_user` ya causará 401 si el JWT no es válido. Alternativamente, la key_func puede derivarse directamente del JWT del header como fallback.

#### Scenario: POST /profile/me/password succeeds with correct current_password
- **WHEN** an authenticated CLIENT sends `POST /api/v1/profile/me/password` with correct `current_password` and valid `new_password`
- **THEN** HTTP 204 is returned
- **THEN** all active `RefreshToken` rows for the user are revoked in the database

#### Scenario: POST /profile/me/password returns 409 on wrong current_password
- **WHEN** `POST /api/v1/profile/me/password` is called with an incorrect `current_password`
- **THEN** HTTP 409 is returned with body `{ "detail": "...", "code": "CURRENT_PASSWORD_MISMATCH" }`

#### Scenario: POST /profile/me/password rate limited after 5 attempts
- **WHEN** the same user sends 6 `POST /api/v1/profile/me/password` requests within 15 minutes
- **THEN** the 6th request receives HTTP 429 with `Retry-After` header

#### Scenario: POST /profile/me/password returns 422 for new_password < 8 chars
- **WHEN** `POST /api/v1/profile/me/password` is called with `new_password` of length 7
- **THEN** HTTP 422 is returned (Pydantic validation error)
