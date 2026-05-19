## Context

Change 07 (`auth-refresh-logout-rbac-me`) shipped a complete auth session lifecycle: JWT emission, refresh rotation with replay detection, logout, RBAC, and `GET /api/v1/auth/me`. Change 13 builds directly on top of that infrastructure to deliver the customer profile self-management layer.

**Current state**:
- `GET /api/v1/auth/me` already returns the authenticated user's `UserRead` (id, email, nombre, apellido, roles). No change needed.
- `Usuario` model fields: `id` (UUID), `email` (str, unique, immutable identifier), `nombre` (str, max 80), `apellido` (str, max 80), `password_hash` (CHAR 60 bcrypt). **No `telefono` field exists** — excluded from scope.
- `RefreshToken` model: `token_hash`, `usuario_id`, `family_id`, `expires_at`, `revoked_at`. The `revoke_family(family_id)` method revokes by family. A new method `revoke_all_for_user(user_id)` will revoke all active tokens for a user.
- Frontend placeholder `/profile` route already registered in Change 08 — ready to be replaced.

**Stack**:
- Backend: FastAPI + SQLModel + PostgreSQL. Feature-First: `Router → Service → UoW → Repository → Model`. Pydantic v2 schemas Read/Create/Update. RFC 7807 errors `{ detail, code, field? }`.
- Frontend: React 19 + TS strict + Vite + Tailwind tokens + FSD. TanStack Query 5. Zustand (`authStore`). TanStack Form. Axios with refresh-queue interceptor.

---

## Goals / Non-Goals

**Goals:**
- Expose `PATCH /api/v1/profile/me` to update editable fields (`nombre`, `apellido`).
- Expose `POST /api/v1/profile/me/password` to change password with current-password verification and global session revocation.
- Frontend `/profile` page with two fully decoupled forms and proper UX states.
- All validations consistent between FE (TanStack Form) and BE (Pydantic v2).
- Transactional atomicity for password change: hash update + token revocation in single UoW.

**Non-Goals:**
- Phone number (`telefono`) — field does not exist in the current `Usuario` model; excluded.
- Avatar upload, preferences, 2FA, session audit — architecture left open, not implemented.
- Admin user management (`/users/{id}`) — reserved for Change 21.
- New RBAC roles — CLIENT role is sufficient; `get_current_user` is the only dependency.
- New package dependencies — all required libraries shipped in Changes 06/07.

---

## Decisions

### D-01 — New `profile/` module instead of extending `auth/`

**Decision**: Create a new module `backend/app/api/v1/profile.py` with router prefix `/api/v1/profile/*`.

**Tradeoff**: Auth manages sessions/tokens (who you are, how long the session lives). Profile manages user data (what your data says). Mixing them inflates the `auth` module and blurs the boundary. A separate `profile/` module gives clean ownership: `auth/*` = session lifecycle, `profile/*` = user data lifecycle.

**Alternative rejected**: Adding `PATCH /auth/me` and `POST /auth/me/password` to the auth router. Rejected because auth endpoints are already rate-limited and monitored differently, and adding data-mutation semantics there would create confusion at archive time and in audit logs.

---

### D-02 — `email` is silently ignored in PATCH body (not rejected)

**Decision**: `ProfileUpdate` Pydantic schema uses `model_config = ConfigDict(extra='ignore')`. If `email` appears in the PATCH body, it is stripped before the service processes the update. The server returns 200 with the current (unchanged) `UserRead`. No 400 error is raised.

**Rationale**: Returning a 400 on `email` in the body would leak information about which fields are immutable, potentially useful for enumeration. Silent ignore is the least-surprising behavior for a client that sends the entire user object back in a PATCH request.

**Alternative considered**: Return `400 Bad Request` with `code="EMAIL_IMMUTABLE"`. Rejected — no security or correctness benefit; adds client-side defensive coding without value.

---

### D-03 — Password change returns 409 on current_password mismatch

