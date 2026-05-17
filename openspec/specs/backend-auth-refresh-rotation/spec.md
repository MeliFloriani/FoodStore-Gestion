# backend-auth-refresh-rotation Specification

## Purpose
Define the refresh token rotation capability for the Food Store backend: atomic single-use token rotation with replay attack detection and family-level revocation. Includes the `family_id` data model extension, new repository methods, `AuthService.rotate_refresh` service logic, and the `POST /api/v1/auth/refresh` endpoint with rate limiting. The critical design decision (D-07-C) is that replay revocation happens in a SECOND independent UoW — never within the service's UoW — to guarantee commits persist even when the router raises an error response.

## Requirements

### Requirement: RefreshToken model gains family_id field
`backend/app/models/user.py` SHALL add `family_id: uuid.UUID` to the `RefreshToken` SQLModel with `nullable=False` and a database-level index. The field SHALL be declared using a `Column` with `ForeignKey` omitted (it is a grouping key, not a self-referential FK).

A new Alembic migration SHALL add the `family_id` column to the `refresh_token` table with `server_default=text("gen_random_uuid()")` to backfill existing rows (PostgreSQL 13+). After the migration is stable the `server_default` may be removed in a subsequent migration.

#### Scenario: RefreshToken model exposes family_id
- **WHEN** `RefreshToken` is instantiated with `family_id=some_uuid`
- **THEN** `refresh_token.family_id` equals `some_uuid`
- **THEN** the SQLAlchemy column is mapped as `UUID` type in PostgreSQL

#### Scenario: Alembic migration adds family_id column
- **WHEN** `alembic upgrade head` is run against a database that has the previous schema
- **THEN** the `refresh_token` table gains a `family_id` column of type `UUID NOT NULL`
- **THEN** existing rows receive a generated UUID value (server_default)

---

### Requirement: RefreshTokenRepository extended for rotation and family management
`backend/app/repositories/user.py` `RefreshTokenRepository` SHALL add the following methods:

- `find_active_by_hash(token_hash: str) -> RefreshToken | None` — returns the token only if `revoked_at IS NULL` AND `expires_at > now_utc`. Returns `None` if not found, revoked, or expired.
- `find_by_hash(token_hash: str) -> RefreshToken | None` — finds by hash without active check — used for replay detection.
- `create_with_family(token: RefreshToken) -> RefreshToken` — delegates to `BaseRepository.create()`. Caller is responsible for setting `family_id` before calling.
- `revoke_family(family_id: uuid.UUID) -> int` — sets `revoked_at = now_utc` on ALL `RefreshToken` rows with `family_id == family_id` WHERE `revoked_at IS NULL`. Returns the count of revoked rows.

No `session.commit()` calls — all mutations go through `session.flush()` inherited from `BaseRepository`.

#### Scenario: find_active_by_hash returns token for valid unrevoked unexpired hash
- **WHEN** `find_active_by_hash(hash)` is called with a hash that matches an active token
- **THEN** the `RefreshToken` instance is returned
- **THEN** its `revoked_at` is `None` and `expires_at` is in the future

#### Scenario: find_active_by_hash returns None for revoked token
- **WHEN** a `RefreshToken` row has `revoked_at` set to a non-null timestamp
- **WHEN** `find_active_by_hash(hash)` is called with its hash
- **THEN** `None` is returned

#### Scenario: find_active_by_hash returns None for expired token
- **WHEN** a `RefreshToken` row has `expires_at` in the past
- **WHEN** `find_active_by_hash(hash)` is called with its hash
- **THEN** `None` is returned

#### Scenario: revoke_family revokes all active tokens with matching family_id
- **WHEN** three `RefreshToken` rows share the same `family_id` and all have `revoked_at IS NULL`
- **WHEN** `revoke_family(family_id)` is called
- **THEN** all three rows have `revoked_at` set to a non-null timestamp after flush
- **THEN** the method returns `3`

#### Scenario: revoke_family is a no-op for already-revoked tokens
- **WHEN** all `RefreshToken` rows with a `family_id` already have `revoked_at` set
- **WHEN** `revoke_family(family_id)` is called
- **THEN** no error is raised
- **THEN** the method returns `0`

---

### Requirement: AuthService.rotate_refresh implements atomic token rotation

`backend/app/services/auth.py` SHALL define `AuthService.rotate_refresh(uow: UnitOfWork, refresh_token_cleartext: str, ip: str, user_agent: str) -> TokenResponse` as a `@staticmethod`.

**Critical transactional constraint**: The service MUST NOT call `revoke_family()` and then raise an exception within the SAME UoW. Reason: UoW `__aexit__` calls `rollback()` on any exception — any mutations (including `revoke_family`) within the same UoW context would be rolled back and never persisted.

