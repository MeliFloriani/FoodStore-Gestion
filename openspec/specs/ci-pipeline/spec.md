# ci-pipeline Specification

## Purpose
Automated CI pipeline via GitHub Actions for the Food Store monorepo. Runs backend and frontend test suites in parallel with coverage verification. Introduced in Change 25 (quality-assurance-tests-and-coverage).

## Requirements

### Requirement: Automated CI pipeline via GitHub Actions
The project SHALL have a GitHub Actions workflow that automatically runs tests on every push to any branch and on every pull request targeting `main`.

#### Scenario: Push triggers CI
- **WHEN** a commit is pushed to any branch
- **THEN** the CI workflow SHALL be triggered automatically

#### Scenario: Pull request triggers CI
- **WHEN** a pull request is opened or updated targeting `main`
- **THEN** the CI workflow SHALL be triggered automatically

### Requirement: Parallel backend and frontend jobs
The CI pipeline SHALL run backend and frontend test suites in parallel to minimize total execution time.

#### Scenario: Backend job runs
- **WHEN** CI workflow executes
- **THEN** a dedicated backend job SHALL install Python dependencies and run `pytest`

#### Scenario: Frontend job runs
- **WHEN** CI workflow executes
- **THEN** a dedicated frontend job SHALL install Node dependencies and run `npx vitest run`

#### Scenario: Parallel execution
- **WHEN** CI workflow executes
- **THEN** backend and frontend jobs SHALL run concurrently

### Requirement: Coverage verification in CI
The CI pipeline SHALL verify that coverage meets the configured thresholds and SHALL fail the workflow if thresholds are not met.

#### Scenario: Coverage threshold met
- **WHEN** coverage is ≥60% in both backend and frontend jobs
- **THEN** both jobs SHALL pass and the workflow SHALL succeed

#### Scenario: Coverage threshold not met (backend)
- **WHEN** backend coverage is <60%
- **THEN** the backend job SHALL fail and the workflow SHALL report failure

#### Scenario: Coverage threshold not met (frontend)
- **WHEN** frontend coverage is <60%
- **THEN** the frontend job SHALL fail and the workflow SHALL report failure

### Requirement: PostgreSQL service for integration tests
The CI pipeline SHALL provide a PostgreSQL service container so that backend integration tests can run.

#### Scenario: PostgreSQL service available
- **WHEN** the backend CI job runs
- **THEN** a PostgreSQL 15 service SHALL be available on `localhost:5432`

#### Scenario: Integration tests execute
- **WHEN** the backend CI job runs with PostgreSQL available
- **THEN** integration tests SHALL be executed (not skipped)

### Requirement: CI badge in README
The repository README SHALL display a GitHub Actions status badge indicating the current state of the CI workflow.

#### Scenario: Badge displayed
- **WHEN** viewing README.md on GitHub
- **THEN** a CI status badge SHALL be visible showing workflow status (passing/failing)
