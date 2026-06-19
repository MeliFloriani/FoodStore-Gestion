## Context

Food Store tiene una suite de tests extensiva (~50+ archivos backend en pytest, ~60+ archivos frontend en vitest) desarrollada incrementalmente durante los changes previos. Sin embargo, el proyecto carece de:

- Configuración formal de cobertura con umbrales (`pytest-cov` está en dependencias pero no configurado; vitest no tiene coverage habilitado)
- Pipeline de CI que ejecute tests automáticamente
- Métrica objetiva de cobertura para verificar el bonus +10 pts del Integrador §12

Este change configura infraestructura de calidad sin modificar lógica de negocio existente.

## Goals / Non-Goals

**Goals:**
- Configurar `pytest-cov` con umbral mínimo ≥60% y generación de reportes (HTML + XML + terminal)
- Configurar `@vitest/coverage-v8` con umbral mínimo ≥60% y reportes (HTML + lcov)
- Crear pipeline CI (GitHub Actions) que ejecute tests + coverage en backend y frontend
- Agregar/ajustar tests donde sea necesario para alcanzar el threshold ≥60% en los módulos críticos (auth, pedidos, pagos)
- Documentar comandos de cobertura en el README

**Non-Goals:**
- NO se reescribe ni refactoriza lógica de negocio existente
- NO se modifican specs de funcionalidad del dominio
- NO se agregan nuevas funcionalidades
- NO se configura deploy continuo (CD) — eso pertenece al Change 26
- NO se migra a otro test runner ni se cambia la estructura de tests existente

## Decisions

### D1 — `pytest-cov` con configuración en `pyproject.toml`
- **Opción**: Configurar coverage en `pyproject.toml` vs `setup.cfg` vs `.coveragerc`
- **Decisión**: Usar `pyproject.toml` con sección `[tool.coverage.run]` y `[tool.coverage.report]`. Es el estándar moderno, consistente con las configs existentes de pytest y ruff en el mismo archivo. Una sola fuente de verdad.
- **Alternativa descartada**: `.coveragerc` — archivo adicional innecesario cuando todo puede vivir en `pyproject.toml`.

### D2 — `@vitest/coverage-v8` sobre `@vitest/coverage-istanbul`
- **Opción**: Coverage con V8 nativo vs Istanbul
- **Decisión**: `@vitest/coverage-v8` — es más rápido (nativo), no requiere transpilación, y para un proyecto TypeScript moderno es la opción recomendada por la documentación de Vitest v4.
- **Trade-off**: Istanbul da reportes más detallados de branch coverage, pero V8 coverage es suficiente para el threshold de línea ≥60% que requiere el TPI.

### D3 — GitHub Actions como proveedor de CI
- **Opción**: GitHub Actions vs GitLab CI vs Jenkins vs scripts manuales
- **Decisión**: GitHub Actions — el proyecto está en GitHub, es gratuito para repos públicos, se integra nativamente con PR checks, y es el estándar de la industria.
- **Alternativa descartada**: Scripts manuales — no automatizan la verificación en cada push.

### D4 — CI jobs separados por capa (backend/frontend)
- **Opción**: Un job monolítico vs jobs paralelos
- **Decisión**: Jobs separados para backend y frontend con ejecución paralela. Más rápido, aísla fallos, y permite ver claramente qué capa falla. Cada job usa su versión específica (Python 3.11 para backend, Node 20 para frontend).

### D5 — Threshold de cobertura: global + módulos críticos
- **Opción**: Threshold global único vs thresholds por módulo
- **Decisión**: Threshold global ≥60% para backend y frontend por separado, más un requisito adicional de ≥60% en cada módulo crítico (auth, pedidos, pagos) según define la spec `backend-test-coverage`. Esto alinea con el bonus del Integrador §12 ("cobertura > 60% (test_pedidos, test_pagos, test_auth)") y asegura que los módulos evaluables no queden descubiertos aunque el promedio global los disfrace.

### D6 — Tests adicionales: priorizar `test_auth`, `test_pedidos`, `test_pagos`
- **Razón**: Estos son los tres módulos que el Integrador §12 menciona explícitamente para el bonus +10 pts. La mayoría ya tienen cobertura alta; se identifican gaps y se completan.
- **Estrategia**: Ejecutar `pytest --cov --cov-report=term-missing` y `npx vitest run --coverage` para detectar líneas no cubiertas, luego agregar tests focalizados.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|------------|
| Coverage threshold ≥60% no se alcanza en primera corrida | Se identifican gaps y se prioriza agregar tests en los módulos críticos (auth, pedidos, pagos). El threshold es alcanzable dado el volumen de tests existente. |
| CI pipeline falla por entorno (base de datos, variables de entorno) | Los tests de integración requieren PostgreSQL. Se configura `services.postgres` en el workflow de CI. Tests unitarios corren sin BD. |
| Frontend coverage bajo por falta de tests de componentes visuales | Vitest con jsdom cubre lógica de hooks, stores y utils. Los tests de componentes con `@testing-library/react` ya existen para varios módulos. Se priorizan los módulos con menor cobertura. |
| `@vitest/coverage-v8` incompatible con versión de Vitest | Se verifica compatibilidad: Vitest v4.x es compatible con `@vitest/coverage-v8` v1.x. |

## Commands de Referencia

```bash
# Backend — ejecutar tests con cobertura
cd backend
pytest --cov=app --cov-report=term-missing --cov-report=html
# Reporte HTML en backend/htmlcov/index.html

# Frontend — ejecutar tests con cobertura
cd frontend
npx vitest run --coverage
# Reporte HTML en frontend/coverage/index.html
```
