# Release Checklist

Before publishing:

- Run dashboard tests.
- Run repo-level tests.
- Run `./scripts/sanitize-repo-check.sh`.
- Confirm `git status --short` contains only intended files.
- Inspect all env examples for placeholders only.
- Inspect systemd examples for placeholders only.
- Confirm no `.env`, logs, runtime images, caches, OpenClaw config, Codex config,
  or SSH data are tracked.
- Confirm docs use placeholders for users, hosts, paths, and provider keys.
- Confirm hardware assumptions are labeled as assumptions, not guarantees.

First public push should happen only after a manual diff review.
