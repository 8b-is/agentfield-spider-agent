# Git hooks

This directory holds repo-tracked git hooks. To activate them after a fresh
clone, run **once** at the repo root:

```bash
git config core.hooksPath .githooks
```

## Hooks

- `pre-commit` — spawns [difit](https://github.com/yoshiko-pg/difit) on staged
  changes in a local web UI. Non-blocking: the commit proceeds immediately
  while the diff opens in your browser for review.
