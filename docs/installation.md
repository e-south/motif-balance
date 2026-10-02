# Install Motif Balance

Motif Balance supports Python 3.12–3.14 on Linux and macOS. The package includes
the Python library and command-line interface.

## Start a project with uv

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```bash
uv init --python 3.12 my-project
cd my-project
uv add motif-balance
uv run motif-balance --help
```

Continue with the ArgR/Cra [README example](../README.md#try-a-design).
In an existing uv project, run only `uv add motif-balance`.
`uv add` records the dependency in your project and lockfile. `uv run` uses
that project's environment.

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

Use a source checkout to contribute. Installed examples can be prepared directly
with `motif-balance example`; no checkout is needed to edit their requests. Follow
[development setup](../CONTRIBUTING.md#development), then prepare the attributed
example inputs:

```bash
uv run python examples/argr-cra/prepare_inputs.py
# Continue where design.yaml and its prepared inputs live.
cd examples/argr-cra
```

Continue with the [ArgR/Cra tutorial](quickstart.md) in that directory.
The separate [twelve-model example](../examples/twelve-motifs/README.md)
runs from the repository root.

For reproducible work, record the installed package version and preserve the project's
`uv.lock`. A source checkout can contain changes beyond the latest release. Record
its commit and any local changes rather than identifying it solely as that release.
