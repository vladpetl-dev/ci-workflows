# Central CI Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** All review/CI/release logic lives in `vladpetl-dev/ci-workflows`; `ai-pr-review-gate` only calls it.

**Architecture:** Existing Python modules move unchanged into the central repo, wrapped by three `workflow_call` workflows. The consumer keeps three thin caller workflows with `secrets: inherit`; secrets are organization-level.

**Tech Stack:** GitHub Actions reusable workflows, Python 3.12, existing `review/` + `scripts/` code and tests, `gh` CLI.

**Spec:** `docs/superpowers/specs/2026-10-03-central-ci-workflows-design.md`

## Global Constraints

- The agent commits with repo-local email `vladpetl1987@gmail.com`; global git config unchanged.
- The agent never reads or writes secret values; the owner adds organization secrets.
- `gh` calls for personal/org resources use `GH_TOKEN=$(gh auth token -u vladpetl1987-star)`; the active `gh` account stays `vladimirp-ytree`.
- Central refs: tags `vX.Y.Z` + moving `v1`; callers use `@v1` and `tools-ref: v1` (default).
- Check names after migration: `ci / build`, `ai-review / review`.
- Model stays `claude-haiku-4-5` (default policy).

## Review Focus

1. Caller pins `@v1` but `tools-ref` differs → review code and workflow out of sync. (Task 2: default `tools-ref: v1`, README states both must match.)
2. Consumer has no `.ai-review/policy.yml` → central default policy is used, not a crash. (Task 2: `test -f` fallback; Task 5 run proves it.)
3. Refactor PR blocked forever because required checks keep old names. (Task 5: ruleset updated before the PR.)
4. Repository-level secrets shadow org secrets → org setup looks fine but repo copies are used. (Task 6: delete repo copies, re-run proves org secrets work.)
5. Release in the consumer computes the version from the central repo's tags instead of the consumer's. (Task 2: `next_version.py` runs with cwd = consumer checkout.)

---

### Task 1: Central repo code and its own CI

**Files:** create in `~/IdeaProjects/ci-workflows`: `review/*` and `scripts/*` copied from `ai-pr-review-gate`, `tests/test_gate.py`, `tests/test_report.py`, `tests/test_review.py`, `tests/test_next_version.py` copied, `pyproject.toml`, `.gitignore`, `.github/workflows/test.yml`.

- [ ] Copy `review/`, `scripts/`, the four test files and `.gitignore` from `../ai-pr-review-gate`.
- [ ] Write `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ci-workflows-tools"
version = "1.0.0"
description = "AI PR review gate and release tooling used by vladpetl-dev reusable workflows"
requires-python = ">=3.10"
dependencies = ["anthropic>=1.11,<2", "pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.hatch.build.targets.wheel]
packages = ["review", "scripts"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]
```

- [ ] Write `.github/workflows/test.yml` (job id `test`): on pull_request and push to main; checkout, setup-python 3.12, `pip install -e ".[dev]"`, `ruff check .`, `pytest -q`.
- [ ] Run: `uv venv -q --python 3.12 .venv && uv pip install -q -e ".[dev]" && .venv/bin/pytest -q && .venv/bin/ruff check .` — Expected: 37 passed (39 minus the 2 hello tests), ruff clean.
- [ ] Commit: `feat: review gate and release tooling moved from ai-pr-review-gate`.

### Task 2: Reusable workflows

**Files:** create `.github/workflows/ai-review.yml`, `ci-python.yml`, `release-python.yml`, `README.md`.

