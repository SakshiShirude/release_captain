## Release engineering rules

Use these deterministic rules before asking a model to interpret ambiguous changes:

- `feat` means feature and normally requires a minor bump.
- `fix` means bug fix and normally requires a patch bump.
- `docs`, `refactor`, and `chore` do not independently require a minor bump.
- `BREAKING CHANGE` or `!` after a Conventional Commit type indicates a major bump.
- Removed public functions, classes, routes, fields, or exports are possible breaking changes.
- A major dependency upgrade is a possible risk and needs evidence.
- Breaking changes take precedence over features; features take precedence over fixes.
- In analysis-only mode, still inspect the repository directly through available
  GitHub tools. Analysis-only means no sandbox execution, not no repository access.
- If no previous tag is available, use the diff against the default branch and
  state that fallback explicitly.
- CI failures, removed files, or missing test evidence must be reflected in the risk section.

Every recommendation must include:

1. The previous tag or current version used as the baseline.
2. The evidence that triggered the bump.
3. Test command, result, exit code, and sandbox/provider.
4. Risks and unresolved uncertainty.
5. The exact actions that remain blocked until approval.
6. A clear distinction between observed evidence and inferred risk.

Release notes should be concise, grouped by category, and must not claim that
demo or simulated evidence came from the target repository.

Approval discipline:

1. Do not create tags, releases, merges, publishes, or deployments during analysis.
2. Do not imply those actions already happened.
3. Stop with an explicit `WAITING FOR HUMAN APPROVAL` status once the plan is ready.