**Decision**: `POST /api/v1/profile/me/password` returns `HTTP 409 Conflict` with `code="CURRENT_PASSWORD_MISMATCH"` when bcrypt comparison fails.

**Rationale**: 409 is semantically correct — the request cannot be fulfilled because the provided credential conflicts with the current state. 401 would imply the JWT is invalid. 403 would imply a role mismatch. 409 is precise and is consistent with the project's RFC 7807 convention of using status codes for domain-specific conflicts.

**Error table**:
| Condition | HTTP Status | code |
|---|---|---|
| JWT missing or invalid | 401 | (from `get_current_user`) |
| `current_password` wrong | 409 | `CURRENT_PASSWORD_MISMATCH` |
| Validation failure | 422 | (Pydantic) |
| User not found (race) | 404 | `USER_NOT_FOUND` |

---

### D-04 — Residual access token window after password change

**Decision**: Accept Option (a) — the current access token (30 min TTL) remains valid after a password change. No `password_changed_at` claim is introduced.

**Rationale**: Access tokens in this system are short-lived (30 min). The probability of a compromised access token being actively exploited in a 30-minute window post-password-change is low relative to the implementation complexity of Option (b). Option (b) would require:
1. Adding a `password_changed_at` field to `Usuario`.
2. Embedding it in the JWT payload or checking it on every authenticated request via DB lookup (killing the stateless property of JWTs).
3. A new migration.

This trade-off is documented and accepted. The session-revocation on all refresh tokens means the attacker cannot silently obtain a new access token after the current one expires.

**Documentation**: The profile spec explicitly states this residual window exists. Future Change 21 (admin user management) may introduce forced token expiry at the user level if the risk model changes.

---

### D-05 — `revoke_all_for_user` revokes ALL tokens, not by family

**Decision**: `change_password` revokes every `RefreshToken` row for `usuario_id` where `revoked_at IS NULL`, regardless of `family_id`. This is different from `revoke_family` (which is family-scoped for replay detection).

**Rationale**: Password change is a voluntary security action — the user explicitly wants all other sessions terminated. All-user revocation is the correct semantic. Family-scoped revocation would only close the current session's family, leaving other devices logged in. US-063 AC explicitly states "Se invalidan todos los refresh tokens existentes".

**Interaction with replay detection**: After `revoke_all_for_user`, a subsequent `/auth/refresh` call with any of those tokens finds `revoked_at IS NOT NULL`. The existing `/auth/refresh` router logic hits `find_active_by_hash → None`, then `find_by_hash → token with revoked_at set`, and raises `TokenReplayError`. However, `revoke_all_for_user` already revoked all families — there is nothing new to revoke. The router's second UoW calls `revoke_family(family_id)` which becomes a no-op (0 rows affected). This is benign, documented, and requires no code change in the refresh flow. The client receives `401 token_replay_detected` which, while technically imprecise, is the correct behavior (reject the refresh, force re-login). A dedicated `code="TOKEN_REVOKED_BY_PASSWORD_CHANGE"` is out of scope for this change.

**Nota de monitoreo:** Los registros de `token_replay_detected` generados por llamadas a `POST /auth/refresh` con tokens revocados por `revoke_all_for_user` son **comportamiento esperado y normal**, no un indicador de ataque real. Cada vez que un usuario cambia su contraseña con sesiones activas en otras tabs, el siguiente intento de renovación de esas sesiones producirá un `token_replay_detected` con 0 filas revocadas por la segunda UoW. Los sistemas de alerta y monitoreo deben configurarse para distinguir este caso (contexto: `profile/password change`) de un replay genuino.

---

### D-06 — Rate limiting on `POST /profile/me/password`: 5/15min per user_id

**Decision**: Rate limit is per `user_id` extracted from the JWT, not per IP.

**Rationale**: Per-IP rate limiting is trivial to bypass with dynamic IPs. Password change is a sensitive operation; per-user limiting mirrors the login rate-limit strategy and is consistent with the project's slowapi usage. The limit of 5/15min matches the login rate limit (RN-AU06), providing symmetry across sensitive auth operations.