- [ ] `ai-review.yml`: `on: workflow_call` with inputs `tools-ref` (default `v1`), `python-version` (default `3.12`), `policy-path` (default `.ai-review/policy.yml`); job `review` with steps: checkout PR to `pr/` (fetch-depth 0, persist-credentials false); checkout `vladpetl-dev/ci-workflows` at `inputs.tools-ref` to `tools/`; checkout `github.base_ref` to `base/` (persist-credentials false); setup-python; `pip install ./tools`; step `policy` that writes `path=base/<policy-path>` if the file exists else `path=tools/review/policy.yml` to `$GITHUB_OUTPUT`; review (`python -m review.review --repo pr --base origin/<base_ref> --head HEAD --policy <path>`, env `ANTHROPIC_API_KEY`); report (always); PR comment with `--repo` (always, same-repo PRs only); artifact (always); gate; Slack on failure (skip when `SLACK_WEBHOOK_URL` empty). All commands run from the workspace root using the installed package (no `working-directory`).
- [ ] `ci-python.yml`: `on: workflow_call` input `python-version`; job `build`: checkout (fetch-depth 0), setup-python, `pip install -e ".[dev]"`, `ruff check .`, `pytest -q`, `python -m build`, upload `dist/`.
- [ ] `release-python.yml`: `on: workflow_call` inputs `tools-ref`, `python-version`; job `release` with `if: github.event.workflow_run.conclusion == 'success' && github.event.workflow_run.event == 'push'`; checkout consumer at `github.event.workflow_run.head_sha` (fetch-depth 0); checkout tools to `tools/`; version step with `tag=$(python tools/scripts/next_version.py --notes-out notes.md)` (cwd = consumer, so consumer tags are used); tag push, build, `gh release create` when tag non-empty. `tools/` and `notes.md` must not end up in the build: build with `python -m build` from the consumer root — `tools/` is not a package of the consumer (packages are listed explicitly) and hatch-vcs ignores untracked files.
- [ ] Validate all YAML with `yaml.safe_load`; README with consumer snippets.
- [ ] Commit: `feat: reusable ai-review, ci and release workflows`.

### Task 3: Publish central repo

- [ ] Create `vladpetl-dev/ci-workflows` (public) via `gh repo create`; set remote `https://vladpetl1987-star@github.com/vladpetl-dev/ci-workflows.git`; push `main`.
- [ ] Wait for `test` workflow green.
- [ ] Tag `v1.0.0` and `v1`, push tags.
- [ ] Ruleset on `main`: PR required, required check `test`, no force push/deletion.

### Task 4: Transfer consumer repo

- [ ] `gh api -X POST repos/vladpetl1987-star/ai-pr-review-gate/transfer -f new_owner=vladpetl-dev`; update local remote to `https://vladpetl1987-star@github.com/vladpetl-dev/ai-pr-review-gate.git`.
- [ ] Owner adds organization secrets `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL` (selected repo: `ai-pr-review-gate`).

### Task 5: Consumer refactor PR

**Files (consumer):** delete `review/`, `scripts/`, `tests/test_gate.py`, `tests/test_report.py`, `tests/test_review.py`, `tests/test_next_version.py`; modify `pyproject.toml` (drop `review` extra; `dev = ["pytest>=8", "ruff>=0.6", "build>=1.2"]`), rewrite the three workflows as thin callers, update `README.md`.

- [ ] Update ruleset `protect-main` required checks to `ci / build` and `ai-review / review`.
- [ ] Branch `refactor/central-workflows`, apply the file changes, run `.venv/bin/pytest -q` (2 passed) and `ruff check .`.
- [ ] Commit `refactor: use central reusable workflows from vladpetl-dev/ci-workflows`, push, open PR.
- [ ] Expected: `ci / build` and `ai-review / review` green (deleting code is not a vulnerability), merge allowed; squash-merge; release `v0.2.1` published.

### Task 6: Secrets cleanup and end-to-end

- [ ] Owner deletes repository-level `ANTHROPIC_API_KEY` and `SLACK_WEBHOOK_URL` from `ai-pr-review-gate`.
- [ ] Branch with `app/shell.py` command injection → PR. Expected: `ai-review / review` red, merge blocked, PR comment, Slack message (proves org secrets are used). Close the PR without merge, delete the branch.
