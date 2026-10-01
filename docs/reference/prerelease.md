# Prepare and publish a release

Publish the exact wheel and source distribution tested from a clean commit.
Keep their checksums and build attestation with the release.

## Review a development build

From the repository root:

```bash
# Run tests, documentation checks and package-installation checks.
bash ./scripts/verify
# Build the wheel and source archive into a new review directory.
uv build --no-sources --out-dir /absolute/path/to/review-dist
# Install the built distributions and check their public commands and examples.
bash ./scripts/wheel-smoke /absolute/path/to/review-dist
```

Use an empty output directory. `wheel-smoke` installs each distribution separately
and checks the API, CLI, and documented Python workflows outside the checkout.
Set `MOTIF_BALANCE_SMOKE_PYTHON=3.13` or `3.14` to check another interpreter.
Uncommitted builds are for review and have no release attestation.

## Update dependencies

Review dependency changes and update `BUILD_LOCK_SHA256` in
`src/motif_balance/constants.py` whenever `uv.lock` changes, then run verification.
This digest identifies the build's dependency lock in execution records.
Dependabot changes the lock but needs this digest update before checks pass.

```bash
# Calculate the lockfile checksum to record with this dependency update.
uv run --locked python -c 'import hashlib; from pathlib import Path; print(hashlib.sha256(Path("uv.lock").read_bytes()).hexdigest())'
```

## Prepare the release files

Choose a version that has not been published. Commit the reviewed changes and
start from a clean checkout whose `HEAD` is contained in `origin/main`. Then run:

```bash
# Build and verify release files, recording this local build and its limits.
bash ./scripts/prepare-prerelease \
  --out /absolute/path/outside/repository/dist-release \
  --builder-kind maintainer_local \
  --limitation independent_rebuild_not_performed
```

The output path must be absolute, outside the repository, and nonexistent.
The command verifies the source, builds from an immutable `git archive` snapshot,
tests the distributions, and records revision, lock, environment, and checksums.
It produces four files: wheel, source distribution,
`release-build-attestation.json`, and `SHA256SUMS`. Declare at least one applicable
limitation. The example records that no independent rebuild has been compared.

Create an annotated `v<version>` tag at that commit and a draft GitHub release.
Upload these four unchanged files, download them into a fresh directory, and
verify the download from the tagged checkout:

```bash
# Check the downloaded release files against the recorded source revision.
uv run --locked python scripts/release_attestation.py verify \
  --directory /path/to/fresh-download \
  --repository-root "$(pwd)" \
  --require-tag
# Install and test those same release files against the current source revision.
MOTIF_BALANCE_PRODUCER_REVISION="$(git rev-parse HEAD)" \
  bash ./scripts/wheel-smoke /path/to/fresh-download
```

Publish the GitHub release after both checks pass. The tag-triggered
`release.yaml` workflow stages these four files without publishing them.
Never replace published files; release fixes under a new version.

## Publish the verified GitHub release to PyPI

Keep the PyPI Trusted Publisher restricted to `e-south/motif-balance`, workflow
`publish.yaml`, and protected environment `pypi`. Check
[PyPI Publishing settings](https://docs.pypi.org/trusted-publishers/adding-a-publisher/)
and GitHub environment protections before publishing.

Run **Publish verified distributions** in GitHub Actions with the published tag.
It checks the annotated tag and main ancestry, downloads all four files, verifies
the attestation, and reruns distribution tests. The protected job uploads only
the wheel and source distribution through
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
without a persistent API token.

Approve the `pypi` environment only for the reviewed version and commit. After
publication, confirm its files and hashes on PyPI and test an explicit install:

```bash
# Install the exact version published in the preceding release step.
python -m pip install "motif-balance==<published-version>"
# Confirm the installed command and list its available operations.
motif-balance --help
```
