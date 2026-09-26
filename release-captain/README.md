# Release Captain

Release Captain is a production-minded release engineering agent built for the TrueFoundry / TrueForge hackathon flow.

You give it a GitHub repository, branch, and optional previous tag. It analyzes what changed, recommends the next version, generates release notes, summarizes change impact, waits for human approval, and can optionally execute controlled GitHub release actions.

It is designed to work across demo, analysis, and execution-oriented workflows.

## What It Does

Release Captain can:

- read a GitHub repository and target branch
- choose a release baseline from:
  - an explicit previous tag
  - the latest available tag
  - the default branch fallback
- collect evidence:
  - commits
  - merged pull requests linked to commits
  - changed files
  - CI / GitHub Actions runs
- categorize changes into:
  - features
  - fixes
  - documentation
  - refactors
  - chores
- detect major change signals and release impact
- recommend a semantic version bump
- generate polished release notes
- store an audit trail, execution results, and session summary
- stop at a human approval gate
- optionally:
  - create a Git tag
  - create a GitHub release

## Why This Exists

Release decisions are usually scattered across commit history, pull requests, CI logs, changelogs, and tribal knowledge.

Release Captain turns that into one workflow:

1. Collect release evidence
2. Analyze impact
3. Recommend the next version
4. Draft release notes
5. Require explicit approval
6. Execute only when permitted

That makes it useful as both:

- a release analysis copilot
- a controlled release execution agent

## Current Product State

What is real today:

- real GitHub repository analysis through the GitHub REST API
- real semantic version recommendation from collected evidence
- real structured release notes
- real approval workflow
- real audit trail and summaries
- real GitHub release execution path for repositories where the token has write access
- local fallback test runner for public GitHub repos

Current operating modes:

- demo mode for deterministic walkthroughs
- analysis mode for real repository evidence collection
- execution mode for controlled GitHub release actions

## Core Workflow

### 1. Analyze

`POST /api/sessions`

Creates a release-analysis session and:

- reads repository evidence
- computes a release plan
- runs allowlisted tests if configured
- stops at `ready_for_approval`

### 2. Approve

`POST /api/sessions/{session_id}/approve`

Validates the exact plan:

- same repository
- same recommended version
- same proposed actions

Then it:

- records human approval
- simulates execution in demo mode
- executes GitHub release actions in real mode when enabled
- enforces permission-aware execution behavior

### 3. Rerun

`POST /api/sessions/{session_id}/rerun`

Re-runs the same input through the workflow and refreshes the evidence.

## Backend Features

### Release Analysis

- baseline selection from tag or default branch
- commit categorization using deterministic rules
- breaking-change signals from commit messages and file evidence
- CI-aware impact detection
- release-note generation
- session summaries with counts and baseline info

### Approval and Execution

- exact-plan approval matching
- approval-driven execution control
- structured execution results
- Git tag creation
- GitHub release creation
- explicit execution outcome reporting

### Test Handling

Supported commands:

- `pytest`
- `python -m pytest`
- `npm test`
- `yarn test`
- `pnpm test`

Execution modes:

- sandbox-off analysis mode -> tests recorded as analysis-only
- demo mode -> deterministic pass result
- local fallback runner -> clones public repo to temp dir and runs the allowlisted command

## API Overview

Available endpoints:

