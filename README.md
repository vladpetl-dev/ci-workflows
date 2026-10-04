# ci-workflows

Central, versioned CI for `vladpetl-dev` repositories: an AI pull-request review gate (Claude),
Python build/test, Kotlin/Java (Gradle) build/test with a coverage gate, and automatic GitHub
releases. Application repositories only call these
reusable workflows; all logic and tests live here.

## Use in a repository

`.github/workflows/ci.yml`
```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  ci:
    uses: vladpetl-dev/ci-workflows/.github/workflows/ci-python.yml@v1
```

Kotlin / Java (Gradle) repositories use `ci-gradle.yml` instead of `ci-python.yml`:

`.github/workflows/ci.yml`
```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: write   # coverage comment on the PR
jobs:
  ci:
    uses: vladpetl-dev/ci-workflows/.github/workflows/ci-gradle.yml@v1
    with:
      coverage-gate: true          # false = report only, never fails
      min-changed-coverage: 90     # % of lines changed by the PR; 0 = off
      min-total-coverage: 0        # % of all lines; 0 = off
```

The repository must produce a JaCoCo XML report (Gradle `jacoco` plugin, `jacocoTestReport`
with `xml.required = true`). The job runs `./gradlew build jacocoTestReport` (tests, lint and
whatever `check` depends on), then posts one PR comment with changed-line coverage, total
coverage, uncovered changed lines and the test totals. Changed lines count only when the
coverage report knows them as executable code, so tests, docs and config never dilute the number.

`.github/workflows/ai-review.yml`
```yaml
name: ai-review
on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]
permissions:
  contents: read
  pull-requests: write
jobs:
  ai-review:
    uses: vladpetl-dev/ci-workflows/.github/workflows/ai-review.yml@v1
    secrets: inherit
```

`.github/workflows/release.yml`
```yaml
name: release
on:
  workflow_run:
    workflows: [ci]
    types: [completed]
    branches: [main]
permissions:
  contents: write
jobs:
  release:
    uses: vladpetl-dev/ci-workflows/.github/workflows/release-python.yml@v1
```

Required status checks for the branch ruleset: `ci / build` and `ai-review / review`.

## Secrets

Organization secrets shared with selected repositories (passed with `secrets: inherit`):

| Secret | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | `ai-review` (required) |
| `SLACK_WEBHOOK_URL` | `ai-review` failure notification (optional) |

## Inputs

| Workflow | Input | Default | Notes |
|---|---|---|---|
| all | `python-version` | `3.12` | |
| `ai-review`, `release-python` | `tools-ref` | `v1` | Ref of this repo for the Python tooling; keep equal to the `@ref` you call |
| `ai-review` | `policy-path` | `.ai-review/policy.yml` | Optional override, read from the caller's **base branch** only |
| `ci-gradle` | `java-version` / `java-distribution` | `25` / `corretto` | |
| `ci-gradle` | `gradle-args` | `build jacocoTestReport` | Must run the tests and write the coverage XML |
| `ci-gradle` | `coverage-gate` | `true` | `false` = report only |
| `ci-gradle` | `min-changed-coverage` | `90` | Line coverage of PR-changed lines, %; `0` = off |
| `ci-gradle` | `min-total-coverage` | `0` | Total line coverage, %; `0` = off |
| `ci-gradle` | `coverage-xml` | `build/reports/jacoco/test/jacocoTestReport.xml` | JaCoCo or Cobertura |

## Review policy

`review/policy.yml` (or the caller's `.ai-review/policy.yml`): `model`, `effort`, `fallbacks`,
`fail_on` (blocking severities), `min_severity` (findings below it are hidden; the comment shows
how many), `max_diff_chars`, `excluded_patterns`, `fail_open_on_error`.

The review prompt only accepts findings caused by the changed lines, with a concrete failure
scenario and nothing in the diff already preventing it; style, speculative hardening and missing
tests are out of scope (tests are the coverage gate's job). The model is not deterministic, so
re-runs can still surface different low-severity remarks; `min_severity` filters them.

## Trust model

- Review code and the default policy come from this repository at `tools-ref`; a pull request
  in a calling repository cannot change them. A policy override is read from the caller's base
  branch, never from the PR head.
- The PR checkout is used only as a diff source; nothing from it is executed.
- The diff is passed to Claude as untrusted input inside `<diff>` tags. This reduces, but does
  not eliminate, prompt-injection risk.
- Fork PRs receive no secrets and are not reviewed.

## Versioning

Releases are tagged `vX.Y.Z`; the moving tag `v1` points at the latest `v1.x.y`. Breaking
changes ship as `v2`.

## Development

```bash
uv venv --python 3.12 .venv && uv pip install -e ".[dev]"
.venv/bin/pytest && .venv/bin/ruff check .
```
