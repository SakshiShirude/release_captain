# Release Captain

Release Captain is a production-minded release engineering agent built for the TrueFoundry / TrueForge hackathon.

The working application lives in [`release-captain/`](/Users/aryansinha/release_captain/release_captain/release-captain), which contains the FastAPI backend, TrueForge integration, tests, demo assets, and submission writeup.

## What it does

Release Captain takes a GitHub repository, branch, optional previous tag, and test command, then:

- collects release evidence from GitHub
- categorizes changes into features, fixes, docs, refactors, and chores
- detects possible breaking changes and risk
- recommends the next semantic version
- generates release notes
- stops at a strict human approval gate
- optionally executes controlled GitHub release actions

## Repo layout

- `release-captain/` — main app and hackathon submission assets
- `release-captain/app/` — FastAPI backend
- `release-captain/agent/` — agent-side logic and prompts
- `release-captain/tests/` — backend tests
- `release-captain/demo/` — demo deck and talk track

## Quick start

```bash
cd release-captain
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8001
```

Demo mode:

```bash
cd release-captain
DEMO_MODE=true RELEASE_CAPTAIN_SANDBOX_ENABLED=false uvicorn app.main:app --reload --port 8001
```

Real analysis mode:

```bash
cd release-captain
GITHUB_TOKEN=your_token DEMO_MODE=false RELEASE_CAPTAIN_SANDBOX_ENABLED=false uvicorn app.main:app --reload --port 8001
```

## Submission assets

- Solution writeup: [`release-captain/SUBMISSION_WRITEUP.md`](/Users/aryansinha/release_captain/release_captain/release-captain/SUBMISSION_WRITEUP.md)
- Demo deck: [`release-captain/demo/release-captain-hackathon-deck.html`](/Users/aryansinha/release_captain/release_captain/release-captain/demo/release-captain-hackathon-deck.html)
- Demo talk track: [`release-captain/demo/release-captain-demo-talk-track.md`](/Users/aryansinha/release_captain/release_captain/release-captain/demo/release-captain-demo-talk-track.md)

For deeper implementation details, see [`release-captain/README.md`](/Users/aryansinha/release_captain/release_captain/release-captain/README.md).
