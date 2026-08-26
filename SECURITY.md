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
numbers, and inconsistent matrix dimensions before allocation or search.
Readers enforce byte and record-count limits and reject symlinks. YAML uses
safe loading followed by strict schema validation.

Artifact paths are normalized relative POSIX paths. Parent traversal, absolute
paths, symlinks, special files, and pre-existing output directories are
rejected. Verification requires a complete manifest and does not fetch remote
content. Network access stays outside the deterministic core.

## Reporting and release

Report vulnerabilities through a private GitHub Security Advisory. Before any
GitHub release, run `bash ./scripts/agent-verify`, inspect wheel and source-
distribution contents, review dependency and code scans, and verify the exact
artifacts in a clean environment. Never put sensitive sequences or credentials
in an issue or diagnostic attachment.
