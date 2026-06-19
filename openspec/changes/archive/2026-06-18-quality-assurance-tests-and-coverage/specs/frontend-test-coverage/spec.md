## ADDED Requirements

### Requirement: Coverage measurement via @vitest/coverage-v8
The frontend test suite SHALL measure code coverage using `@vitest/coverage-v8` configured in `vite.config.ts`. Coverage SHALL be measured across all source code under `src/`.

#### Scenario: Default coverage run
- **WHEN** user runs `npx vitest run --coverage`
- **THEN** coverage statistics SHALL be reported in the terminal output

#### Scenario: HTML report generation
- **WHEN** user runs `npx vitest run --coverage`
- **THEN** an HTML report SHALL be generated at `coverage/index.html`

#### Scenario: lcov report generation
- **WHEN** user runs `npx vitest run --coverage`
- **THEN** an lcov report SHALL be generated at `coverage/lcov.info`

### Requirement: Coverage threshold ≥60%
The frontend SHALL enforce a minimum total coverage threshold of 60%. If coverage falls below this threshold, the test run SHALL fail.

#### Scenario: Coverage exceeds threshold
- **WHEN** frontend coverage is ≥60%
- **THEN** vitest SHALL exit with code 0

#### Scenario: Coverage below threshold
- **WHEN** frontend coverage is <60%
- **THEN** vitest SHALL exit with a non-zero exit code indicating failure

### Requirement: Source paths omitted from coverage
Coverage SHALL omit `test/`, `**/__tests__/`, and `**/*.test.*` files from measurement to avoid inflating the metric with test code.

#### Scenario: Omission configuration
- **WHEN** coverage run completes
- **THEN** test helper files, `__tests__/` directories, and `*.test.*` files SHALL NOT be included in the coverage calculation
