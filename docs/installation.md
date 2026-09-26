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

Motif Balance supports Python 3.12–3.14 on Linux and macOS. The package includes
the Python library and command-line interface.

## Start a project with uv

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uv init --python 3.12 motif-example
cd motif-example
uv add motif-balance
uv run motif-balance --help
```

Continue with the ArgR/Cra [README example](../README.md#try-a-design).
In an existing uv project, run only `uv add motif-balance`.
`uv add` records the dependency and updates the project's lockfile; `uv run`
keeps its environment in sync before running the command.
This follows uv's [project workflow](https://docs.astral.sh/uv/concepts/projects/layout/).

SVG figures and HTML inspection work with the base installation. For PNG,
animated GIF, and MP4 exports, add the visualization extra:

```bash
uv add 'motif-balance[visualization]'
```

## Install with pip

If you already use pip, install into a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install motif-balance
motif-balance --help
```

Run Python and package commands directly in that activated environment.
The optional media package is `motif-balance[visualization]`.

## Install from source

A source checkout is for contributing or changing the bundled recipes. Follow [development setup](../CONTRIBUTING.md#development),
then prepare the attributed example inputs:

```bash
uv run python examples/argr-cra/prepare_inputs.py
```

Continue with the [ArgR/Cra tutorial](quickstart.md) or the
[twelve-model example](biological-example.md).