Implementation: `@_limiter.limit("5/15minutes", key_func=lambda req: str(req.state.user_id))` where `req.state.user_id` is injected by `get_current_user` dependency.

**Precondición del rate-limiter**: `get_current_user` DEBE poblar `request.state.user_id = str(user.id)`. El implementador debe verificar que la dependencia de auth existente ya lo hace o añadirlo explícitamente. Si por alguna razón `req.state.user_id` no existe (error de dependencia), el endpoint retorna 500 antes de llegar al rate-limiter — esto es aceptable dado que `get_current_user` ya causará 401 si el JWT no es válido.

---

### D-07 — Password validator reuse from Change 06

**Decision**: The Pydantic `@field_validator` for `new_password` in `PasswordChangeRequest` SHALL reuse the same validation logic as `RegisterRequest.password` from `backend/app/schemas/auth.py`. If the validator is defined as a standalone function, import it. If it is inline in the schema class, extract it to `backend/app/core/validators.py` as a reusable function.

**Constraint**: No duplication of the `min 8 chars` rule. Single source of truth in the backend; frontend replicates the rule locally for UX but the backend is authoritative.

---

### D-08 — Sin locking explícito en `change_password`

**Decision**: La operación `change_password` no aplica `SELECT FOR UPDATE` ni nivel de aislamiento `SERIALIZABLE`. El sistema opera con `READ COMMITTED` (default de PostgreSQL).

**Escenarios de race analizados y aceptados:**
- Cambio de contraseña concurrente con refresh activo en otra tab: en READ COMMITTED, el token puede ser renovado antes de que `revoke_all_for_user` commitee. La ventana de race es de milisegundos para una operación infrecuente. El estado final siempre es seguro (el token recién emitido por la rotación queda revocado tras el commit de `change_password`).
- Dos `change_password` simultáneos del mismo usuario: `last-writer-wins` en el UPDATE de `password_hash`. Ambas revocaciones son idempotentes. El sistema queda en estado coherente.

**Justificación**: las queries de revocación usan `WHERE revoked_at IS NULL` (idempotentes), el UoW garantiza atomicidad interna, y la probabilidad e impacto de estas races son despreciables. Agregar locking añadiría complejidad y contención sin beneficio de seguridad tangible para este dominio.

---

## API Contracts

### Read Profile (existing, no change)
```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
→ 200 UserRead
```

### Update Profile
```
PATCH /api/v1/profile/me
Authorization: Bearer <access_token>
Content-Type: application/json

Request body (ProfileUpdate):
{
  "nombre": "string (optional, max 80 chars)",
  "apellido": "string (optional, max 80 chars)"
}
Note: "email" field, if present, is silently ignored.

Response 200 (UserRead):
{
  "id": "uuid",
  "email": "string",
  "nombre": "string",
  "apellido": "string",
  "roles": ["string"]
}

Error responses (RFC 7807):
  401 → JWT missing/invalid (get_current_user)
  422 → Pydantic validation error
```

### Change Password
```
POST /api/v1/profile/me/password
Authorization: Bearer <access_token>
Content-Type: application/json

Request body (PasswordChangeRequest):
{
  "current_password": "string",
  "new_password": "string (min 8 chars, same rules as registration)"
}
Note: "password_confirm" exists only on the frontend, NEVER sent to backend.

Response 204 No Content

Error responses (RFC 7807):
  401 → JWT missing/invalid
  409 → current_password mismatch  { detail: "...", code: "CURRENT_PASSWORD_MISMATCH" }
  422 → Pydantic validation (e.g., new_password < 8 chars)
  429 → Rate limit exceeded (5/15min per user)
```

---

## Schemas (Pydantic v2)

