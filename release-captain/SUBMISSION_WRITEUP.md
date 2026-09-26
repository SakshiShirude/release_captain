# Release Captain — Solution Writeup

Release Captain solves a common release-engineering problem: deciding what is safe and meaningful to ship is usually manual, fragmented, and error-prone. Teams must inspect commits, pull requests, changed files, CI runs, tags, and release notes, then still make a judgment call on versioning and execution. Our goal was to turn that into a structured, human-governed AI workflow.

The agent takes a GitHub repository, branch, optional previous tag, and test command. It then collects repository evidence, categorizes changes into features, fixes, documentation, refactors, and chores, detects possible breaking changes, recommends the next semantic version, drafts release notes, and stops at a strict approval gate. After that point, it can optionally execute controlled release actions such as creating a tag or GitHub release.

The architecture has two layers. The backend is a FastAPI service that manages release sessions, audit events, approval validation, evidence, test results, and execution outcomes. The agent layer is connected through TrueForge, which is used to define the release-engineering behavior, create synced agents, and run persistent sessions. This gives us a real orchestration layer instead of a one-shot script.

What is real today: GitHub repository analysis, semantic version recommendation, structured release notes, approval matching, audit trail, and safe execution outcomes. What is conditional or limited: isolated sandbox test execution depends on runtime availability, and real post-approval execution requires a GitHub token with write access to the target repository.

Known limits: the current implementation is GitHub-focused, the UI is lighter than the backend, and some deployment actions remain intentionally conservative. Even so, the system already behaves like a production-minded release copilot: evidence first, human approval before action, and explicit handling of risk, permissions, and failure.
