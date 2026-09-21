# Contributing

Start with the [task documentation](docs/README.md) and [module overview](ARCHITECTURE.md).

## Development

```bash
uv sync --locked --group dev
bash ./scripts/preflight --strict
bash ./scripts/verify
```

Run relevant tests while editing and the full verification command before submitting.
Add a regression test for behavior changes. Preserve the [scoring and selection
contracts](DESIGN.md); describe compatibility changes to scores or schemas explicitly.

## Pull requests

Explain the problem, what changed and how you checked it. Update examples or
command documentation when needed. Keep numerical changes separate from refactors.
Public motif examples need source identifiers and redistribution terms.

See the [security policy](SECURITY.md) for sensitive reports and the
[release procedure](docs/reference/prerelease.md) for distribution builds.
