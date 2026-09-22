---
doc_id: motif-balance-installation
title: Install Motif Balance
intent: Install the current prerelease without a research workspace.
audience: [users]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-22
doc_type: how-to
---

# Install Motif Balance

Use the source checkout to run all bundled examples. The current prerelease
supports Python 3.12–3.14 on Linux and macOS.

## Install from source

With Git and [uv](https://docs.astral.sh/uv/) installed:

```bash
# Download the library, documentation and example motif files.
git clone https://github.com/e-south/motif-balance.git
# Enter the checkout so uv can find the project and its lockfile.
cd motif-balance
# Install the locked environment, including PNG, GIF and MP4 export support.
uv sync --locked --extra visualization
# Download and prepare the ArgR and Cra example inputs.
uv run python examples/argr-cra/prepare_inputs.py
# List the available commands.
uv run motif-balance --help
```

Use `uv run` to run Python or the CLI in this environment. Continue with
[First design](quickstart.md) or the [Python examples](../README.md#try-a-design).

<details>
<summary>Install a supplied wheel</summary>

If you received a wheel, replace the path below with that file. PyPI installation
by package name is not yet available.

```bash
# Create an isolated environment using a supported Python version.
python3 -m venv .venv
# Install the supplied wheel and its image/video dependencies.
.venv/bin/python -m pip install '/path/to/motif_balance-0.6.0a1-py3-none-any.whl[visualization]'
# Activate the environment so its commands are on your shell path.
source .venv/bin/activate
# Check that the command is available.
motif-balance --help
```

The wheel includes the library and CLI. The [Python tutorial](python-api.md)
also needs the source checkout's `examples/argr-cra` directory. From the checkout
root, use the installed wheel's interpreter to prepare its inputs:

```bash
# Download and prepare the two profiles using the installed package.
python examples/argr-cra/prepare_inputs.py
```

Then run the tutorial from that checkout. Use `motif-balance` in place of
`uv run motif-balance` when the wheel environment is active.

</details>

Development and release checks are described in [Contributing](../CONTRIBUTING.md).

The `visualization` extra exports a recorded search state as a PNG image, or the
saved states as an animated GIF or MP4 video. Each frame places the DNA and motif
logos beside the best-balance curve. SVG figures, HTML inspection and browser
playback work without the extra. See [playback exports](reference/playback.md#export-media).