```python
# backend/app/schemas/profile.py

class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='ignore')
    nombre: str | None = Field(default=None, max_length=80)
    apellido: str | None = Field(default=None, max_length=80)

class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str
    new_password: str = Field(min_length=8)
    # @field_validator('new_password') reuses validator from auth schemas

# UserRead — reutilizar el existente de backend/app/schemas/auth.py
# No duplicar: importar UserRead desde schemas/auth.py
```

**Decisión arquitectónica — `UserRead` reuse**: `UserRead` se REUTILIZA desde `backend/app/schemas/auth.py`. No se re-declara en `schemas/profile.py`. Esto garantiza que los contratos de `GET /auth/me` y `PATCH /profile/me` (su respuesta) sean idénticos por construcción, eliminando riesgo de drift. El import es unidireccional (`profile → auth schemas`) y no genera dependencia circular.

---

## Sequence Diagram — Password Change Flow

```
Client                 Frontend              Backend                 PostgreSQL
  │                      │                      │                         │
  │  fill form ─────────►│                      │                         │
  │  submit ─────────────►│                     │                         │
  │                      │─POST /profile/me/password──────────────────────►│
  │                      │                      │  get_current_user (JWT) │
  │                      │                      │◄────────────────────────│
  │                      │                      │                         │
  │                      │                      │  async with UnitOfWork():
  │                      │                      │    find user by id      │
  │                      │                      │◄────────────────────────│
  │                      │                      │    bcrypt.checkpw(      │
  │                      │                      │      current_password,  │
  │                      │                      │      user.password_hash)│
  │                      │                      │  [if mismatch → 409]    │
  │                      │                      │    hash new_password    │
  │                      │                      │    UPDATE usuario       │
  │                      │                      │────────────────────────►│
  │                      │                      │    revoke_all_for_user  │
  │                      │                      │    UPDATE refresh_token │
  │                      │                      │      SET revoked_at=now │
  │                      │                      │      WHERE user_id=X    │
  │                      │                      │      AND revoked_at IS  │
  │                      │                      │      NULL               │
  │                      │                      │────────────────────────►│
  │                      │                      │    UoW commits          │
  │                      │                      │◄────────────────────────│
  │                      │◄──────────────────────│  204 No Content        │
  │                      │                      │                         │
  │                      │  mutation onSuccess:                           │
  │                      │    toast("Contraseña cambiada")                │
  │                      │    await POST /auth/logout (best-effort)       │
  │                      │    authStore.logout()                          │
  │                      │    navigate('/login')                          │
  │◄─────────────────────│  redirect to /login                           │
```

---

## Module Structure

```
backend/app/
├── schemas/
│   └── profile.py          ← ProfileUpdate, PasswordChangeRequest
├── services/
│   └── profile.py          ← ProfileService (@staticmethod: update_profile, change_password)
├── repositories/
│   └── user.py             ← RefreshTokenRepository + revoke_all_for_user (additive)
└── api/v1/
    ├── profile.py          ← profile_router (PATCH /me, POST /me/password)
    └── router.py           ← include_router(profile_router, prefix="/profile")

frontend/src/
├── pages/
│   └── ProfilePage/
│       └── index.tsx       ← Composes EditProfileForm + ChangePasswordForm
├── features/
│   └── profile/
│       ├── EditProfileForm.tsx
│       ├── ChangePasswordForm.tsx
│       ├── hooks/
│       │   ├── useUpdateProfile.ts
│       │   └── useChangePassword.ts
│       └── index.ts        ← barrel export
└── shared/api/
    └── endpoints.ts        ← PROFILE_ME, PROFILE_ME_PASSWORD (additive)
```

---

## Shared FE/BE Validation Strategy

The backend is the single source of truth for validation rules. The frontend replicates them locally for instant UX feedback but the backend always wins on conflict.

| Field | Rule | Backend (Pydantic) | Frontend (TanStack Form) |
|---|---|---|---|
| `nombre` | max 80 chars | `Field(max_length=80)` | `z.string().max(80)` or inline validator |
| `apellido` | max 80 chars | `Field(max_length=80)` | same |
| `new_password` | min 8 chars | `Field(min_length=8)` + custom validator | min length check |
| `password_confirm` | equals `new_password` | NOT sent to backend | client-only equality check |
| `email` | immutable | ignored by Pydantic (`extra='ignore'`) | field shown as disabled/readonly |

