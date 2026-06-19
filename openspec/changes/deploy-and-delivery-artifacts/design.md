## Context

Food Store está completo funcionalmente en localhost (Changes 01–25 archivados), pero ningún deploy ha sido realizado. El webhook IPN de MercadoPago requiere una URL pública accesible desde sus servidores, y la entrega del TPI exige capturas de pantalla, video demo y documentación actualizada.

Actualmente:
- Backend: FastAPI + Uvicorn, se ejecuta con `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Frontend: Vite + React 19, se sirve en dev con `vite` y build con `tsc -b && vite build`
- Base de datos: PostgreSQL local
- Integración MP: Configurada con variables de entorno, requiere URL pública para webhook
- CI: GitHub Actions para tests (Change 25), sin pipeline de deploy

## Goals / Non-Goals

**Goals:**
- Dockerizar backend y frontend con imágenes optimizadas para producción (multi-stage, imágenes ligeras)
- Desplegar backend en Railway como servicio web con PostgreSQL gestionado
- Desplegar frontend en Railway como servicio web estático (Nginx)
- Configurar `MP_NOTIFICATION_URL` y `FRONTEND_BASE_URL` con los dominios reales de producción
- Generar ≥10 capturas de pantalla representativas del sistema funcionando en producción
- Producir un video demo de 5–10 min del flujo completo
- Actualizar README.md raíz con URLs, stack, setup local e instrucciones de uso

**Non-Goals:**
- Implementar un pipeline CI/CD de GitHub Actions para deploy automático (el deploy en Railway es manual vía GitHub connect o Railway CLI)
- Configurar dominios custom con SSL (Railway provee dominio `.railway.app` con HTTPS automático)
- Implementar multi-ambiente (staging, production) — solo production
- Migrar a otra plataforma de cloud (Render, Fly.io, Vercel) — este change se enfoca en Railway

## Decisions

### D-01: Railway como plataforma de deploy
**Decisión**: Usar Railway como plataforma única para backend y frontend, configurando cada servicio vía Dashboard con su Root Directory.
**Razón**: Railway ofrece PostgreSQL gestionado, deploy desde GitHub, HTTPS automático, dominios `.railway.app`, y soporte nativo para Dockerfiles. Render y Fly.io son alternativas válidas, pero Railway simplifica el deploy de servicios Docker sin configurar balanceadores o dominios manualmente.
**Alternativa considerada**: Render — soporte similar pero requiere config separada para servicios web y static sites.

**Nota sobre configuración**: Railway NO soporta un único `railway.json` mult-servicio. Cada servicio (backend, frontend) requiere su propia configuración. La opción más simple para el TPI es:
  1. Crear proyecto Railway desde GitHub.
  2. Agregar servicio backend con Root Directory = `backend/` (Railway detecta Dockerfile automáticamente).
  3. Agregar servicio frontend con Root Directory = `frontend/` (Railway detecta Dockerfile automáticamente).
  4. Provisionar PostgreSQL plugin desde el Dashboard.
  Opcionalmente, se puede agregar un `backend/railway.json` o `frontend/railway.json` por separado si se desea config-as-code.

### D-02: Nginx para servir el frontend en producción
**Decisión**: Usar Nginx (imagen oficial `nginx:alpine`) para servir los estáticos del build de Vite.
**Razón**: Vite en modo `preview` no es recomendado para producción. Nginx provee compresión Brotli, caching de estáticos por content-type, SPA fallback (`try_files`), y es significativamente más eficiente en memoria/CPU que un servidor Node.js.
**Alternativa considerada**: Servir con Express/Node — innecesario cuando solo se sirven archivos estáticos.

### D-03: Railway PostgreSQL como base de datos de producción
**Decisión**: Usar el plugin PostgreSQL de Railway (PostgreSQL 15+ gestionado).
**Razón**: Railway provee un plugin PostgreSQL con backup automático, conectividad interna entre servicios en el mismo proyecto (sin exponer puertos a internet), y replicación gestionada. Se conecta vía variable de entorno `DATABASE_URL` que Railway inyecta automáticamente.

### D-04: Variables de entorno gestionadas en Railway Dashboard
**Decisión**: Configurar `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `SECRET_KEY`, etc. en el dashboard de Railway (no en archivos versionados).
**Razón**: Seguridad — las credenciales de producción nunca deben estar en el repositorio. Railway permite setear variables en el panel con valores enmascarados.
**Excepción**: `ENVIRONMENT=production`, `API_V1_PREFIX=/api/v1`, `BACKEND_CORS_ORIGINS` se definen en el dashboard con valores públicos.

### D-05: Screenshots organizados por criterio CE
**Decisión**: Las capturas se nombran como `docs/screenshots/CE-NN-descripcion.png` y se indexan en el README.
**Razón**: La rúbrica del TPI evalúa contra los criterios CE-01 a CE-14. Tenerlas mapeadas facilita la corrección.

### D-06: Uvicorn single-worker para producción
**Decisión**: Usar `uvicorn app.main:app --host 0.0.0.0 --port 8000` sin workers adicionales.
**Razón**: Para el alcance del TPI (demostración, no alta concurrencia), un solo worker es suficiente y consume menos memoria en el plan gratuito de Railway (512MB RAM). Si en el futuro se requiere concurrencia, se puede agregar `--workers 2` o migrar a `gunicorn -k uvicorn.workers.UvicornWorker`.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|------------|
| **Railway cambia su plan gratuito** | Los Dockerfiles son portables a Render/Fly.io con cambios mínimos en la config del Dashboard |
| **MP sandbox no responde en producción** | Usar ngrok en local para verificar el webhook antes del deploy final |
| **BCRYPT_COST=12 en backend lento en Railway (512MB RAM)** | Reducir a BCRYPT_COST=10 si la respuesta de login excede 2s |
| **CORS bloquea requests del frontend** | Verificar `BACKEND_CORS_ORIGINS` incluya exactamente el dominio del frontend en Railway |
| **Video demo pesado (5-10 min)** | Comprimir con H.264, subir a YouTube como no listado, link en README |
| **Screenshots quedan desactualizadas** | Se generan al final del change, después de verificar que todo funciona en producción |
