# ArgR and Cra

Design 25-base DNA with matches to the *Escherichia coli* transcription factors
ArgR and Cra. Their profiles span 25 and 14 positions, so matches must overlap
within this length. The [top-level example](../../README.md#try-a-design)
loads the prepared models from Python; [First design](../../docs/quickstart.md) uses
the same request from the command line.

The numerical matrices come from **Baumgart et al. (2021), Supplementary Data 2**,
[Persistence and plasticity in bacterial gene regulation](https://doi.org/10.1038/s41592-021-01312-2).
They were inferred from DAP-seq experiments. The setup script downloads the
publisher archive, checks its SHA-256 digest and extracts only these two records. [SOURCE.json](SOURCE.json) identifies
the original archive members, retrieval URL and checksums.

- `inputs/source/` contains the extracted nucleotide probabilities and source backgrounds.
- `inputs/motifs/` contains the prepared models consumed by the design request.
- `design.yaml` fixes the length, requested count, evaluation budget and seed.

To prepare each position, we divide its four source values by their sum to
remove decimal rounding error. We then mix these probabilities with a uniform
prior: `p = (p0 + 0.025) / 1.1`. The scoring background assigns 0.25 to each base.
This gives positive probabilities for every nucleotide. The original background
is retained in the conversion record.

```bash
# Download and prepare the source profiles in a new local inputs directory.
uv run python examples/argr-cra/prepare_inputs.py
# Verify the local models against the numerical source data.
uv run python examples/argr-cra/verify_inputs.py
# Check the request before searching.
uv run motif-balance design examples/argr-cra/design.yaml --check
# Search and save the four sequences in a new directory.
uv run motif-balance design examples/argr-cra/design.yaml --out /tmp/argr-cra-result
```

The repository distributes the preparation recipe and source identifiers.
Source and prepared matrices stay in the ignored `inputs/` directory because
we have not established redistribution terms for the publisher's dataset.
Use a new `--out` directory when rerunning preparation.
