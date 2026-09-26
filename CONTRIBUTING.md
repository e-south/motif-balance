# Contributing

Start with the [task documentation](docs/README.md) and [module overview](ARCHITECTURE.md).

## Development

With Git and [uv](https://docs.astral.sh/uv/) installed:

```bash
git clone https://github.com/e-south/motif-balance.git
cd motif-balance
# Install the locked development tools and library dependencies.
uv sync --locked --group dev
# Prepare the environment and check the repository contracts.
bash ./scripts/preflight --strict
# Run tests, documentation checks and package-installation checks.
bash ./scripts/verify
```

Run relevant tests while editing and the full verification command before submitting.
Add a regression test for behavior changes. Preserve the [scoring and selection
contracts](DESIGN.md); describe compatibility changes to scores or schemas explicitly.

Use the module header in existing source files: package name, repository-relative
path, a short purpose, and author attribution. Apply it to tests and scripts too;
shell scripts use comment lines below their shebang.

## Pull requests

Explain the problem, what changed and how you checked it. Update examples or
command documentation when needed. Keep numerical changes separate from refactors.
Public motif examples need source identifiers and redistribution terms.

See the [security policy](SECURITY.md) for sensitive reports and the
[release procedure](docs/reference/prerelease.md) for distribution builds.