**Replay detection flow** (see D-07-C for full rationale):
- The service raises a domain exception `TokenReplayError(family_id, user_id)` — NOT `UnauthorizedError` — when a replay is detected.
- `TokenReplayError` must be defined in `backend/app/core/exceptions.py` as a non-HTTP exception (not a subclass of `HTTPException`).
- The router catches `TokenReplayError` and performs the revocation in a SECOND independent UoW (see router requirement below).

**Steps within the service** (inside the provided `uow` context — single transaction):
1. Compute `token_hash = hashlib.sha256(refresh_token_cleartext.encode()).hexdigest()`.
2. Call `uow.refresh_tokens.find_active_by_hash(token_hash)`. If `None`:
   - Call `uow.refresh_tokens.find_by_hash(token_hash)` to check if token is known.
   - If found with `revoked_at IS NOT NULL` → **replay detected**: raise `TokenReplayError(family_id=token.family_id, user_id=token.usuario_id)`. DO NOT call `revoke_family` here — the UoW would roll it back.
   - If found with `revoked_at IS NULL` but expired → raise `UnauthorizedError(code="token_expired")`. Do NOT revoke family (expired, not compromised).
   - If not found at all → raise `UnauthorizedError(code="invalid_token")`.
3. Revoke the current token: `uow.refresh_tokens.revoke_by_hash(token_hash)`.
4. Issue new access token: `create_access_token(str(token.usuario_id))`.
5. Issue new refresh token: `cleartext_new, digest_new = create_refresh_token(str(token.usuario_id))`.
6. Persist new token: `uow.refresh_tokens.create_with_family(RefreshToken(token_hash=digest_new, usuario_id=token.usuario_id, family_id=token.family_id, expires_at=now+7days))`.
7. Return `TokenResponse(access_token=..., refresh_token=cleartext_new)`.

SHALL NOT call `session.commit()`. For `UnauthorizedError` (expired/invalid), SHALL raise directly. For replay, SHALL raise `TokenReplayError` — the router handles revocation and then re-raises as `UnauthorizedError`.

#### Scenario: Successful rotation returns new TokenResponse and revokes old token
- **WHEN** `rotate_refresh(uow, valid_cleartext_refresh, ip, user_agent)` is called
- **THEN** the old `RefreshToken` row has `revoked_at` set
- **THEN** a new `RefreshToken` row exists with the same `family_id` and `revoked_at IS NULL`
- **THEN** the returned `TokenResponse` has `access_token` and `refresh_token` as non-empty strings
- **THEN** the returned `refresh_token` hashes to the new row's `token_hash`

#### Scenario: Replay attack revokes entire family and returns 401
- **WHEN** a refresh token that has already been rotated (old, revoked) is presented again
- **WHEN** `rotate_refresh(uow, already_rotated_cleartext, ip, user_agent)` is called
- **THEN** `TokenReplayError` is raised by the service (NOT `UnauthorizedError` — this is intentional)
- **THEN** the router catches `TokenReplayError`, opens a SECOND UoW, calls `revoke_family(family_id)` within it, commits successfully
- **THEN** the router logs WARNING with `user_id`, `family_id`, `ip`, `user_agent`
- **THEN** the router raises `UnauthorizedError(code="token_replay_detected")` → HTTP 401 is returned
- **THEN** ALL `RefreshToken` rows with the same `family_id` have `revoked_at` set (including the currently-active successor) — verified via the committed second UoW
- **THEN** the revocation persists in the database (not rolled back), because it was committed in the second UoW before the 401 response is sent

#### Scenario: Unknown token hash returns 401 invalid_token
- **WHEN** `rotate_refresh(uow, completely_unknown_cleartext, ip, user_agent)` is called
- **THEN** `UnauthorizedError` is raised with `code="invalid_token"`
- **THEN** no rows are modified

#### Scenario: Expired token (not in active set) raises invalid_token not replay
- **WHEN** a token whose `expires_at` is in the past and `revoked_at IS NULL` is presented
- **WHEN** `find_active_by_hash` returns `None` (expired check)
- **WHEN** `find_by_hash` returns the row (exists but inactive)
- **THEN** the service distinguishes expired-but-not-revoked from replay:
  - If `revoked_at IS NOT NULL` → replay detected (revoke family)
  - If `revoked_at IS NULL` but expired → raise `UnauthorizedError(code="token_expired")` — do NOT revoke family

---

### Requirement: POST /api/v1/auth/refresh endpoint with rate limiting
`backend/app/api/v1/auth.py` SHALL define `POST /auth/refresh` with:
- `response_model=TokenResponse`, `status_code=200`.
- Body: `RefreshRequest` schema with `refresh_token: str`.
- Rate limit: `30/15minutes` per IP via `@_limiter.limit("30/15minutes")`.
- Delegates to `AuthService.rotate_refresh(uow, data.refresh_token, _get_client_ip(request), request.headers.get("user-agent", ""))`.
- No `Depends(get_current_user)` — the refresh token IS the credential.
- **MUST catch `TokenReplayError`** (raised by `rotate_refresh`) and handle it in a second UoW (see D-07-C):
  ```python
  except TokenReplayError as e:
      async with UnitOfWork() as uow2:
          await uow2.refresh_tokens.revoke_family(e.family_id)
      logger.warning("auth.replay_detected", user_id=str(e.user_id), family_id=str(e.family_id), ip=_get_client_ip(request))
      raise UnauthorizedError("Sesión comprometida", code="token_replay_detected")
  ```

