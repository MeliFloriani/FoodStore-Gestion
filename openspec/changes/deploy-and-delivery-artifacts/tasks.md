## 1. Containerization — Backend Dockerfile

- [x] 1.1 Create `backend/Dockerfile` with multi-stage build (python:3.11-slim, requirements.txt, pip install --no-cache-dir)
- [x] 1.2 Add HEALTHCHECK instruction using `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"` (no curl dependency)
- [x] 1.3 Add `backend/.dockerignore` excluding `__pycache__/`, `.venv/`, `.env`, `tests/`, `.git/`
- [x] 1.4 Verify Docker build succeeds: `docker build -t foodstore-backend ./backend` (489MB ✅)

## 2. Containerization — Frontend Dockerfile

- [x] 2.1 Create `frontend/Dockerfile` with multi-stage build (node:22-alpine build stage + nginx:alpine production stage, pnpm via corepack)
- [x] 2.2 Create `frontend/nginx.conf` with SPA fallback (`try_files $uri /index.html`), Brotli/gzip compression, and asset caching headers
- [x] 2.3 Add `frontend/.dockerignore` excluding `node_modules/`, `.env*`, `tests/`, `.git/` (NOTA: `src/` NO se excluye porque el Dockerfile COPY . . lo necesita para el build)
- [x] 2.4 Verify Docker build succeeds: `docker build --build-arg VITE_API_BASE_URL=... -t foodstore-frontend ./frontend` (75.2MB ✅, pnpm via corepack, node:22-alpine)

## 3. Railway Deployment — Configuration

- [ ] 3.1 Create Railway project via Dashboard: add backend service (Root Directory = `backend/`) and frontend service (Root Directory = `frontend/`)
- [ ] 3.2 Connect GitHub repository to Railway project
- [ ] 3.3 Provision Railway PostgreSQL plugin for the backend service
- [ ] 3.4 Configure backend environment variables in Railway Dashboard:
  - `ENVIRONMENT=production`
  - `BACKEND_CORS_ORIGINS=<frontend-url>`
  - `SECRET_KEY` (new random 64-char hex)
  - `MP_ACCESS_TOKEN` (production/sandbox token)
  - `MP_PUBLIC_KEY` (sandbox or production public key — required by backend Settings)
  - `MP_WEBHOOK_SECRET` (from MP dashboard)
  - `MP_NOTIFICATION_URL=https://<backend-url>/api/v1/pagos/webhook`
  - `FRONTEND_BASE_URL=https://<frontend-url>`
  - `BCRYPT_COST=12`
- [ ] 3.5 Configure frontend **Build Variable** in Railway Dashboard (IMPORTANT: set as Build Variable, not runtime env var — Vite embeds VITE_ vars at build time):
  - `VITE_API_BASE_URL=https://<backend-url>/api/v1`
- [ ] 3.6 Deploy backend service and verify health check returns 200
- [ ] 3.7 Deploy frontend service and verify it loads in the browser
- [ ] 3.8 Run Alembic migrations in Railway: `railway run alembic upgrade head`
- [ ] 3.9 Run seed data in Railway: `railway run python -m app.db.seed` (roles, estados, formas de pago, admin user)

## 4. Delivery Artifacts — Screenshots

- [ ] 4.1 Create `docs/screenshots/` directory
- [ ] 4.2 Capture CE-01: Catálogo público con productos listados
- [ ] 4.3 Capture CE-02: Detalle de producto con ingredientes
- [ ] 4.4 Capture CE-03: Registro de nuevo usuario
- [ ] 4.5 Capture CE-04: Inicio de sesión
- [ ] 4.6 Capture CE-05: Carrito de compras con productos
- [ ] 4.7 Capture CE-06: Checkout con selección de dirección
- [ ] 4.8 Capture CE-07: Pago con MercadoPago (redirect a Checkout Pro)
- [ ] 4.9 Capture CE-08: Documentación Swagger/OpenAPI en `/docs`
- [ ] 4.10 Capture CE-09: Confirmación de pedido después del pago
- [ ] 4.11 Capture CE-10: Historial de pedidos del cliente
- [ ] 4.12 Capture CE-11: Timeline de estados del pedido
- [ ] 4.13 Capture CE-12: Dashboard de administración con métricas
- [ ] 4.14 Capture CE-13: Gestión de productos por ADMIN
- [ ] 4.15 Capture CE-14: Gestión de pedidos con transición de estados

## 5. Delivery Artifacts — Video Demo

- [ ] 5.1 Record video demo (5–10 min) covering: registro, login, catálogo, carrito, checkout, pago MP, seguimiento de pedido, panel admin
- [ ] 5.2 Upload video to YouTube (unlisted) and save the link

## 6. Delivery Artifacts — README and Documentation

- [ ] 6.1 Update `README.md` with: project description, tech stack, production URLs, video demo link, screenshots index, local setup guide, architecture overview
- [ ] 6.2 Update `docs/CHANGES.md`: move Change 26 to "Ya realizado" section with archive date, update Última actualización

## 7. Final Verification

- [ ] 7.1 Verify end-to-end flow in production: register → login → catalog → cart → checkout → payment → order tracking
- [ ] 7.2 Verify MP webhook receives notification at `MP_NOTIFICATION_URL`
- [ ] 7.3 Verify all screenshots exist and are named correctly in `docs/screenshots/`
- [ ] 7.4 Verify README renders correctly with all links working
