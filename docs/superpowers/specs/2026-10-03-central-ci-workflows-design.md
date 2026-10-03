# Central CI Workflows — Design

Date: 2026-10-03
Status: approved in chat

## Purpose

Move the AI review gate, CI and release logic out of the application repository into one
central, versioned repository. Application repositories keep only thin workflow files that
call the central reusable workflows. Shared secrets live at the GitHub Organization level.

Success criteria:

1. `ai-pr-review-gate` contains no review/release code — only its app and three workflow files
   of a few lines each that call `vladpetl-dev/ci-workflows/...@v1`.
2. `ANTHROPIC_API_KEY` and `SLACK_WEBHOOK_URL` are organization secrets shared with selected
   repositories; the application repository has no repository-level copies.
3. End to end on the application repo: vulnerable PR → `ai-review / review` red, merge blocked,
   PR comment, Slack message; fixed PR → green → merge → GitHub Release.
4. A PR in the application repo cannot change the review code or the default policy.

## Organization

Free GitHub Organization `vladpetl-dev`, owned by `vladpetl1987-star`. Both repositories are
public (rulesets are enforced for public repos on the free plan).

## Central repository `vladpetl-dev/ci-workflows`

```
review/                         review.py, gate.py, report.py, config.py, schema.py, policy.yml
scripts/next_version.py
tests/                          gate, report, review, next_version tests
.github/workflows/ai-review.yml       on: workflow_call
.github/workflows/ci-python.yml       on: workflow_call
.github/workflows/release-python.yml  on: workflow_call
.github/workflows/test.yml            this repo's own CI (ruff + pytest)
pyproject.toml                  installable package (review + scripts), deps anthropic, pyyaml
README.md                       usage for consumers
```

Versioning: tags `vX.Y.Z` plus a moving major tag `v1`. Consumers pin `@v1`.

### `ai-review.yml` (workflow_call)

Inputs: `tools-ref` (default `v1`, must match the `@ref` the caller uses), `python-version`
(default `3.12`), `policy-path` (default `.ai-review/policy.yml`).
Job id `review`. Steps: checkout the PR (`pr/`, full history, no persisted credentials),
checkout `ci-workflows` at `tools-ref` (`tools/`), checkout the consumer's base branch
(`base/`) to read an optional policy override, install `./tools`, run review → report →
PR comment (same-repo PRs only) → artifact → gate → Slack on failure. Uses secrets passed with
`secrets: inherit`.

Policy resolution: `base/<policy-path>` if it exists on the base branch, else
`tools/review/policy.yml`. The PR head is never a policy source.

### `ci-python.yml` (workflow_call)

Input `python-version`. Job id `build`: checkout, `pip install -e ".[dev]"`, `ruff check .`,
`pytest -q`, `python -m build`, upload `dist/`.

### `release-python.yml` (workflow_call)

Inputs `tools-ref`, `python-version`. Called from the consumer's `workflow_run` workflow; job id
`release`; runs only when the triggering `ci` run succeeded on a push. Checks out the consumer at
`github.event.workflow_run.head_sha`, computes the version with `tools/scripts/next_version.py`,
pushes the tag, builds, creates the GitHub Release. Needs `contents: write` from the caller.

## Consumer repository `vladpetl-dev/ai-pr-review-gate`

Transferred from `vladpetl1987-star` (GitHub keeps a redirect). After the change it contains
`app/`, `tests/test_hello.py`, `pyproject.toml` (dev extra: pytest, ruff, build), `README.md`,
`docs/`, and three workflows:

- `ci.yml`: `jobs.ci.uses: vladpetl-dev/ci-workflows/.github/workflows/ci-python.yml@v1`
- `ai-review.yml`: `jobs.ai-review.uses: .../ai-review.yml@v1`, `secrets: inherit`,
  permissions `contents: read`, `pull-requests: write`
- `release.yml`: `workflow_run` on `ci`, `jobs.release.uses: .../release-python.yml@v1`,
  permissions `contents: write`

Required status checks (ruleset `protect-main`) become `ci / build` and `ai-review / review`.

## Secrets

Organization secrets `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`, visibility "selected
repositories" = `ai-pr-review-gate`. Added by the owner. Repository-level copies are deleted
afterwards (repository secrets would otherwise shadow organization secrets).

## Migration order

1. Owner creates the organization.
2. Transfer `ai-pr-review-gate` to the organization.
3. Create and push `ci-workflows`; tag `v1.0.0` and `v1`; protect its `main`.
4. Owner adds organization secrets.
5. Update the consumer ruleset to the new check names, then open the refactor PR (it must be
   reviewed by the new workflows to merge).
6. Merge → release; delete repository-level secrets; end-to-end PR with a vulnerability.

## Out of scope

Docker/Bitbucket Pipe packaging, publishing to PyPI, the deferred minor findings from the first
review.
