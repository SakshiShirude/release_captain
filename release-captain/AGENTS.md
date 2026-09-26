# Release Captain — ShiftLeft

## Mission

Build Release Captain, a safe AI release-engineering agent for the TrueFoundry
"Agents That Act" hackathon.

The agent must:

1. Read a GitHub repository.
2. Identify changes since the latest release tag.
3. Read commits, pull requests, and CI information where available.
4. Categorize changes.
5. Detect possible breaking changes.
6. Recommend a semantic version bump.
7. Run the repository test command in an isolated sandbox.
8. Generate evidence-backed release notes.
9. Stop at a human approval gate.
10. Never create a tag, publish a package, or deploy without explicit approval.

## Important implementation rule

Do not invent TrueForge SDK functions or configuration fields.

Before integrating with TrueForge:

- Inspect the installed TrueForge version.
- Read the local documentation or official documentation.
- Inspect available CLI commands.
- Inspect examples in the official repository.
- Keep TrueForge-specific code isolated behind an adapter.
- If the Python SDK is unavailable, implement a clean HTTP/API adapter or CLI adapter
  based only on verified documentation.
- Clearly mark any integration that requires manual configuration.

Official references:

- https://trueforge.dev
- https://github.com/truefoundry/trueforge
- https://www.truefoundry.com/docs/agent-platform/agent-harness/overview

## Technology

- Python 3.11+
- FastAPI
- Pydantic v2
- httpx
- GitHub REST API
- pytest
- Docker or the configured TrueForge sandbox
- Minimal HTML/CSS/JavaScript frontend served by FastAPI
- Optional Three.js or CSS-based 3D animation
- No React or separate Node frontend unless explicitly requested

## Repository structure

Create this structure:

release-captain/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── routes.py
│   ├── services/
│   │   ├── github_service.py
│   │   ├── analysis_service.py
│   │   ├── test_service.py
│   │   ├── release_service.py
│   │   └── trueforge_adapter.py
│   └── prompts/
│       └── release_captain.md
├── web/
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── tests/
│   ├── test_health.py
│   ├── test_analysis.py
│   └── test_semver.py
├── sample-repo/
├── .env.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
└── AGENTS.md

## Coding standards

- Use type hints everywhere.
- Use Pydantic models for request and response data.
- Use async FastAPI endpoints where appropriate.
- Keep GitHub, sandbox, LLM, and TrueForge integrations separate.
- Never place secrets in source code.
- Read secrets only from environment variables.
- Add useful error messages.
- Add tests for deterministic logic.
- Do not execute arbitrary shell commands directly from HTTP request input.
- Use an allowlist for supported test commands.
- Apply timeouts to network calls and test execution.
- Store audit events for every major action.
- Make the application runnable in demo mode without real credentials.

## Safety policy

The following operations are read-only or reversible:

- Reading tags.
- Reading commits.
- Reading pull requests.
- Reading CI status.
- Running analysis.
- Running tests in an isolated environment.
- Generating release notes.

The following operations are destructive or externally visible:

- Creating a Git tag.
- Publishing to npm, PyPI, or another registry.
- Triggering a deployment.
- Merging a pull request.
- Modifying repository files.

These operations must be represented by a separate approval-required action.
The backend must reject them unless approval has explicitly been recorded for the
same release plan, version, repository, and action list.

## Demo mode

Implement DEMO_MODE=true.

When demo mode is enabled:

- Use deterministic sample commits and pull requests.
- Simulate sandbox test execution with realistic output.
- Simulate a passing test suite and a second scenario with a failing test.
- Never call external write APIs.
- Show the approval gate.
- Show the exact actions that would happen after approval.
- Keep the UI functional without GitHub or OpenAI credentials.

## Primary user flow

1. User enters repository URL, branch, and optional previous tag.
2. User clicks "Analyze release".
3. Backend creates a release session.
4. UI displays:
   - Fetching repository data.
   - Categorizing changes.
   - Detecting breaking changes.
   - Running sandbox tests.
   - Generating release notes.
5. Backend produces a ReleasePlan.
6. UI displays:
   - Recommended version.
   - Change categories.
   - Breaking-change risks.
   - Test evidence.
   - Proposed actions.
7. UI displays "WAITING FOR HUMAN APPROVAL".
8. User can approve or request changes.
9. Approval must be tied to the exact plan.
10. In demo mode, execution is simulated and recorded in the audit timeline.
11. In real mode, write actions are executed only through verified, approval-aware tools.

## Required API endpoints

Implement:

GET /api/health

POST /api/sessions

GET /api/sessions/{session_id}

POST /api/sessions/{session_id}/approve

POST /api/sessions/{session_id}/request-changes

GET /api/sessions/{session_id}/audit

GET /api/sessions/{session_id}/evidence

The API must return stable JSON that the frontend can consume.

## Required data models

Create models for:

- ReleaseSession
- CommitChange
- PullRequestChange
- TestResult
- Risk
- ReleasePlan
- ApprovalRequest
- AuditEvent
- SessionStatus

Use explicit statuses:

created
collecting
analyzing
testing
ready_for_approval
approved
executing
completed
rejected
failed

## Release analysis rules

Use deterministic rules before asking an LLM for interpretation:

- Commit prefix "feat" means feature.
- Commit prefix "fix" means fix.
- Commit prefix "docs" means documentation.
- Commit prefix "refactor" means refactor.
- Commit prefix "chore" means chore.
- "BREAKING CHANGE" or "!" after the commit type means breaking.
- Removal of public functions, classes, routes, fields, or exports is a possible breaking change.
- A major dependency upgrade is a possible risk.
- If a breaking change is confirmed or strongly indicated, recommend major.
- Else if a feature exists, recommend minor.
- Else recommend patch.
- Always include evidence for the recommendation.

## Test execution rules

Only support allowlisted commands:

- pytest
- python -m pytest
- npm test
- yarn test
- pnpm test

Never accept arbitrary command strings from a public request.

The test result must include:

- command
- status
- exit code
- duration
- passed count where available
- failed count where available
- log excerpt
- sandbox/provider name

## UI requirements

Build a clean dark release-control dashboard.

Visual style:

- Background: near-black navy.
- Accent: cyan and violet.
- Status colors:
  - cyan = running
  - green = passed
  - amber = approval required
  - red = failed or risky
- Use glass-like cards sparingly.
- Use a responsive layout.
- Avoid excessive gradients.
- Avoid distracting animations.

Include:

- ShiftLeft logo text.
- Release Captain title.
- Repository input form.
- Pipeline progress component.
- Release plan card.
- Risk card.
- Test evidence card.
- Approval gate card.
- Audit timeline.
- A subtle 3D CSS release capsule or rotating orb.
- Reduced-motion support using prefers-reduced-motion.

The UI must make it obvious:

- What the agent is doing.
- What evidence it found.
- What it recommends.
- What is waiting for approval.
- What will happen after approval.
- What will never happen automatically.

## Final acceptance criteria

Before declaring the work complete:

1. Run the backend tests.
2. Start the FastAPI server.
3. Open the dashboard.
4. Run the complete demo flow in DEMO_MODE=true.
5. Confirm the approval gate pauses execution.
6. Confirm approve and request-changes flows work.
7. Confirm no destructive operation occurs in demo mode.
8. Confirm README setup instructions work.
9. Confirm no secrets are committed.
10. Report completed tasks, remaining tasks, known limitations, and demo commands.