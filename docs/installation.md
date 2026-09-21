---
doc_id: motif-balance-installation
title: Install Motif Balance
intent: Install the current prerelease without a research workspace.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: how-to
---

# Install Motif Balance

Motif Balance supports CPython 3.12–3.14 on Linux and macOS. It is currently
available as a source checkout or a supplied prerelease wheel. Installation from
PyPI by package name is not yet available.

## Install a supplied wheel

Create an environment in your working directory and install the actual wheel
you downloaded:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install /path/to/motif_balance-0.6.0a1-py3-none-any.whl
.venv/bin/motif-balance --help
```

Replace the wheel path with your file. To use the shorter commands in these
guides, activate the environment:

```bash
source .venv/bin/activate
motif-balance --help
```

The distribution name and command are `motif-balance`; the Python import is
`motif_balance`. The underscore in a wheel filename is normal packaging syntax.

The wheel installs the library and CLI, not the repository's example folders.
The [Python tutorial](python-api.md) runs from an empty directory. To run the
[biological example](biological-example.md), also obtain its complete input
folder from the same revision as your wheel.

## Install from source

With Git and [uv](https://docs.astral.sh/uv/) installed:

```bash
git clone https://github.com/e-south/motif-balance.git
cd motif-balance
uv sync --locked
uv run motif-balance --help
```

Use `uv run motif-balance` wherever a guide shows `motif-balance`. The locked
environment retains the repository's dependency versions. Development checks
and optional release tooling are described in [Contributing](../CONTRIBUTING.md).

Continue with the [quickstart](quickstart.md) to produce and inspect a result,
or [supply your own motifs](motif-models.md).
