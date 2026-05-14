## MODIFIED Requirements

### Requirement: `core/security.py` — JWT decode helper
`backend/app/core/security.py` SHALL define `decode_access_token(token: str) -> dict` using `python-jose[cryptography]`. It SHALL:
1. Call `jwt.decode(token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.JWT_ALGORITHM])` with explicit `options` dict: `verify_signature=True`, `verify_exp=True`, `verify_nbf=True`, `verify_iat=True`, `verify_aud=False`, `verify_iss=False` (audience and issuer policies deferred).
2. On `JWTError` (including `ExpiredSignatureError`): raise `UnauthorizedError("Token inválido o expirado", code="invalid_token")`.
3. Return the decoded payload dict on success.

**Supersession of D-07**: This requirement now co-exists with token issuance functions in the same module. The restriction from Change 04 — "This module SHALL NOT contain token issuance functions" — is LIFTED by change `auth-register-login`. `backend/app/core/security.py` now also exports `hash_password`, `verify_password`, `create_access_token`, and `create_refresh_token` (see capability `backend-auth-token-issuance`). The import of `passlib[bcrypt]` and `hashlib` in `security.py` is valid and expected.

The `decode_access_token` implementation itself is UNCHANGED from Change 04.

#### Scenario: Valid token decodes to payload dict
- **WHEN** `decode_access_token(valid_jwt)` is called with a JWT signed with the correct `SECRET_KEY` and not expired
- **THEN** the method returns a `dict` containing at minimum the `sub` field (user UUID as string)
- **THEN** no exception is raised

#### Scenario: Expired token raises UnauthorizedError
- **WHEN** `decode_access_token(expired_jwt)` is called where the token's `exp` claim is in the past
- **THEN** `UnauthorizedError` is raised (not `JWTError` — the jose exception is wrapped)
- **THEN** the `UnauthorizedError` has `code="invalid_token"` and `status_code=401`

#### Scenario: Wrong signature raises UnauthorizedError
- **WHEN** `decode_access_token(tampered_jwt)` is called where the signature does not match `SECRET_KEY`
- **THEN** `UnauthorizedError` is raised (not a raw `JWTError`)

#### Scenario: nbf claim in the future raises UnauthorizedError
- **WHEN** `decode_access_token` is called with a token whose `nbf` is in the future
- **THEN** it raises `UnauthorizedError` (not a raw `JWTError`) and the deps layer maps it to HTTP 401

#### Scenario: options dict is passed explicitly with all verification flags
- **WHEN** `decode_access_token` is called
- **THEN** `options={"verify_signature": True, "verify_exp": True, "verify_nbf": True, "verify_iat": True, "verify_aud": False, "verify_iss": False}` is passed explicitly to `jwt.decode`

#### Scenario: security.py now contains both decode and issuance functions
- **WHEN** `backend/app/core/security.py` is statically inspected
- **THEN** it defines `decode_access_token` (unchanged), `hash_password`, `verify_password`, `create_access_token`, and `create_refresh_token`
- **THEN** the D-07 "decode-only" restriction is no longer in effect
