# ci-workflows

Central, versioned CI for `vladpetl-dev` repositories: an AI pull-request review gate (Claude),
Python build/test, and automatic GitHub releases. Application repositories only call these
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
