## Why

El proyecto Food Store ha implementado tests unitarios, de integración y E2E a lo largo de todos los changes previos, pero carece de tres elementos críticos para garantizar calidad sostenible: (1) configuración formal de cobertura con umbrales medibles, (2) un pipeline de CI que ejecute tests automáticamente en cada push, y (3) cobertura ≥60% en los módulos críticos (auth, pedidos, pagos) requerida por el bonus +10 pts del Integrador §12.

Sin este change, el proyecto no puede medir objetivamente su cobertura, no automatiza la verificación de calidad en cada cambio, y pierde el bonus de 10 puntos en la rúbrica de evaluación.

## What Changes

- Configurar `pytest-cov` con umbral mínimo de cobertura (≥60%) y generación de reportes HTML/XML
- Configurar `@vitest/coverage` en el frontend con umbral mínimo de cobertura (≥60%) y reportes
- Agregar o completar tests faltantes para alcanzar cobertura ≥60% en los módulos: `test_auth`, `test_pedidos`, `test_pagos` (backend) y sus contrapartes frontend
- Crear pipeline CI con GitHub Actions que ejecute tests + verifique cobertura en backend y frontend
- Agregar badge de estado de CI al README
- NO se modifican specs de funcionalidad existente — el testing es infraestructura de calidad transversal

## Capabilities

### New Capabilities

- `backend-test-coverage`: Configuración de pytest-cov con thresholds, reportes HTML/XML/terminal, integración con CI. Define los requisitos de cobertura mínima por módulo y la generación automatizada de reportes.
- `frontend-test-coverage`: Configuración de vitest/coverage con thresholds, reportes HTML/lcov, integración con CI. Define los requisitos de cobertura mínima para el frontend.
- `ci-pipeline`: Pipeline de integración continua con GitHub Actions que ejecuta tests de backend y frontend, verifica cobertura, y reporta resultados.

### Modified Capabilities

<!-- No se modifican requisitos de specs existentes — el testing es infraestructura transversal que no cambia el comportamiento de las capabilities del dominio. -->

## Impact

- **Backend**: modificación de `pyproject.toml` para agregar `[tool.coverage.run]` y `[tool.coverage.report]`, sin cambios en código de aplicación
- **Frontend**: modificación de `vite.config.ts` para agregar configuración de coverage en la sección `test:`, sin cambios en código de componentes
- **Infraestructura**: creación de `.github/workflows/ci.yml` para CI pipeline
- **Tests existentes**: revisión y eventual completitud de tests para alcanzar threshold ≥60%
- **README.md**: agregar badge de estado de CI
- **.gitignore**: agregar exclusiones para reportes de cobertura (`htmlcov/`, `coverage/`, `coverage.xml`)
- **Dependencias**: agregar `pytest-cov` (ya presente en dev de backend) y `@vitest/coverage-v8` (nuevo en frontend)
