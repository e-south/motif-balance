---
doc_id: motif-balance-release
title: Prepare and publish a release
intent: Verify installable distributions and publish the reviewed files.
audience:
  - maintainers
owner: Eric J. South, Dunlop Lab
status: active
last_verified: 2026-09-21
doc_type: how-to
---

# Prepare and publish a release

Build a wheel and source distribution for the same version, test their installed
behavior, and publish those exact files. A development build can be reviewed
before committing. A release must identify a clean commit and preserve its
checksums. Return to the [documentation index](../README.md) for user guides.

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

Use an empty output directory. `wheel-smoke` checks both distributions, installs
each in a separate environment, and compares the installed API and command-line
behavior with the source tree. It also executes the documented Python workflows
outside the checkout. Set `MOTIF_BALANCE_SMOKE_PYTHON=3.13` or `3.14` to check another
supported interpreter. A build from uncommitted files is review material; it does
not yet have a release attestation.

## Update dependencies

Review dependency changes before refreshing the lock. After `uv lock` changes
`uv.lock`, update `BUILD_LOCK_SHA256` in `src/motif_balance/constants.py` to its
SHA-256 digest, then run verification. Execution records include this identity so
a retained result can identify the dependency lock used by its producing build.
Dependabot updates the lock but does not update this embedded digest; its pull
requests need that small follow-up before the repository checks can pass.

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

The output directory must be absolute, outside the repository, and nonexistent.
The command runs verification, builds from an immutable `git archive` snapshot,
checks the resulting distributions, and records the revision, dependency lock,
environment and artifact checksums. It produces the wheel, source distribution,
`release-build-attestation.json`, and `SHA256SUMS`. Declare only limitations that
apply to this build; the example states that a second independent build has not
been compared. The current attestation format requires at least one declared
limitation.

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

Publish the GitHub release after these checks pass. The tag-triggered
`release.yaml` workflow can stage the same four verified files for download; it
does not publish them. Versioned release files are immutable. Correct a defect
with a new version rather than replacing published bytes.

## Configure PyPI once

Keep the distribution and command name **motif-balance** and the Python import
**motif_balance**. Hyphens are valid in distribution names. Package indexes treat
`motif-balance`, `motif_balance`, and `motif.balance` as the same normalized name;
`motifbalance` would be a different name. See the [PyPA naming specification](https://packaging.python.org/en/latest/specifications/name-normalization/).

A PyPI account needs a verified email address and two-factor authentication.
There is no separate application by email to become a trusted account. A
*Trusted Publisher* is an authorized publishing workflow, configured through the
PyPI website. See [PyPI account requirements](https://pypi.org/help/#my-account).

For the first release, configure a [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
in your PyPI account with these values:

- PyPI project: `motif-balance`
- GitHub owner: `e-south`
- Repository: `motif-balance`
- Workflow filename: `publish.yaml`
- Environment: `pypi`

Also create the `pypi` environment in GitHub and require a release review before
it runs. PyPI recommends using an environment to restrict trusted publishing.
For an existing project, add the same configuration under its [Publishing settings](https://docs.pypi.org/trusted-publishers/adding-a-publisher/).
A pending publisher does not reserve the project name; creation occurs on the
first successful upload. Check availability when configuring it, since an absent
public project page does not prove that a name can be registered.

## Publish the verified GitHub release to PyPI

After account and environment setup, manually run **Publish verified
distributions** in GitHub Actions and supply the published release tag.
`publish.yaml` checks the annotated tag and main-branch ancestry, downloads the
four release assets, verifies the attestation, and reruns distribution tests.
Only the wheel and source distribution proceed to the protected publishing job.
That job uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
so no persistent API token is stored in this repository.

Approve the `pypi` environment only for the reviewed version and commit. After
publication, confirm its files and hashes on PyPI and test an explicit install:

```bash
# Install the exact version published in the preceding release step.
python -m pip install "motif-balance==<published-version>"
# Confirm the installed command and list its available operations.
motif-balance --help
```

An exact version allows an alpha release to be installed deliberately. Ordinary
unversioned installs generally skip releases. Publishing and account setup
are maintainer actions, separate from building and reviewing the package.
