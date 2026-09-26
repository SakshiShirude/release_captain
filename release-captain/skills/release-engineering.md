## Release engineering rules

Use these deterministic rules before asking a model to interpret ambiguous changes:

- `feat` means feature and normally requires a minor bump.
- `fix` means bug fix and normally requires a patch bump.
- `docs`, `refactor`, and `chore` do not independently require a minor bump.
- `BREAKING CHANGE` or `!` after a Conventional Commit type indicates a major bump.
- Removed public functions, classes, routes, fields, or exports are possible breaking changes.
- A major dependency upgrade is a possible risk and needs evidence.
- Breaking changes take precedence over features; features take precedence over fixes.

Every recommendation must include:

1. The previous tag or current version used as the baseline.
2. The evidence that triggered the bump.
3. Test command, result, exit code, and sandbox/provider.
4. Risks and unresolved uncertainty.
5. The exact actions that remain blocked until approval.

Release notes should be concise, grouped by category, and must not claim that
demo or simulated evidence came from the target repository.
