# Release Captain demo talk track

Use this with the 5-slide deck for a short hackathon demo.

## Slide 1 — Release Captain

“Release Captain is an AI release engineering agent. You give it a GitHub repo, a branch, and optionally a previous tag. It reads what changed, recommends the next version, drafts release notes, highlights risk, and waits for human approval before taking any release action.”

## Slide 2 — The problem

“Today, release decisions are scattered across commits, PRs, CI, and tags. Teams either do a lot of manual work or automate too aggressively. Our goal was to build an agent that behaves more like a careful release engineer than a generic chatbot.”

## Slide 3 — The workflow

“The flow is strict. First we create a release session. Then the agent collects evidence from GitHub, analyzes the impact, recommends a semantic version, generates release notes, and stops at `ready_for_approval`. Only after exact approval can it execute controlled actions.”

## Slide 4 — What is real today

“The important point is that this backend is not fake. It already performs real GitHub analysis, real semver reasoning, real release-note generation, and stores an audit trail. It also handles execution outcomes safely — completed, blocked, or failed with a reason.”

## Slide 5 — The live demo

“In the demo I’ll create a session for a public GitHub repo, show the evidence and release plan, then approve it. If execution is blocked because the token is read-only or the repo is not writable, I’ll call that out as a safety feature. The system should never silently perform release actions it is not authorized to do.”

## Good closing line

“Release Captain turns release management from tribal knowledge into a verified, human-governed workflow.”
