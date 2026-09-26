# Release Captain (ShiftLeft)

> **“Agents That Act” — TrueFoundry × Polaris Hackathon**

Release Captain is an autonomous release engineering agent built on the **TrueForge Agent Harness**. It shifts release preparation left by gathering commits and pull requests, executing automated tests in sandboxed environments, reasoning about semantic versioning and breaking changes, and enforcing human-in-the-loop approval gates before publishing releases.

---

## Architecture & Workflow

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         Release Captain (ShiftLeft)                 │
│  “Agents That Act” — TrueFoundry × Polaris Hackathon                │
└─────────────────────────────────────────────────────────────────────┘

                          ┌───────────────────┐
                          │   Human Operator  │
                          │ (Release Manager) │
                          └─────────┬─────────┘
                                    │ 1. Trigger release analysis
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        TrueForge Agent Harness                      │
│  • MCP tools (GitHub, Sandbox, Package Registry)                    │
│  • Sandboxed code execution                                         │
│  • Approval checkpoints (gate before tag/publish)                   │
│  • Session persistence                                              │
└─────────────────────────────────────────────────────────────────────┘
         │                    │                     │
         │ 2a. Fetch commits  │ 2b. Run tests      │ 2c. Read PRs
         ▼                    ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│  GitHub MCP     │  │  Sandbox MCP    │  │  GitHub MCP (PRs)       │
│  • commits      │  │  • clone repo   │  │  • titles, labels       │
│  • tags         │  │  • install deps │  │  • reviewers, status    │
│  • PR metadata  │  │  • run tests    │  │                         │
└─────────────────┘  └─────────────────┘  └─────────────────────────┘
         │                    │                     │
         └────────────────────┴─────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  Reasoning Engine   │
                   │  (LLM via TrueForge)│
                   │  • categorize       │
                   │  • detect breaking  │
                   │  • recommend bump   │
                   │  • draft notes      │
                   └─────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  Approval Gate      │
                   │  (TrueForge checkpoint)
                   │  • show summary     │
                   │  • risks, test report
                   │  • WAIT FOR HUMAN   │
                   └─────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
      [APPROVED]                      [REJECTED / EDITS]
              │                               │
              ▼                               ▼
   ┌─────────────────────┐         ┌─────────────────────┐
   │  Execute Release    │         │  Report & Loop Back │
   │  • create git tag   │         │  • show why rejected│
   │  • publish to npm   │         │  • suggest fixes    │
   │  • trigger deploy   │         └─────────────────────┘
   └─────────────────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Audit Log & Report │
   │  • what was done    │
   │  • evidence bundle  │
   └─────────────────────┘
```

---

## Key Phases

### 1. Trigger & Ingestion
- **Human Operator** initiates the release analysis workflow.
- **GitHub MCP**: Fetches commits, recent tags, PR titles, labels, reviewers, and approval states since the last release.
- **Sandbox MCP**: Clones the target repository, sets up dependencies in an isolated sandbox, and executes the test suite.

### 2. Analysis & Reasoning
- **Categorization**: Groups changes into features, bug fixes, performance improvements, documentation, and chores.
- **Breaking Change Detection**: Identifies incompatible API or schema alterations.
- **SemVer Recommendation**: Computes next version (Major, Minor, or Patch) based on semantic commit guidelines.
- **Changelog Drafting**: Automatically generates clean release notes and highlights risks.

### 3. Human-in-the-Loop Approval Gate
- Displays release capsule summary, test verification report, and identified risks.
- Halts execution at a **TrueForge checkpoint**, awaiting explicit operator review:
  - **Approved**: Proceeds with execution.
  - **Rejected / Edits Requested**: Feeds operator feedback back into the loop to adjust release parameters or address issues.

### 4. Release Execution & Audit
- Creates git tags and releases on GitHub.
- Publishes packages to designated registries (e.g., npm, PyPI).
- Dispatches deployment workflows.
- Generates a comprehensive audit log and evidence bundle documenting all actions taken.

---

## Project Structure

```text
release-captain/
├── agent/                   # Agent logic and MCP integrations
│   ├── tools/               # MCP tools (GitHub, sandbox runner, categorizer)
│   ├── release_captain.py   # Agent core implementation
│   └── system_prompt.md     # Agent system prompt and operational instructions
├── skills/                  # Domain knowledge and release engineering guidelines
│   └── release-engineering.md
├── ui/                      # Web interface for human operators
│   ├── app/                 # Next.js application routes
│   ├── components/          # UI components (ReleaseCapsule, GenerativeUIRenderer)
│   └── lib/                 # TrueForge client integration
├── trueforge.yaml           # TrueForge agent harness configuration
└── requirements.txt         # Python dependencies
```
