# ci-workflows

Central, versioned CI for `vladpetl-dev` repositories. Application repositories only call these reusable
workflows; all logic and its tests live here. Every gate fails its check, and a branch ruleset turns a failed
check into a blocked merge.

| Gate | Workflow | Blocks the merge when |
|---|---|---|
| AI review (Claude), independent and adversarial | `ai-review.yml` | a finding at a `fail_on` severity (default HIGH, CRITICAL) |
| Backend build, tests, coverage | `ci-gradle.yml` | the build fails, or coverage of PR-changed lines < **95%** (total coverage optional) |
| Frontend build, tests, coverage | `ci-node.yml` | lint, typecheck, tests or build fail, or changed-line coverage < **95%** |
| Vulnerability scan (Trivy) | `security.yml` | any **HIGH or CRITICAL** vulnerability, fixed or not, unless accepted in `.trivyignore` |
| Release | `release.yml` | — (runs after CI passes on the default branch: tag `vX.Y.Z` + GitHub release) |
| Dependency updates | Renovate preset `default.json` | — (Renovate PRs pass through the same gates) |

## Use in a repository (v2)

`.github/workflows/ci.yml`: backend and frontend in one workflow; drop the job you do not have.

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: write   # coverage comments on the PR
jobs:
  backend:
    uses: vladpetl-dev/ci-workflows/.github/workflows/ci-gradle.yml@v2
    with:
      working-directory: backend          # where gradlew is; "." for a single-module repo
      min-changed-coverage: 95            # default; % of lines changed by the PR
      min-total-coverage: 0               # default off
  frontend:
    uses: vladpetl-dev/ci-workflows/.github/workflows/ci-node.yml@v2
    with:
      working-directory: frontend
```

- **Backend:** the Gradle build must write a JaCoCo XML report: the `jacoco` plugin, `jacocoTestReport` with
  `xml.required = true`.
- **Frontend:** `package.json` needs the scripts `lint`, `typecheck`, `test:coverage` and `build` (rename them
  through the inputs, or pass `""` to skip one). `test:coverage` must write `coverage/cobertura-coverage.xml`;
  with Vitest that is `vitest run --coverage` with `coverage: { reporter: ['text', 'cobertura'] }`.
  Test results in JUnit XML under `test-results/` are optional.
- **Coverage comments:** each report posts and updates its own PR comment. Changed lines count only when the
  coverage report knows them as executable code, so tests, docs and config never dilute the number.

`.github/workflows/security.yml`:

```yaml
name: security
on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"    # new CVEs appear without code changes
permissions:
  contents: read
  pull-requests: write
  security-events: write   # SARIF to GitHub code scanning
jobs:
  security:
    uses: vladpetl-dev/ci-workflows/.github/workflows/security.yml@v2
    with:
      gradle-directory: backend   # omit if there is no Gradle build
```

What it scans:
- lock files in the repo (npm, pnpm, yarn, Gradle lockfiles, Maven, pip, poetry…);
- for a Gradle build, the jars it assembles (`assemble`, tests skipped). Trivy reads the dependencies inside
  Spring Boot fat jars, so no Gradle lockfiles are needed;
- with `image-ref`, a container image.

`fail-on` (default `HIGH,CRITICAL`) and `ignore-unfixed` (default `false`) set what blocks.

To accept a risk, add the CVE id to `.trivyignore` with a comment saying why; the file is reviewed like any
other change:

```
# CVE-2026-1234: only reachable through the XML parser, which we do not use. Revisit 2027-01.
CVE-2026-1234
```

`.github/workflows/ai-review.yml`:

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
    uses: vladpetl-dev/ci-workflows/.github/workflows/ai-review.yml@v2
    secrets: inherit
```

