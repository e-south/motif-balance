---
doc_id: motif-balance-installation
title: Install Motif Balance
intent: Install the package without a research workspace.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-26
doc_type: how-to
---

# Install Motif Balance

Motif Balance supports Python 3.12–3.14 on Linux and macOS.

## Install with pip

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install motif-balance
motif-balance --help
```

The package includes the Python library and command-line interface. For PNG,
GIF, and MP4 exports, install the optional media dependencies:

```bash
python -m pip install 'motif-balance[visualization]'
```

SVG figures and HTML inspection work with the base installation.
The [Python API](python-api.md) accepts your own prepared motif models.

## Install from source

The biological tutorials also use scripts and input records in the repository.
With Git and [uv](https://docs.astral.sh/uv/) installed:

```bash
git clone https://github.com/e-south/motif-balance.git
cd motif-balance
uv sync --locked --extra visualization
uv run python examples/argr-cra/prepare_inputs.py
uv run motif-balance --help
```

Continue with [First design](quickstart.md) or the
[twelve-model example](biological-example.md). If you already installed with pip,
clone the repository for its example files and run `python` and `motif-balance`
in your activated environment instead of `uv run`.

Development and release checks are described in [Contributing](../CONTRIBUTING.md).
