# Release Captain

*An evidence-led release workflow with a human approval gate.*

## Problem and workflow

Release teams reconcile commits, pull requests, diffs, tags and CI to choose versions and write notes. Scattered evidence makes signals easy to miss.

Users provide a repository, branch, optional tag and allowlisted test command. Live mode uses that tag, the latest tag or a default-branch comparison, then collects commits, linked pull requests, changed-file summaries and recent Actions runs. Commit-message rules categorize changes and flag breaking markers; removed files and CI failures become risks. Release Captain recommends a semantic version and drafts notes. The review shows evidence, risks, test status and audit events, then stops at `WAITING FOR HUMAN APPROVAL`. Approval must match the repository, version and action list.

## Architecture and TrueForge

The Next.js dashboard uses FastAPI for GitHub collection, deterministic analysis, session state, approval validation, audit and execution. A checked-in TrueForge manifest and Python SDK connector can register or sync the agent and stream sessions when TrueForge and GitHub MCP are configured. Dashboard recommendations use deterministic FastAPI rules; its sessions do not pass through the connector.

## What's implemented and current limits

Live GitHub analysis is implemented. After exact-plan approval, the backend can create a Git tag and GitHub release when execution is enabled and the token has write access. Demo evidence, passing tests and post-approval actions are simulated. TrueForge sandbox is disabled by default. The optional test runner executes allowlisted commands on local clones of public repositories, outside a sandbox. Version bumps follow commit prefixes and explicit breaking markers; removed files and CI failures appear as risks. These checks are limited; review each recommendation. Session and audit history are in memory; backend restart clears them. Publishing and deployment are not implemented.
