---
doc_id: motif-balance-private-prerelease
title: Private prerelease procedure
intent: Build and verify one immutable checksummed private prerelease from an exact main commit.
audience:
  - maintainers
  - security reviewers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: how-to
---

# Private prerelease procedure

The release authority is `scripts/prepare-private-prerelease`. It runs the
complete package gate, builds once from the current clean commit, verifies the
exact distributions, and emits a canonical build attestation plus checksums.
The distributions are built from a `git archive` snapshot of `HEAD`, not from
mutable working-tree files. Attestation identity is derived from committed
`pyproject.toml` and `uv.lock` bytes, and the source tree is rechecked after the
build.
GitHub Actions may invoke the same command, but runner availability is not a
semantic property of the package or its release bytes. Automation only stages
short-retention build artifacts; it never publishes a release. A maintainer
owns the draft, independent download verification, and final publication gate.

## Prepare exact assets

Start from a clean checkout whose `HEAD` is contained in `origin/main`. Record
why any normal automation was unavailable as an explicit limitation:

```bash
bash ./scripts/prepare-private-prerelease \
  --out dist-release \
  --builder-kind maintainer_local \
  --limitation hosted_ci_unavailable_account_billing \
  --limitation codeql_not_executed \
  --limitation github_dependency_review_not_executed \
  --limitation independent_rebuild_not_performed
```

The command refuses a dirty checkout or existing output path. It produces
exactly four release assets:

- the versioned wheel;
- the versioned source distribution;
- `release-build-attestation.json`;
- `SHA256SUMS` covering the other three files.

The attestation binds the repository, revision, Git tree, tag, version, lock
digest, build environment, passed gates, artifact digests, and declared
limitations. It contains no machine path or credential.

## Publish and verify

Create an annotated version tag object at the verified commit; a lightweight
tag does not satisfy the verification contract. Create the private
GitHub prerelease as a draft, upload the unchanged four files, and download
them into a fresh directory. From the exact tagged source, verify the download:

```bash
uv run --locked python scripts/release_attestation.py verify \
  --directory /path/to/fresh-download \
  --repository-root "$(pwd)" \
  --require-tag
MOTIF_BALANCE_PRODUCER_REVISION="$(git rev-parse HEAD)" \
  bash ./scripts/wheel-smoke /path/to/fresh-download
```

Publish the draft only after both commands pass and the remote annotated tag
peels to the verified commit. Never rebuild, replace, or move published version
bytes. A defect after publication requires a new version; retained execution
workspaces continue to use the wheel recorded inside their own trust boundary.
