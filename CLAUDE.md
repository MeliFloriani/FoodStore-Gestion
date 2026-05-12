# CLAUDE.md — Food Store · Gestión de Pedidos

## Rol
Actúa como un Senior Tech Lead y Arquitecto de Software con enfoque en Spec-Driven Development. Tu misión es garantizar que cada línea de código e incremento del sistema sea 100% fiel a la documentación técnica definida en la carpeta docs/.

## Regla de trabajo (MANDATORIA): usar subagentes

Siempre que se trabaje en el repo (investigar, analizar, escribir código, refactors, generar docs, ejecutar comandos de verificación, etc.) se DEBEN usar **subagentes**.

- Este agente principal actúa como **orquestador/coordinador**: define el plan, delega, revisa resultados y toma decisiones.
- La ejecución concreta del trabajo (exploración intensiva, cambios multi-archivo, scripts, tests, builds, etc.) se delega a subagentes mediante la herramienta de tareas.
- Únicas excepciones permitidas: preguntas de clarificación al usuario y comandos mínimos de “estado” (p.ej. `openspec status/list`, `git status/diff/log`) para entender el contexto antes de delegar.

## Proyecto

**Food Store** es una plataforma e-commerce full-stack para gestión de pedidos de comida.

- **Backend:** FastAPI + SQLModel + PostgreSQL + Alembic · Feature-First (Router → Service → UoW → Repository → Model)
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS · Feature-Sliced Design (FSD)
- **Pagos:** MercadoPago Checkout API (tarjeta, Rapipago, Pago Fácil) + webhooks IPN
- **Auth:** JWT + RBAC (4 roles: Cliente, Admin, Gestor de Stock, Gestor de Pedidos) + refresh token en BD
- **Estado:** Zustand 4 (cliente) + TanStack Query 5 (servidor)
- **Metodología:** Spec-Driven Development (SDD) · Versión de spec: 5.0

---

## Estructura del proyecto

```
food-store/
├── backend/                  ← Workspace Python/FastAPI
│   ├── app/
│   │   ├── api/             ← Routers FastAPI (por dominio)
│   │   ├── services/        ← Lógica de negocio
│   │   ├── repositories/    ← Acceso a datos
│   │   ├── models/          ← Entidades SQLModel
│   │   ├── schemas/         ← Pydantic v2 (Read/Create/Update)
│   │   ├── core/            ← config.py, security.py, uow.py
│   │   ├── db/              ← sessions.py (fábrica async)
│   │   └── main.py          ← Entrypoint + GET /health
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.txt     ← Lockfile generado con pip freeze
│   └── .env.example
│
├── frontend/                 ← Workspace React/TS/Vite
│   ├── src/
│   │   ├── app/             ← Providers, router stub, estilos globales
│   │   ├── pages/           ← Composición de páginas (FSD layer)
│   │   ├── widgets/         ← Bloques reutilizables multi-feature
│   │   ├── features/        ← Casos de uso (FSD layer)
│   │   ├── entities/        ← Tipos de dominio (FSD layer)
│   │   └── shared/          ← UI kit, utils, tipos, api client base
│   ├── vite.config.ts
│   ├── tsconfig.app.json
│   ├── tailwind.config.js
│   └── .env.example
│
├── openspec/                 ← Artefactos OPSX (NO editar manualmente)
├── docs/                     ← Documentación del TPI
├── .gitignore
├── .editorconfig
├── .nvmrc                    ← Node 20
├── .python-version           ← Python 3.11
└── README.md
```
---

## Arquitectura Backend — Regla de Oro

El flujo de imports es **unidireccional y no puede invertirse:**

```
Router → Service → UoW → Repository → Model
```

- `router.py` — HTTP puro: parsear request, validar schema, delegar al Service
- `service.py` — Lógica de negocio stateless, orquesta a través del UoW
- `core/uow.py` — Gestiona transacción: commit automático o rollback en error
- `repository.py` — Acceso a BD, sin lógica de negocio, hereda `BaseRepository[T]`
- `model.py` — SQLModel tables + relaciones, sin imports de capas superiores

---

## Skills Disponibles

Las siguientes skills están instaladas en `.agents/skills/`. Cargalas leyendo su `SKILL.md` **antes** de escribir código en los contextos indicados.

