## Why

Food Store está completo en desarrollo local, pero sin deployment público el webhook IPN de MercadoPago no puede alcanzar el backend, lo que hace que el flujo de pago end-to-end (CE-09) no sea evaluable. Además, la entrega del TPI requiere capturas de pantalla (≥10 pantallas), un video demo (5–10 min) y documentación actualizada con URLs funcionales.

Este change cierra el proyecto: convierte el código en un producto desplegado, documentado y presentable.

## What Changes

- **Dockerización del backend**: Dockerfile multi-stage para FastAPI + Uvicorn con `requirements.txt` y entrypoint.
- **Dockerización del frontend**: Dockerfile multi-stage para build Vite + servidor Nginx estático con SPA fallback.
- **Despliegue en Railway**: Configuración de servicios en Railway Dashboard (Root Directory por servicio), variables de entorno de producción y health check.
- **URL pública**: Configuración de `MP_NOTIFICATION_URL` y `FRONTEND_BASE_URL` apuntando a los dominios reales.
- **Capturas de pantalla**: ≥10 pantallas clave del sistema funcionando en producción (cubriendo CE-01 a CE-14).
- **Video demo**: Grabación de 5–10 min recorriendo el flujo completo (registro → login → catálogo → carrito → checkout → pago → seguimiento).
- **README final**: Actualización con descripción del proyecto, stack tecnológico, URLs de producción, instrucciones de desarrollo local y enlaces a la documentación.
- **Sync de `docs/CHANGES.md`**: Mover Change 26 a archivados al finalizar.

## Capabilities

### New Capabilities
- `containerization-backend`: Dockerfile multi-stage para el backend FastAPI con dependencias, entrypoint asíncrono (uvicorn) y health check.
- `containerization-frontend`: Dockerfile multi-stage para el frontend React — build Vite + Nginx con SPA fallback y compresión Brotli.
- `deployment-railway`: Configuración de Railway (servicios backend/frontend vía Dashboard con Root Directory), variables de entorno de producción, migraciones y health check endpoint.
- `delivery-artifacts`: Capturas de pantalla (≥10), video demo (5–10 min) y README final con URLs, stack y guía de desarrollo.

### Modified Capabilities
<!-- No existing specs need requirement changes — todo es nuevo. -->

## Impact

- **Backend**: Se agrega `Dockerfile` en `backend/`.
- **Frontend**: Se agrega `Dockerfile` en `frontend/` y config de Nginx (`nginx.conf`).
- **Infraestructura**: Se requiere una cuenta en Railway (o plataforma alternativa), PostgreSQL gestionado por Railway, y dominio público.
- **Env vars**: `MP_NOTIFICATION_URL` y `FRONTEND_BASE_URL` deben apuntar a los dominios de producción.
- **CI/CD**: No se modifica el pipeline existente de GitHub Actions (Change 25); el deploy es independiente vía Railway CLI o conexión GitHub.
- **Documentación**: README raíz se actualiza; screenshots se almacenan en `docs/screenshots/`; video se sube a YouTube/Vimeo (link en README).