#### Scenario: Valid refresh token returns 200 TokenResponse
- **WHEN** `POST /api/v1/auth/refresh` is called with a valid, unrevoked, unexpired refresh token
- **THEN** HTTP 200 is returned
- **THEN** the body is `{ access_token, refresh_token, token_type: "bearer", expires_in: 1800 }`
- **THEN** the old refresh token is revoked in the database
- **THEN** a new refresh token row with the same `family_id` exists

#### Scenario: Replay attack returns 401 with family revoked
- **WHEN** a previously-rotated (already revoked) refresh token is presented
- **THEN** HTTP 401 is returned with `code="token_replay_detected"`
- **THEN** the entire token family is revoked in the database (committed via second UoW in the router before the 401 response is sent)
- **THEN** a subsequent refresh attempt with any token from the same family also returns 401 (family fully revoked)

#### Scenario: Rate limit returns 429 after 30 attempts
- **WHEN** the same IP sends more than 30 `POST /api/v1/auth/refresh` requests within 15 minutes
- **THEN** subsequent requests receive HTTP 429 with `Retry-After` header

#### Scenario: Refresh schema RefreshRequest is validated
- **WHEN** `POST /api/v1/auth/refresh` is called with a missing `refresh_token` field
- **THEN** HTTP 422 is returned

---

### Requirement: _get_client_ip helper — null-safe IP resolution
`backend/app/api/v1/auth.py` (or a shared utility `backend/app/api/utils.py`) SHALL define:

```python
def _get_client_ip(request: Request) -> str:
    """Resolve client IP with X-Forwarded-For support and null-safe fallback.

    Used for rate limiting and audit logging only — not for authorization.
    X-Forwarded-For may be spoofed if the app is not behind a trusted proxy.
    For Sprint 1 this is acceptable: the rate limiter exists and IP is for
    audit/logging purposes only, not for access control decisions.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

This helper SHALL be used in the `/auth/refresh` endpoint instead of `request.client.host` directly. If placed in a shared utility module, it MAY also be used by `/auth/login` and other endpoints that log client IP for audit.

**Rationale**: Behind reverse proxies (Railway, Render, Fly.io, nginx), `request.client` may be `None` because the proxy does not forward the original socket address as a FastAPI `Request.client`. Using `request.client.host` directly causes an `AttributeError` → HTTP 500. The `X-Forwarded-For` header contains the original client IP set by the proxy.

#### Scenario: _get_client_ip returns X-Forwarded-For when present
- **WHEN** the request has `X-Forwarded-For: 203.0.113.5, 10.0.0.1`
- **THEN** `_get_client_ip(request)` returns `"203.0.113.5"` (first entry)

#### Scenario: _get_client_ip falls back to client.host when no header
- **WHEN** the request has no `X-Forwarded-For` header and `request.client.host` is `"127.0.0.1"`
- **THEN** `_get_client_ip(request)` returns `"127.0.0.1"`

#### Scenario: _get_client_ip returns unknown when client is None
- **WHEN** `request.client` is `None` and no `X-Forwarded-For` header is present
- **THEN** `_get_client_ip(request)` returns `"unknown"` without raising an exception

---

### Requirement: login_user seeds family_id on first token issuance
`backend/app/services/auth.py` `AuthService.login_user` SHALL be updated: when persisting the `RefreshToken` row, it SHALL generate `family_id = uuid.uuid4()` and include it in the `RefreshToken` constructor.

#### Scenario: Login creates RefreshToken with family_id
- **WHEN** `POST /api/v1/auth/login` succeeds
- **THEN** the inserted `RefreshToken` row has a non-null `family_id` (a UUID)
- **THEN** the `family_id` is unique per login call (new UUID each time)

---

### Requirement: RefreshRequest schema
`backend/app/schemas/auth.py` SHALL define `RefreshRequest(BaseModel)` with `refresh_token: str`. This schema is used as the body for `POST /api/v1/auth/refresh`.

#### Scenario: RefreshRequest accepts string refresh_token
- **WHEN** `RefreshRequest(refresh_token="some.jwt.string")` is instantiated
- **THEN** `request.refresh_token` equals `"some.jwt.string"`

#### Scenario: RefreshRequest rejects missing field
- **WHEN** `RefreshRequest()` is instantiated without `refresh_token`
- **THEN** a `ValidationError` is raised
