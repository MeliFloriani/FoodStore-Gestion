## MODIFIED Requirements

### Requirement: RefreshTokenRepository extended in repositories/user.py
The existing `RefreshTokenRepository` in `backend/app/repositories/user.py` SHALL be extended with the following methods (in addition to `insert` and `revoke_by_hash` defined in Change 06):

- `insert(token: RefreshToken) -> RefreshToken` — UNCHANGED from Change 06. Persists a new `RefreshToken` entity via the base `create` method. **Callers are now responsible for setting `family_id` on the token before calling insert.**
- `revoke_by_hash(token_hash: str) -> bool` — UNCHANGED from Change 06. Sets `revoked_at = now_utc`. Returns `True` if found and updated, `False` otherwise.
- `find_by_hash(token_hash: str) -> RefreshToken | None` — NEW. Finds a `RefreshToken` by exact hash match WITHOUT checking active status. Used for replay detection (to check if a revoked token belongs to a known family).
- `find_active_by_hash(token_hash: str) -> RefreshToken | None` — NEW. Finds a token only if `revoked_at IS NULL` AND `expires_at > now_utc`. Returns `None` otherwise.
- `create_with_family(token: RefreshToken) -> RefreshToken` — NEW. Alias for `insert` — delegates to `BaseRepository.create()`. Semantic distinction: callers use this when they are explicitly managing `family_id`.
- `revoke_family(family_id: uuid.UUID) -> int` — NEW. Sets `revoked_at = now_utc` on all rows with matching `family_id` and `revoked_at IS NULL`. Returns count of revoked rows.

All mutations go through the inherited session from `BaseRepository`. No direct `session.commit()` calls.

#### Scenario: insert persists a RefreshToken row with family_id
- **WHEN** `RefreshTokenRepository.insert(RefreshToken(token_hash=digest, usuario_id=uid, family_id=fid, expires_at=exp))` is called within a UoW
- **THEN** a `RefreshToken` row with `token_hash == digest` and `family_id == fid` exists in the database after commit

#### Scenario: revoke_by_hash sets revoked_at
- **WHEN** `RefreshTokenRepository.revoke_by_hash(digest)` is called for an existing unrevoked token
- **THEN** `refresh_token.revoked_at` is set to a non-null timestamp
- **THEN** the method returns `True`

#### Scenario: revoke_by_hash returns False for unknown hash
- **WHEN** `RefreshTokenRepository.revoke_by_hash("nonexistent-hash")` is called
- **THEN** the method returns `False` and no exception is raised

#### Scenario: find_by_hash returns token regardless of revocation status
- **WHEN** a `RefreshToken` exists with `revoked_at` set (revoked)
- **WHEN** `find_by_hash(token_hash)` is called
- **THEN** the `RefreshToken` instance is returned (revocation status is not filtered)

#### Scenario: find_active_by_hash returns None for revoked token
- **WHEN** a `RefreshToken` has `revoked_at IS NOT NULL`
- **WHEN** `find_active_by_hash(token_hash)` is called
- **THEN** `None` is returned

#### Scenario: revoke_family revokes all matching active tokens
- **WHEN** multiple `RefreshToken` rows share the same `family_id`
- **WHEN** `revoke_family(family_id)` is called
- **THEN** all rows with `revoked_at IS NULL` are updated to have `revoked_at` set
- **THEN** the count of revoked rows is returned
