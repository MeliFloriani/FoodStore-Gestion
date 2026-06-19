# backend-test-coverage Specification

## Purpose
Code coverage measurement and enforcement for the backend (FastAPI/Python) using pytest-cov. Introduced in Change 25 (quality-assurance-tests-and-coverage).

## Requirements

### Requirement: Coverage measurement via pytest-cov
The backend test suite SHALL measure code coverage using `pytest-cov` with the configuration defined in `pyproject.toml`. Coverage SHALL be measured across all modules under `app/`.

#### Scenario: Default coverage run
- **WHEN** user runs `pytest --cov=app`
- **THEN** coverage statistics SHALL be reported in the terminal output

#### Scenario: HTML report generation
- **WHEN** user runs `pytest --cov=app --cov-report=html`
- **THEN** an HTML report SHALL be generated at `htmlcov/index.html`

#### Scenario: XML report generation
- **WHEN** user runs `pytest --cov=app --cov-report=xml`
- **THEN** an XML report SHALL be generated at `coverage.xml`

### Requirement: Coverage threshold ≥60%
The backend SHALL enforce a minimum total coverage threshold of 60%. If coverage falls below this threshold, the test run SHALL fail.

#### Scenario: Coverage exceeds threshold
- **WHEN** backend coverage is ≥60%
- **THEN** pytest SHALL exit with code 0

#### Scenario: Coverage below threshold
- **WHEN** backend coverage is <60%
- **THEN** pytest SHALL exit with a non-zero exit code indicating failure

### Requirement: Critical modules coverage
The backend SHALL achieve and maintain coverage ≥60% in each of the following critical modules: `test_auth`, `test_pedidos`, `test_pagos` (as required by Integrador §12 bonus criteria). Coverage is measured as the aggregate (total lines covered / total lines) across the listed source files for each module.

#### Scenario: Auth code coverage
- **WHEN** coverage is measured across `app/services/auth.py`, `app/api/v1/auth.py`, `app/repositories/user.py`, `app/core/security.py`
- **THEN** the aggregate coverage of these files SHALL be ≥60%

#### Scenario: Pedidos code coverage
- **WHEN** coverage is measured across `app/services/pedidos_service.py`, `app/services/pedidos_validar_service.py`, `app/api/v1/pedidos.py`, `app/services/state_transition.py`
- **THEN** the aggregate coverage of these files SHALL be ≥60%

#### Scenario: Pagos code coverage
- **WHEN** coverage is measured across `app/pagos/service.py`, `app/pagos/router.py`, `app/pagos/repository.py`, `app/integrations/mercadopago_client.py`
- **THEN** the aggregate coverage of these files SHALL be ≥60%

### Requirement: Source paths omitted from coverage
Coverage SHALL omit `tests/`, `migrations/`, and `__init__.py` files from measurement to avoid inflating the metric with non-production code.

#### Scenario: Omission configuration
- **WHEN** coverage run completes
- **THEN** tests/, migrations/, and __init__.py files SHALL NOT be included in the coverage calculation
