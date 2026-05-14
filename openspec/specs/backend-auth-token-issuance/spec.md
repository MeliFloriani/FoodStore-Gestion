# backend-auth-token-issuance Specification

## Purpose
TBD - created by archiving change auth-register-login. Update Purpose after archive.
## Requirements
### Requirement: hash_password and verify_password in security.py
`backend/app/core/security.py` SHALL export:
- `hash_password(plain: str) -> str` — hashes using bcrypt at `Settings.BCRYPT_COST` rounds; returns a `$2b$`-prefixed 60-character string.
- `verify_password(plain: str, hashed: str) -> bool` — returns `True` iff `bcrypt.checkpw(plain.encode(), hashed.encode())`, `False` otherwise; MUST NOT raise exceptions for invalid hash strings (catch and return `False`).

These functions SHALL use `passlib[bcrypt]` as the bcrypt implementation. The cost factor SHALL be read from `get_settings().BCRYPT_COST` at call time (not module load time), so test fixtures can override it.

#### Scenario: hash_password produces bcrypt hash
- **WHEN** `hash_password("mysecretpassword")` is called
- **THEN** the result starts with `$2b$`
- **THEN** the result is exactly 60 characters long

#### Scenario: verify_password returns True for matching plain text
- **WHEN** `verify_password("mysecretpassword", hash_password("mysecretpassword"))` is called
- **THEN** it returns `True`

#### Scenario: verify_password returns False for wrong password
- **WHEN** `verify_password("wrongpassword", hash_password("mysecretpassword"))` is called
- **THEN** it returns `False`

#### Scenario: verify_password returns False for invalid hash string (no exception)
- **WHEN** `verify_password("any", "not-a-valid-bcrypt-hash")` is called
- **THEN** it returns `False` without raising any exception

---

### Requirement: create_access_token in security.py
`backend/app/core/security.py` SHALL export `create_access_token(subject: str, expires_in: int = 1800) -> str`. It SHALL:
1. Build a payload: `{ "sub": subject, "iat": now_utc, "exp": now_utc + expires_in seconds, "type": "access" }`.
2. Sign with `Settings.SECRET_KEY.get_secret_value()` using `Settings.JWT_ALGORITHM`.
3. Return the compact JWT string.

#### Scenario: create_access_token produces a decodable JWT
- **WHEN** `create_access_token("some-uuid-string")` is called
- **THEN** the result is a string with exactly two `.` characters (JWT format)
- **THEN** decoding it with `jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])` returns a payload with `sub == "some-uuid-string"` and `type == "access"`

#### Scenario: create_access_token respects expires_in parameter
- **WHEN** `create_access_token("uid", expires_in=60)` is called
- **THEN** the decoded `exp` claim is approximately `iat + 60` (within 2 seconds tolerance)

---

### Requirement: create_refresh_token in security.py
`backend/app/core/security.py` SHALL export `create_refresh_token(subject: str, expires_in: int = 7*24*3600) -> tuple[str, str]`. It SHALL:
1. Build a payload: `{ "sub": subject, "iat": now_utc, "exp": now_utc + expires_in seconds, "type": "refresh" }`.
2. Sign with `Settings.SECRET_KEY.get_secret_value()` using `Settings.JWT_ALGORITHM`.
3. Compute `digest = hashlib.sha256(cleartext_jwt.encode()).hexdigest()`.
4. Return `(cleartext_jwt, digest)`.

The `digest` is the value to persist in `RefreshToken.token_hash`. The `cleartext_jwt` is returned to the client and MUST NOT be stored.

#### Scenario: create_refresh_token returns (jwt, sha256_hex)
- **WHEN** `create_refresh_token("some-uuid-string")` is called
- **THEN** the first element is a JWT string (contains two `.`)
- **THEN** the second element is exactly 64 lowercase hexadecimal characters
- **THEN** `hashlib.sha256(first.encode()).hexdigest() == second`

#### Scenario: create_refresh_token payload contains type refresh
- **WHEN** the returned cleartext JWT is decoded
- **THEN** the payload contains `"type": "refresh"` and `"sub": "some-uuid-string"`

---

### Requirement: BCRYPT_COST setting added to config.py
`backend/app/core/config.py` SHALL add `BCRYPT_COST: int = 12` to the `Settings` class. This field SHALL be env-overridable (Pydantic settings standard). Test suites SHALL set `BCRYPT_COST=4` to keep bcrypt fast.

#### Scenario: BCRYPT_COST defaults to 12
- **WHEN** `Settings()` is instantiated without `BCRYPT_COST` in environment
- **THEN** `settings.BCRYPT_COST` equals `12`

#### Scenario: BCRYPT_COST can be overridden for tests
- **WHEN** `BCRYPT_COST=4` is set in the test environment
- **THEN** `settings.BCRYPT_COST` equals `4`
- **THEN** `hash_password` uses cost 4 (verifiable by inspecting the hash string `$2b$04$...`)

---

### Requirement: RefreshTokenRepository extended in repositories/user.py
The existing `RefreshTokenRepository` in `backend/app/repositories/user.py` SHALL be extended with the following methods:
- `insert(token: RefreshToken) -> RefreshToken` — persists a new `RefreshToken` entity via the base `create` method (which calls `session.add + session.flush`).
- `revoke_by_hash(token_hash: str) -> bool` — sets `revoked_at = now_utc` on the matching `RefreshToken` (by `token_hash`); returns `True` if a record was found and updated, `False` otherwise.

All mutations go through the inherited session from `BaseRepository`. No direct `session.commit()` calls.

#### Scenario: insert persists a RefreshToken row
- **WHEN** `RefreshTokenRepository.insert(RefreshToken(token_hash=digest, usuario_id=uid, expires_at=exp))` is called within a UoW
- **THEN** a `RefreshToken` row with `token_hash == digest` exists in the database after commit

#### Scenario: revoke_by_hash sets revoked_at
- **WHEN** `RefreshTokenRepository.revoke_by_hash(digest)` is called for an existing unrevoked token
- **THEN** `refresh_token.revoked_at` is set to a non-null timestamp
- **THEN** the method returns `True`

#### Scenario: revoke_by_hash returns False for unknown hash
- **WHEN** `RefreshTokenRepository.revoke_by_hash("nonexistent-hash")` is called
- **THEN** the method returns `False` and no exception is raised

---

### Requirement: D-07 supersession documentation
This change supersedes design decision D-07 from Change 04 (`backend-base-patterns`). The restriction "This module SHALL NOT contain token issuance functions" is lifted. `backend/app/core/security.py` now contains both decode (`decode_access_token`) and issuance (`create_access_token`, `create_refresh_token`, `hash_password`, `verify_password`) functions. The import of `passlib[bcrypt]` and `hashlib` in `security.py` is now valid and expected.

#### Scenario: security.py contains both decode and issuance functions
- **WHEN** `backend/app/core/security.py` is statically inspected
- **THEN** it defines `decode_access_token`, `hash_password`, `verify_password`, `create_access_token`, and `create_refresh_token`
- **THEN** the existing `decode_access_token` implementation is unchanged from Change 04

