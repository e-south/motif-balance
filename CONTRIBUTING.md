# Contributing to Motif Balance

Contributions should preserve the package's reusable software boundary and
scientific contracts. Start with [the documentation index](docs/index.md),
[architecture](ARCHITECTURE.md), and [engineering contracts](DESIGN.md).

## Development loop

```bash
uv sync --locked
bash ./scripts/agent-preflight --strict
bash ./scripts/agent-verify
```

Add a failing test before behavior changes. Public schema, scoring, or ownership
changes require a compatibility statement and matching documentation. Keep
refactors separate from semantic changes.

## Pull requests

Keep changes narrow enough to review. State the contract affected, negative
paths exercised, compatibility impact, and verification commands. Do not add
private datasets, application-specific identities, credentials, local paths,
or generated output from neighboring repositories. See
[the security policy](SECURITY.md) for sensitive reports.