`.github/workflows/release.yml`: a release for every merge to `main` whose CI passed.

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
    uses: vladpetl-dev/ci-workflows/.github/workflows/release.yml@v2
    with:
      java-version: "25"                                   # optional, for build-command
      build-command: cd backend && ./gradlew bootJar -x test
      assets: backend/build/libs/*.jar                     # optional
```

How the version is chosen (Conventional Commits since the last `v*` tag):
- `type!:` or `BREAKING CHANGE` → major;
- `feat:` → minor;
- anything else → patch;
- the first release is `v0.1.0`.

The notes list the commit subjects. Python packages can keep `release-python.yml`.

`renovate.json`:

```json
{ "extends": ["github>vladpetl-dev/ci-workflows"] }
```

The shared preset (`default.json`):
- weekly schedule; security updates at any time;
- non-major updates grouped per area (backend, frontend, frontend dev, Python, GitHub Actions, Docker);
- automerge only for frontend dev dependencies and GitHub Actions, and only once every required check is
  green;
- major updates one PR each, never automerged.

Renovate runs as the GitHub App installed on the organization.

## Branch protection

A failed check blocks a merge only when the branch requires it. After the workflows above have run once (so
the checks exist), run:

```bash
scripts/protect-branch.sh vladpetl-dev/<repo> "backend / build" "frontend / build" "security / trivy" "ai-review / review"
```

The script creates or updates the ruleset `default-branch-protection` on the default branch:
- pull requests only (no review approval required, so the owner can merge after the gates pass);
- the listed checks required;
- no force-push and no deletion.

It also enables auto-merge (for Renovate) and branch deletion after merge. Check names are
`<caller job> / <reusable workflow job>`.

## Secrets

Organization secrets shared with selected repositories (passed with `secrets: inherit`):

| Secret | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | `ai-review` (required) |
| `SLACK_WEBHOOK_URL` | `ai-review` failure notification (optional) |

## Inputs

| Workflow | Input | Default | Notes |
|---|---|---|---|
| all with tooling | `tools-ref` | `v2` | Ref of this repo for the Python tooling; keep equal to the `@ref` you call |
| `ai-review` | `policy-path` | `.ai-review/policy.yml` | Optional override, read from the caller's **base branch** only |
| `ci-gradle` | `working-directory` | `.` | Where `gradlew` is |
| `ci-gradle` | `java-version` / `java-distribution` | `25` / `corretto` | |
| `ci-gradle` | `gradle-args` | `build jacocoTestReport` | Must run the tests and write the coverage XML |
| `ci-gradle`, `ci-node` | `coverage-gate` | `true` | `false` = report only |
| `ci-gradle`, `ci-node` | `min-changed-coverage` | `95` | Line coverage of PR-changed lines, %; `0` = off |
| `ci-gradle`, `ci-node` | `min-total-coverage` | `0` | Total line coverage, %; `0` = off |
| `ci-gradle` | `coverage-xml` | `build/reports/jacoco/test/jacocoTestReport.xml` | Relative to `working-directory`; JaCoCo or Cobertura |
| `ci-gradle`, `ci-node` | `report-label` | `backend` / `frontend` | One PR comment per label |
| `ci-node` | `working-directory` | `frontend` | |
| `ci-node` | `node-version` | `26` | |
| `ci-node` | `lint-script`, `typecheck-script`, `test-script`, `build-script` | `lint`, `typecheck`, `test:coverage`, `build` | `""` skips a step (not the test step) |
| `ci-node` | `coverage-xml` | `coverage/cobertura-coverage.xml` | Relative to `working-directory` |
| `security` | `fail-on` | `HIGH,CRITICAL` | |
| `security` | `ignore-unfixed` | `false` | |
| `security` | `gradle-directory`, `gradle-args`, `jar-paths` | `""`, `assemble`, `build/libs` | Gradle build whose jars are scanned |
| `security` | `image-ref` | `""` | Image to scan |
| `security` | `upload-sarif` | `true` | Needs `security-events: write`; not a gate |
| `release` | `java-version`, `node-version`, `build-command`, `assets` | empty | Optional build and files to attach |

## Review policy and stance

`review/policy.yml` (or the caller's `.ai-review/policy.yml`) sets:
- `model`, `effort`, `fallbacks`;
- `fail_on` (blocking severities);
- `min_severity` (findings below it are hidden; the comment shows how many);
- `max_diff_chars`, `excluded_patterns`, `fail_open_on_error`.

The reviewer is told it is independent of the author. It must try to break the change (input, state, ordering
or failure that makes the new code misbehave) and not take the author's comments, commit messages or test
names as proof. It reports only findings caused by the changed lines, with a concrete failure scenario and
nothing in the diff already preventing it. Style, speculative hardening and missing tests are out of scope;
tests are the coverage gate's job.

## Trust model

- Review code and the default policy come from this repository at `tools-ref`; a pull request in a calling
  repository cannot change them. A policy override is read from the caller's base branch, never from the PR
  head.
- The PR checkout is used only as a diff source; nothing from it is executed by the review.
- The diff is passed to Claude as untrusted input inside `<diff>` tags. This reduces, but does not eliminate,
  prompt-injection risk.
- Fork PRs receive no secrets and are not reviewed.

## Versioning

Releases are tagged `vX.Y.Z`; the moving tags `v1` and `v2` point at the latest release of their major.
- **v2:**
  - changed-line coverage default 95% (was 90%);
  - labelled coverage reports;
  - `ci-node`, `security` (Trivy) and the generic `release`;
  - adversarial review prompt;
  - action versions updated.
- `v1` stays available, unchanged.

## Development

```bash
uv venv --python 3.12 .venv && uv pip install -e ".[dev]"
.venv/bin/pytest && .venv/bin/ruff check . && actionlint
```

This repository runs its own gates on every PR: tests, actionlint, Trivy and the AI review (review code taken
from `main`).