| Contexto de activación | Skill | Archivo a leer |
|------------------------|-------|----------------|
| Cualquier endpoint FastAPI, service, repository, schema Pydantic, UoW, router | `fastapi-python` | `.agents/skills/fastapi-python/SKILL.md` |
| Componentes React, páginas, hooks, Tailwind, estilo visual del frontend | `frontend-design` | `.agents/skills/frontend-design/SKILL.md` |
| Design system, tokens, componentes Tailwind reutilizables, sistema de clases | `tailwind-design-system` | `.agents/skills/tailwind-design-system/SKILL.md` |
| Crear o mejorar una skill de agente IA | `skill-creator` | `.agents/skills/skill-creator/SKILL.md` |
| El usuario pregunta qué skill usar o si existe una skill para X | `find-skills` | `.agents/skills/find-skills/SKILL.md` |

> **Regla:** si el contexto activa una skill, leé el `SKILL.md` correspondiente **antes** de generar código. Múltiples skills pueden aplicar simultáneamente.

---

# Reglas de Continuidad entre Sesiones

Cuando inicia una nueva sesión, el agente DEBE:

1. Leer los archivos de la carpeta /docs.
2. Utilizarlos como fuente operativa principal
3. Reconciliarlo contra el estado real del repositorio
4. Detectar drift si existen inconsistencias

---

## Convenciones del Proyecto

### Backend

- Cada módulo sigue la estructura: `model.py · schemas.py · repository.py · service.py · router.py`
- El `router.py` usa `response_model` explícito en todos los endpoints
- El `service.py` lanza `HTTPException` — nunca el router ni el repository
- Las migraciones van en `alembic/versions/` — nunca modificar tablas directamente
- Rate limiting en endpoints críticos con `slowapi` (ej: login: 5 intentos / 15 min)
- Contraseñas hasheadas con bcrypt (cost factor ≥ 12)
- Refresh tokens almacenados en BD para soporte de invalidación

### Frontend

- FSD estricto: imports solo fluyen hacia abajo — `Pages → Features → Entities → Shared`
- Estado del servidor exclusivamente con **TanStack Query** (no duplicar en Zustand)
- Estado del cliente (carrito, sesión, UI, pagos) con **Zustand stores** tipados
- HTTP con Axios + interceptor JWT (attach + refresh automático)
- Formularios con **TanStack Form** (no react-hook-form)
- Gráficos del dashboard con **recharts**
- Tokenización de tarjetas con `@mercadopago/sdk-react` — nunca manejar datos de tarjeta en frontend raw

### General

- Commits: Conventional Commits (`feat:`, `fix:`, `chore:`, etc.) — sin co-authored-by ni atribución a IA
- Variables de entorno: usar `.env.example` como referencia — nunca commitear `.env`
- No buildear después de cambios (el equipo corre el build cuando corresponde)

---

## Flujo OPSX (Spec-Driven Development)

Este proyecto usa **OPSX** para gestión de cambios. Los artefactos viven en `openspec/`.

```
/opsx:explore  →  /opsx:propose  →  /opsx:apply  →  /opsx:archive
```

- Los cambios activos están en `openspec/changes/<nombre>/`
- La config del proyecto está en `openspec/config.yaml`
- Antes de implementar cualquier feature nueva, verificar si existe un change activo con `openspec list --json`

### Sync de docs/CHANGES.md al archivar

Cada vez que completes el archivado de un change, **además de** ejecutar el comando de OPSX, mantené sincronizado el índice humano en `docs/CHANGES.md`:

```bash
/opsx:archive <change-name>
```

- Abrí `docs/CHANGES.md` y actualizá `Última actualización` a la fecha del día (formato `YYYY-MM-DD`).
- Ubicá la fila del change en la tabla donde esté (Sprint/Epic) y **movela** a `## Ya realizado (archivado en OPSX)` (manteniendo la misma estructura de columnas).
- En la fila movida, `Estado` debe quedar como `✅ Hecho (archivado YYYY-MM-DD)`.
- En la fila movida, `Evidencia` debe apuntar a `openspec/changes/archive/YYYY-MM-DD-<change-name>/`.
- Importante: el **source of truth** del cambio sigue siendo `openspec/` (OPSX). `docs/CHANGES.md` es solo un resumen para lectura rápida.

---

## Documentación de Referencia

| Documento | Contenido |
|-----------|-----------|
| `docs/Integrador.txt` | Especificación técnica SDD v5.0 completa — ERD v5, FSM de pedidos, API REST, schemas Pydantic, rúbrica |
| `docs/Descripcion.txt` | Descripción integral del sistema (15 secciones) |
| `docs/Historias_de_usuario.txt` | Historias de usuario por actor |
| `docs/CHANGES.md` | Historial de cambios del proyecto |
