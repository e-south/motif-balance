---
doc_id: motif-balance-security
title: Motif Balance security and public-data boundary
intent: Define safe inputs, output paths, repository content, and release gates.
audience: [maintainers, security reviewers]
owner: Motif Balance maintainers
status: active
last_verified: 2026-09-20
doc_type: reference
---

# Motif Balance security and public-data boundary

## Public repository content

Treat every tracked file, test fixture, log, and built artifact as potentially
public. Do not add private study identifiers, unpublished biological sequences,
raw datasets, credentials, tokens, machine-local paths, or neighboring-
repository outputs. Examples may contain synthetic motifs or biological profiles with explicit source
identifiers and redistribution terms.

Distribution builds and checks do not publish a package. Publishing permissions
and release verification are described in the
[release procedure](docs/reference/prerelease.md).

## Untrusted inputs and paths

Strict schema boundaries reject unknown fields, unsafe alphabets, non-finite
numbers, inconsistent matrix dimensions, and out-of-contract resource budgets
before compilation or search.
Readers enforce byte and record-count limits and reject symlinks. Bundle
inspection pins the directory descriptor, reads each regular member at most
once with `O_NOFOLLOW`, checks inode and size before and after the bounded read,
and parses only that immutable byte snapshot. YAML uses safe duplicate-key
rejection followed by strict schema validation.

Product inspection never recursively discovers result roots. Inspection uses
the bundle contract by default and requires an explicit execution-source mode.
Derived output is rejected if it would land at or below an inspected result
root. Inspection records contain no source path and do not execute, import, or
fetch anything named by the inspected object.

Search observations use bounded snapshots, incumbent receipts, and quality
samples. They contain sequences and model inputs, so callers must keep private
observations outside public repositories. See the
[observation contract](docs/reference/search-observations.md) for replay and
retention limits.

Artifact paths are normalized relative POSIX paths. Parent traversal, absolute
paths, symlinks, special files, and pre-existing output directories are
rejected. Verification requires a complete manifest and does not fetch remote
content. Network access stays outside the deterministic core.

## Reporting and release

Report vulnerabilities through a [private GitHub Security Advisory](https://github.com/e-south/motif-balance/security/advisories/new). Before any
GitHub release, use the
[prerelease procedure](docs/reference/prerelease.md). It runs
the repository checks, inspects and smoke-tests the exact distributions, records
available dependency and code-review evidence, and records which checks could not be completed. Independently download and verify the
unchanged release assets before publishing the draft. Never put sensitive
sequences or credentials in an issue or diagnostic attachment.
