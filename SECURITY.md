---
doc_id: motif-balance-security
title: Motif Balance security and public-data boundary
intent: Define safe inputs, output paths, repository content, and release gates.
audience:
  - maintainers
  - security reviewers
owner: Motif Balance maintainers
status: active
last_verified: 2026-08-26
doc_type: reference
---

# Motif Balance security and public-data boundary

## Public by construction

Treat every tracked file, test fixture, log, and built artifact as potentially
public. Do not add private study identifiers, unpublished biological sequences,
raw datasets, credentials, tokens, machine-local paths, or neighboring-
repository outputs. Documentation examples use short synthetic motifs only.

The distribution retains the `Private :: Do Not Upload` classifier as an
accidental PyPI brake. Removing it or adding trusted publishing is a separate,
reviewed release decision. The current release workflow can create only a
GitHub prerelease from a prerelease version; it has no PyPI permission or job.

## Untrusted inputs and paths

Strict schema boundaries reject unknown fields, unsafe alphabets, non-finite
numbers, inconsistent matrix dimensions, and out-of-contract resource budgets
before compilation or search.
Readers enforce byte and record-count limits and reject symlinks. YAML uses
safe duplicate-key rejection followed by strict schema validation.

Product inspection never recursively discovers result roots. Callers declare
the current artifact kind, and derived output is rejected if it would land at
or below an inspected result root. Inspection records contain no source path
and do not execute, import, or fetch anything named by the inspected object.

Artifact paths are normalized relative POSIX paths. Parent traversal, absolute
paths, symlinks, special files, and pre-existing output directories are
rejected. Verification requires a complete manifest and does not fetch remote
content. Network access stays outside the deterministic core.

## Reporting and release

Report vulnerabilities through a private GitHub Security Advisory. Before any
GitHub release, use the
[prerelease procedure](docs/reference/prerelease.md). It runs
the owner gate, inspects and smoke-tests the exact distributions, records
available dependency and code-review evidence, and binds unavailable checks as
explicit attestation limitations. Independently download and verify the
unchanged release assets before publishing the draft. Never put sensitive
sequences or credentials in an issue or diagnostic attachment.