- `GET /api/health`
- `GET /api/sessions`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/sessions/{session_id}/rerun`
- `POST /api/sessions/{session_id}/approve`
- `POST /api/sessions/{session_id}/request-changes`
- `GET /api/sessions/{session_id}/audit`
- `GET /api/sessions/{session_id}/evidence`

Important response fields:

- `status`
- `plan`
- `test_result`
- `audit`
- `execution_results`
- `summary`
- `evidence`

## Session Statuses

- `collecting`
- `analyzing`
- `testing`
- `ready_for_approval`
- `approved`
- `executing`
- `completed`
- `rejected`
- `failed`

## Environment Flags

### Core flags

- `DEMO_MODE`
  - `true`: deterministic demo data and simulated execution
  - `false`: real GitHub analysis

- `RELEASE_CAPTAIN_SANDBOX_ENABLED`
  - enables test execution flow

- `RELEASE_CAPTAIN_EXECUTION_ENABLED`
  - enables real post-approval GitHub release actions

- `RELEASE_CAPTAIN_LOCAL_TEST_RUNNER_ENABLED`
  - enables local fallback test runner when sandbox execution is not available

- `GITHUB_TOKEN`
  - used for higher API rate limits and GitHub write actions

### Token permissions

For read-only analysis, a read-only GitHub token is enough.

For real execution, the token must have write access to the target repository.

For fine-grained tokens, the important permission is:

- `Contents: Read and write`

And the token must target the exact repository you want to act on.

## Running It

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run tests

```bash
python -m pytest
```

### 3. Start in demo mode

```bash
DEMO_MODE=true RELEASE_CAPTAIN_SANDBOX_ENABLED=false uvicorn app.main:app --reload --port 8001
```

### 4. Start in real analysis mode

```bash
GITHUB_TOKEN=your_token \
DEMO_MODE=false \
RELEASE_CAPTAIN_SANDBOX_ENABLED=false \
uvicorn app.main:app --reload --port 8001
```

### 5. Start with real execution enabled

```bash
GITHUB_TOKEN=your_token \
DEMO_MODE=false \
RELEASE_CAPTAIN_SANDBOX_ENABLED=false \
RELEASE_CAPTAIN_EXECUTION_ENABLED=true \
uvicorn app.main:app --reload --port 8001
```

### 6. Start with local test-runner fallback

```bash
GITHUB_TOKEN=your_token \
DEMO_MODE=false \
RELEASE_CAPTAIN_SANDBOX_ENABLED=true \
RELEASE_CAPTAIN_LOCAL_TEST_RUNNER_ENABLED=true \
uvicorn app.main:app --reload --port 8001
```

## Example API Usage

### Health check

```bash
curl http://127.0.0.1:8001/api/health
```

### Create a release-analysis session

```bash
curl -X POST http://127.0.0.1:8001/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "repository_url": "https://github.com/driceroland/Search",
    "branch": "main",
    "previous_tag": "v1.0.3",
    "test_command": "pytest"
  }'
```

### Approve the exact plan

```bash
curl -X POST http://127.0.0.1:8001/api/sessions/SESSION_ID/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "plan_version": "v1.0.4",
    "repository_url": "https://github.com/driceroland/Search",
    "actions": ["Create tag v1.0.4", "Create GitHub release v1.0.4"]
  }'
```

### Rerun a session

```bash
curl -X POST http://127.0.0.1:8001/api/sessions/SESSION_ID/rerun
```

## TrueForge / Agent Layer

The project also includes a TrueForge agent definition and connection layer:

- [connect.py](./connect.py)
- [trueforge.yaml](./trueforge.yaml)
- [agent/system_prompt.md](./agent/system_prompt.md)
- [skills/release-engineering.md](./skills/release-engineering.md)

The agent is configured to:

- inspect repositories directly
- prefer evidence-backed decisions
- stop at human approval
- behave safely when sandbox execution is unavailable

## Project Structure

```text
release-captain/
├── agent/
│   ├── release_captain.py
│   ├── system_prompt.md
│   └── tools/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── routes.py
│   └── services/
│       ├── analysis_service.py
│       ├── execution_service.py
│       ├── github_service.py
│       ├── release_service.py
│       └── trueforge_adapter.py
├── skills/
│   └── release-engineering.md
├── tests/
│   └── test_backend.py
├── ui/
├── connect.py
├── trueforge.yaml
└── requirements.txt
```

## Testing Status

The backend workflow is covered by automated tests for:

- demo flow
- real GitHub evidence collection
- approval validation
- permission-aware execution handling
- successful execution path
- execution error handling path
- local fallback test runner
- session listing
- rerun behavior

## Current Scope

- GitHub is the primary repository source
- PR discovery uses commit-to-PR linkage available from GitHub
- the local test runner supports analysis workflows for public repositories
- successful GitHub execution uses:
  - a token with write access
  - permission on the target repository

## Control Model

Release Captain is designed for controlled release operations:

- it never accepts arbitrary shell commands
- it only runs allowlisted test commands
- it ties approval to an exact plan
- it records all major actions in the audit trail
- it preserves explicit permission boundaries

## Demo Positioning

The strongest one-line description is:

> Release Captain is a release analysis and controlled execution agent that reads a repository, recommends the next release, drafts release notes, summarizes change impact, and only acts after explicit human approval.
