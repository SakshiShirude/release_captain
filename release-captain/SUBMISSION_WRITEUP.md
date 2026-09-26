# Release Captain — Solution Writeup

Release Captain solves a common release-engineering problem: deciding what is meaningful to ship is usually manual, fragmented, and slow. Teams must inspect commits, pull requests, changed files, CI runs, tags, and release notes, then still make a judgment call on versioning and execution. Our goal was to turn that into a structured, human-governed AI workflow.

The agent takes a GitHub repository, branch, optional previous tag, and test command. It then collects repository evidence, categorizes changes into features, fixes, documentation, refactors, and chores, detects major change signals, recommends the next semantic version, drafts release notes, and stops at a strict approval gate. After that point, it can optionally execute controlled release actions such as creating a tag or GitHub release.

The architecture has two layers. The backend is a FastAPI service that manages release sessions, audit events, approval validation, evidence, test results, and execution outcomes. The agent layer is connected through TrueForge, which is used to define the release-engineering behavior, create synced agents, and run persistent sessions. This gives us a real orchestration layer instead of a one-shot script.

What is real today: GitHub repository analysis, semantic version recommendation, structured release notes, approval matching, audit trail, and governed execution outcomes. Demo mode is available for deterministic local development, while real execution can operate with the appropriate GitHub permissions.

The current scope is intentionally focused: GitHub-first analysis, a strong backend workflow, and approval-driven release control. The result is a production-minded release copilot: evidence first, human approval before action, and clear operational traceability throughout the session lifecycle.