---

## Error Handling — HTTP Status → UI State Mapping

| HTTP Status | code | UI State |
|---|---|---|
| 200/204 | — | `success` toast + (for password: logout + redirect) |
| 400 | any | `error` inline (unexpected validation) |
| 401 | any | session expired → `authStore.logout()` → redirect `/login` |
| 409 | `CURRENT_PASSWORD_MISMATCH` | inline error on `current_password` field |
| 422 | any | map `detail[].loc` to form field errors |
| 429 | any | "Demasiados intentos, espera 15 minutos" toast |
| 5xx | — | generic error toast, no redirect |

The Axios interceptor (Change 07) handles 401 → attempt token refresh → if refresh fails → `authStore.logout()` + redirect `/login`. This applies to both profile endpoints transparently.

---

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|---|---|---|
| **Access token residual window** (D-04) | Low — 30 min max exposure after password change | Documented and accepted; all refresh tokens revoked so attacker cannot extend the window |
| **`revoke_all_for_user` triggers `token_replay_detected` on subsequent refresh** | UX confusion if user still has old tabs open | 401 forces re-login which is the correct behavior; no code change needed |
| **Frontend password_confirm mismatch with backend** | Low risk — password_confirm never sent | Pydantic's `min_length=8` enforced on server; FE equality check is UX-only |
| **`telefono` absent from model** | Scope reduction vs. US-062 description | US-062 says "nombre o telefono" — modelo actual solo tiene nombre/apellido. Change 21 or a dedicated migration can add telefono. Documented in proposal. |
| **ProfileUpdate with all-None body** | No-op update accepted | Service returns current UserRead without DB write if no fields are set. Idempotent. |

---

## Migration Plan

**No Alembic migration required.** The `Usuario` model already has `nombre` and `apellido` fields. No new columns, no schema changes.

Deploy steps:
1. Apply backend code changes (new files + modified files).
2. Register `profile_router` in `build_v1_router`.
3. Deploy frontend with updated `/profile` page.
4. No rollback concerns — endpoints are purely additive; no breaking changes to existing contracts.

---

## Open Questions

None blocking. The following are noted for future changes:
- Should `telefono` be added to `Usuario` in a dedicated migration? → Deferred to future change.
- Should a `password_changed_at` timestamp be introduced to enable forced access-token invalidation? → Out of scope per D-04; revisit in Change 21 if the risk model changes.

---

## Preparación para futuro

The `profile/` module is intentionally minimal. The architecture is open for:
- **Avatar upload**: a `POST /api/v1/profile/me/avatar` endpoint in the same router, with a new `avatar_url` field on `Usuario`.
- **User preferences**: a `PATCH /api/v1/profile/me/preferences` endpoint or a `UserPreferences` sub-table.
- **2FA**: an enrollment endpoint in the same router; `totp_secret` field on `Usuario`; would require `password_changed_at` or a dedicated OTP-reset flow.
- **Session audit**: a `GET /api/v1/profile/me/sessions` endpoint returning active `RefreshToken` rows for the user (token hashes redacted, showing only `created_at`, `expires_at`, `user_agent`, `ip_address` if logged).

None of these are designed or implemented in this change.

---

## Standards aplicables (para la fase apply)

Skills que deberán cargarse en la fase apply:
- **`fastapi-python`** — para backend: router, service, repository method, schemas Pydantic v2, UoW pattern, slowapi, RFC 7807 errors.
- **`frontend-design`** — para frontend: componentes React, páginas FSD, TanStack Form, TanStack Query mutations, estados de UI.
- **`tailwind-design-system`** — para frontend: tokens semánticos, consistent UI con el resto de la app (forms, buttons, alerts).
